"""엔진 실행기 자체 시험. 인터넷·API 키·실제 장부를 쓰지 않는다(API 응답은 가짜로 만든다).

    python -m pipeline.forecast.selftest        이 시험도 함께 돈다
"""
import contextlib
import hashlib
import io
import json
import os
import tempfile
import threading
import urllib.error
from datetime import datetime, timedelta, timezone

from ..collect import bls, store
from ..collect import selftest as collect_selftest
from ..ledger import commit as ledger_commit
from ..ledger import core
from ..ledger.commit import read_private
from . import engine as E
from . import runner as R

# 사실 표와 답 형식의 해시. 값이 달라졌다면 render·answer 를 고친 것이다 — 고치지 말고 새 번호(table/2, json/2)를 더한다.
# 등록된 레시피는 옛 번호를 가리키므로, 옛 것이 바뀌면 "레시피가 그대로면 엔진이 본 것도 그대로"가 깨진다.
PIN_TABLE_1 = "dabbdafafbd82a57355e2cd366382a67a02f18ddd442875ca232dcaf9c820605"
PIN_JSON_1 = "4db8da10322d77686cb804fb477aff5bfb32c0a34e9aefaa90687fdd10083fb0"

FIXTURE = {
    "bundle_spec": "CPI/0.2", "data_cutoff_utc": "2099-02-09T12:00:00Z",
    "event": {"kind": "CPI", "title": "소비자물가", "ref_period": "2099-01", "release_at_utc": "2099-02-11T13:30:00Z"},
    "targets": [{"target": "CPI_MOM", "name": "CPI 전월비(계절조정)", "unit": "%", "decimals": 1, "prev": {"period": "2098-12", "value": 0.2, "note": ""}},
                {"target": "CPI_YOY", "name": "CPI 전년비", "unit": "%", "decimals": 1, "prev": {"period": "2098-11", "value": 2.0, "note": "직전 달 값이 비어 있어 그보다 앞선 값입니다"}}],
    "history": {"CPI_MOM": [{"period": "2098-11", "value": 0.3}, {"period": "2098-12", "value": 0.2}], "CPI_YOY": [{"period": "2098-11", "value": 2.0}]},
    "history_fine": {"CPI_MOM": [{"period": "2098-11", "value": 0.26}, {"period": "2098-12", "value": 0.16}], "CPI_YOY": []},
    "components": [{"series": "CUSR0000SA0E", "name": "에너지", "measure": "전월비 % (지수로 계산, 소수 둘째 자리)", "values": [{"period": "2098-11", "value": -1.24}, {"period": "2098-12", "value": 0.4}]},
                   {"series": "CUSR0000SAH1", "name": "주거", "measure": "전월비 % (지수로 계산, 소수 둘째 자리)", "values": [{"period": "2098-12", "value": 0.31}]}],
    "related": {"EMP": [{"series": "LNS14000000", "name": "실업률", "measure": "%", "values": [{"period": "2098-12", "value": 4.1}, {"period": "2099-01", "value": 4.2}]}], "PPI": []},
    "yoy_ingredients": {"CUUR0000SA0": {"index_prev_month": {"period": "2098-12", "value": 223.83}, "index_same_month_last_year": {"period": "2098-01", "value": None},
                                        "nsa_mom_same_month_past_years": [{"period": "2098-01", "value": 0.33}]}},
    "notes": ["모든 값은 자료 마감 시각까지 알려진 발표값입니다."],
    "coverage": {"series_used": [], "series_skipped": [], "allow_unverified": False},
}

RECIPE = {"format": "recipe/1", "provider": "anthropic", "model": "model-a", "n_runs": 5, "min_valid_runs": 3, "max_attempts": 2, "timeout_sec": 60,
          "render": "table/1", "answer": "json/1", "aggregate": "median", "request": {"max_tokens": 4000}}
CPI = ["CPI_MOM", "CPI_CORE_MOM", "CPI_YOY"]
A_VALS, O_VALS = (0.31, 0.33, 0.37, 0.39, 0.41), (0.51, 0.53, 0.57, 0.59, 0.61)
ENV = {"ANTHROPIC_API_KEY": "KEY-A-SECRET-VALUE", "OPENAI_API_KEY": "KEY-O-SECRET-VALUE"}
T0 = datetime(2099, 2, 10, 0, 0, tzinfo=timezone.utc)   # CPI 발표(2099-02-11 13:30 UTC) 37.5시간 전


def write_recipe(folder, **change):
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "recipe.json"), "w", encoding="utf-8") as f:
        json.dump(dict(RECIPE, **change), f)
    with open(os.path.join(folder, "prompt.md"), "w", encoding="utf-8") as f:
        f.write("아래 자료로 답하세요.\n\n{{FACTS}}\n\n{{ANSWER_FORMAT}}\n")
    with open(os.path.join(folder, "system.md"), "w", encoding="utf-8") as f:
        f.write("시험용 지시문\n")
    return folder


def anthropic_doc(text, stop="end_turn", usage=None):
    return {"type": "message", "model": "model-a-snapshot", "stop_reason": stop, "usage": usage or {"input_tokens": 1000, "output_tokens": 500},
            "content": [{"type": "thinking", "thinking": "{\"forecasts\": \"생각 속의 것은 읽지 않는다\"}"}, {"type": "text", "text": text}]}


def openai_doc(text, status="completed", why=None):
    return {"object": "response", "model": "model-o-snapshot", "status": status, "incomplete_details": {"reason": why} if why else None,
            "usage": {"input_tokens": 900, "output_tokens": 700},
            "output": [{"type": "reasoning", "summary": []}, {"type": "message", "content": [{"type": "output_text", "text": text}]}]}


def answer(ids, p50):
    """형식이 맞는 답. 지표마다 p50 주위로 범위를 둔다."""
    return "따져 본 과정 {중괄호가 섞여도 된다}.\n```json\n%s\n```" % json.dumps(
        {"forecasts": {t: {"p10": round(p50 - 0.1, 2), "p50": p50, "p90": round(p50 + 0.1, 2)} for t in ids}})


def good(who, ids, vals):
    make = anthropic_doc if who == "anthropic" else openai_doc
    return [(200, make(answer(ids, v)), ("", "")) for v in vals]


class FakeApi:
    """두 회사 API 흉내. plan[회사] = 부를 때마다 차례로 쓰는 응답 목록(마지막 것은 되풀이). 응답은 (HTTP 상태, 문서, (오류 종류, 설명)) 또는 예외"""

    def __init__(self, clock=None, takes=0):
        self.plan, self.calls, self.bodies, self.lock = {}, {"anthropic": 0, "openai": 0}, [], threading.Lock()
        self.clock, self.takes = clock, takes

    def send(self, url, headers, body, timeout):
        who = "anthropic" if "anthropic.com" in url else "openai"
        with self.lock:
            i = self.calls[who]
            self.calls[who] += 1
            self.bodies.append((who, headers, body))
            if self.clock:
                self.clock.t += self.takes
        item = self.plan[who][min(i, len(self.plan[who]) - 1)]
        if isinstance(item, Exception):
            raise item
        return item + (None,)


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def quiet(fn, *args, **kw):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = fn(*args, **kw)
    return code, buf.getvalue()


def said(res):
    return json.dumps([res["result"], res["memo"]], ensure_ascii=False)


class World:
    """시험 하나가 쓰는 가짜 장부·레시피 둘(alpha=anthropic, beta=openai)·가짜 API. DB 와 일정표는 함께 쓴다."""

    def __init__(self, tmp, name, db, sched):
        base = os.path.join(tmp, name)
        self.led, self.prv, self.eng, self.runs = (os.path.join(base, d) for d in ("ledger", "private", "engines", "runs"))
        self.work = os.path.join(self.runs, "CPI_2099-01")
        sig = os.path.join(base, "target_2099-02-02.json")
        os.makedirs(base)
        with open(sig, "w", encoding="utf-8") as f:
            json.dump({"generator": "live_signal_a_selftest", "engine": "A", "params": {}, "asof_week": "2099-02-02", "generated_at": "2099-02-02",
                       "orders": {"exit": [], "entry": []}, "model_positions": [{"symbol": "HOLD"}], "context": {}}, f)
        self.common = ["--engines-dir", self.eng, "--ledger-dir", self.led, "--private-dir", self.prv]
        quiet(ledger_commit.main, ["--file", sig, "--signals-csv", os.path.join(base, "signals.csv"), "--no-ots"] + self.common[2:])
        write_recipe(os.path.join(self.eng, "alpha", "v1"))
        write_recipe(os.path.join(self.eng, "beta", "v1"), provider="openai", model="model-o", request={"max_output_tokens": 9000, "reasoning": {"effort": "high"}})
        self.registered = [quiet(R.main, ["register", "--name", n, "--label", lab, "--version", "1", "--no-ots"] + self.common)[0] for n, lab in (("alpha", "알파"), ("beta", "베타"))]
        self.api, self.builds, self.env = FakeApi(), [], dict(ENV)
        self.opts = {"ledger_dir": self.led, "private_dir": self.prv, "engines_dir": self.eng, "runs_dir": self.runs, "schedule": sched, "db": db, "no_ots": True}

    def build(self, kind, ref, cutoff, release_at, o):
        self.builds.append(cutoff)
        return R.build_bundle_from_db(kind, ref, cutoff, release_at, o)

    def go(self, when=T0, clock=None, **more):
        kw = {"clock": clock} if clock else {}
        return R.run_event("CPI", "2099-01", dict(self.opts, **more), now=when, env=self.env, send=self.api.send, sleep=lambda s: None, build=self.build, **kw)

    def ledger(self):
        return core.read_ledger(os.path.join(self.led, "ledger.jsonl"))

    def sealed_values(self, entry):
        p = read_private(self.prv, entry)["payload"]
        return p, {(f["engine"], f["target"]): f for f in p["forecasts"]}


def unit_checks(check, tmp):
    # --- 레시피 검사
    good_recipe, problems = R.load_recipe(write_recipe(os.path.join(tmp, "good")))
    check("레시피: 형식이 맞으면 읽음", good_recipe is not None and not problems and good_recipe["system"] == "시험용 지시문", problems)
    _, p = R.load_recipe(write_recipe(os.path.join(tmp, "tools"), request={"max_tokens": 4000, "tools": [{"type": "web_search"}]}))
    check("레시피: 도구·검색을 켠 요청은 거부", any("tools" in x for x in p), p)
    _, p = R.load_recipe(write_recipe(os.path.join(tmp, "oa"), provider="openai", request={"max_output_tokens": 9000, "reasoning": {"effort": "high"}, "previous_response_id": "x", "store": True}))
    check("레시피: 이어 붙이거나 상대 서버에 남기는 요청은 거부", any("previous_response_id" in x for x in p) and any("store" in x for x in p), p)
    _, p = R.load_recipe(write_recipe(os.path.join(tmp, "oatools"), provider="openai", request={"max_output_tokens": 9000, "tools": [{"type": "web_search"}], "tool_choice": "auto", "truncation": "auto"}))
    check("레시피(openai): 도구·검색·입력 자르기는 거부", all(any(k in x for x in p) for k in ("tools", "tool_choice", "truncation")), p)
    _, p = R.load_recipe(write_recipe(os.path.join(tmp, "nomax"), request={}))
    _, p2 = R.load_recipe(write_recipe(os.path.join(tmp, "nomax2"), provider="openai", request={"reasoning": {"effort": "high"}}))
    _, p3 = R.load_recipe(write_recipe(os.path.join(tmp, "nomax3"), request={"max_tokens": 900000}))
    check("레시피: 출력 상한이 없거나 터무니없으면 거부(쓸 토큰이 미리 정해지게)", any("max_tokens" in x for x in p) and any("max_output_tokens" in x for x in p2) and p3, (p, p2, p3))
    _, p = R.load_recipe(write_recipe(os.path.join(tmp, "render"), render="table/9"))
    check("레시피: 모르는 사실 표 번호는 거부", any("render" in x for x in p), p)
    _, p = R.load_recipe(write_recipe(os.path.join(tmp, "types"), provider=["anthropic"], n_runs=5.0, max_attempts=True))
    check("레시피: 틀린 자료형은 멈추지 않고 알려 줌", any("provider" in x for x in p) and any("n_runs" in x for x in p) and any("max_attempts" in x for x in p), p)
    bad = dict(RECIPE, extra=1)
    del bad["min_valid_runs"]
    folder = write_recipe(os.path.join(tmp, "missing"))
    with open(os.path.join(folder, "recipe.json"), "w", encoding="utf-8") as f:
        json.dump(bad, f)
    _, p = R.load_recipe(folder)
    check("레시피: 빠진 항목과 모르는 항목을 알려 줌", any("min_valid_runs" in x for x in p) and any("extra" in x for x in p), p)
    folder = write_recipe(os.path.join(tmp, "noformat"))
    with open(os.path.join(folder, "prompt.md"), "w", encoding="utf-8") as f:
        f.write("{{FACTS}} {{OTHER}}")
    _, p = R.load_recipe(folder)
    check("레시피: 답 형식 자리가 없거나 모르는 자리가 있으면 거부", any("ANSWER_FORMAT" in x for x in p) and any("OTHER" in x for x in p), p)

    # --- 사실 표·답 형식·합치기는 이름과 번호로 고정
    table = R.render_table_1(FIXTURE)
    digest = hashlib.sha256(table.encode("utf-8")).hexdigest()
    check("사실 표 table/1 이 그대로임 (달라졌다면 새 번호를 더할 것)", digest == PIN_TABLE_1, digest)
    digest = hashlib.sha256(R.answer_text_json_1(FIXTURE).encode("utf-8")).hexdigest()
    check("답 형식 json/1 이 그대로임 (달라졌다면 새 번호를 더할 것)", digest == PIN_JSON_1, digest)
    check("사실 표: 발표값 옆에 지수로 계산한 값, 빈 값은 – 로", "기간 | CPI_MOM | CPI_YOY | CPI_MOM 계산값\n" in table and "2098-12 | 0.2 | – | 0.16\n" in table
          and "| – | 0.31\n" in table and "(2098-01) – |" in table, table)
    system, user, d1 = R.build_prompt(good_recipe, FIXTURE)
    check("보내는 글: 자리 표시가 남지 않고 해시가 정해짐", "{{" not in user and table in user and len(d1) == 64 and d1 == R.build_prompt(good_recipe, FIXTURE)[2])
    cases = [([(0.1, 0.2, 0.5), (0.2, 0.3, 0.4), (0.2, 0.31, 0.6), (0.3, 0.4, 0.45), (0.0, 0.33, 0.9)], 1, (0.2, 0.31, 0.5)),   # 다섯 번: 자리마다 가운데 값
             ([(0.1, 0.12, 0.2), (0.1, 0.13, 0.2)], 1, (0.1, 0.13, 0.2)),         # 두 번: 평균 0.125 → 사사오입 0.13
             ([(0.08, 0.11, 0.6), (0.09, 0.12, 0.7)], 1, (0.09, 0.12, 0.65)),     # 0.085 → 0.09, 0.115 → 0.12 (이진 실수로 계산하면 내려간다)
             ([(0.6, 0.6, 0.6), (0.7, 0.7, 0.7)], 0, (0.7, 0.7, 0.7)),            # 발표 자릿수 0: 0.65 → 0.7
             ([(149.6, 150.26, 180.0)], 0, (149.6, 150.3, 180.0)),                # 천 명 단위는 소수 한 자리까지
             ([(-0.15, -0.05, 0.0), (-0.2, -0.1, 0.0)], 1, (-0.18, -0.08, 0.0))]  # 음수: -0.175 → -0.18, -0.075 → -0.08
    got = [tuple(R.aggregate_median([dict(zip(("p10", "p50", "p90"), r)) for r in runs], places)[k] for k in ("p10", "p50", "p90")) for runs, places, _ in cases]
    check("합치기 median 이 그대로임: 가운데 값, 십진수 사사오입 (달라졌다면 새 이름을 더할 것)", got == [c[2] for c in cases], got)

    # --- 답 읽기
    ids = ["CPI_MOM", "CPI_YOY"]
    v, why = R.parse_json_1(answer(ids, 0.37), ids)
    check("답 읽기: 글 속의 JSON", v is not None and v["CPI_MOM"] == {"p10": 0.27, "p50": 0.37, "p90": 0.47}, why)
    one = '{"forecasts": {"CPI_MOM": {"p10": 9, "p50": 9, "p90": 9}, "CPI_YOY": {"p10": 9, "p50": 9, "p90": 9}}}'
    check("답 읽기: 여러 개면 마지막 것", R.parse_json_1(one + " 고쳐서 다시: " + answer(ids, 0.37), ids)[0]["CPI_MOM"]["p50"] == 0.37)
    nested = '{"forecasts": {"CPI_MOM": {"p10": 0.2, "p50": 0.3, "p90": 0.4}}, "scenarios": {"upside": {"forecasts": {"CPI_MOM": {"p10": 0.5, "p50": 0.6, "p90": 0.7}}}}}'
    check("답 읽기: 답 안쪽에 든 다른 forecasts 는 보지 않음", R.parse_json_1(nested, ["CPI_MOM"])[0]["CPI_MOM"]["p50"] == 0.3)
    draft = '{"forecasts": {"CPI_MOM": {"p10": 0.1, "p50": 0.2, "p90": 0.3}}}'
    check("답 읽기: 끝의 답이 읽히지 않으면 앞의 초안을 대신 쓰지 않음", R.parse_json_1(draft + ' 최종: {"forecasts": {"CPI_MOM": {"p10": 0.5, "p50": 0.6, "p90": 0.7,}}}', ["CPI_MOM"])[0] is None
          and R.parse_json_1('{"설명": 틀린 JSON, "안쪽": ' + draft + "}", ["CPI_MOM"])[0] is None and R.parse_json_1(draft + " 참고 {메모}", ["CPI_MOM"])[0] is None)
    check("답 읽기: 답 뒤에 중괄호 없는 말이 붙는 것은 괜찮음, 아주 긴 글은 끝만 읽음", R.parse_json_1(draft + "\n```\n이상입니다.", ["CPI_MOM"])[0]["CPI_MOM"]["p50"] == 0.2
          and R.parse_json_1("{" * 300000 + draft, ["CPI_MOM"])[0]["CPI_MOM"]["p50"] == 0.2)
    check("답 읽기: 지표가 빠지면 틀린 답", R.parse_json_1(answer(["CPI_MOM"], 0.3), ids)[0] is None)
    check("답 읽기: 순서가 틀리면 틀린 답", R.parse_json_1('{"forecasts": {"CPI_MOM": {"p10": 0.5, "p50": 0.3, "p90": 0.6}}}', ["CPI_MOM"])[0] is None)
    shape = '{"forecasts": {"CPI_MOM": {"p10": %s, "p50": %s, "p90": %s}}}'
    wrong = [("0.2", '"0.3"', "0.4"), ("0.2", "0.3", "true"), ("0.2", "NaN", "0.4"), ("0.2", "0.3", "1" + "0" * 400), ("0.2", "0.3", "2e12")]
    check("답 읽기: 따옴표 친 숫자·참거짓·NaN·터무니없이 큰 수는 틀린 답", all(R.parse_json_1(shape % w, ["CPI_MOM"])[0] is None for w in wrong)
          and R.parse_json_1(shape % ("0", "0.3", "1"), ["CPI_MOM"])[0] == {"CPI_MOM": {"p10": 0.0, "p50": 0.3, "p90": 1.0}})
    check("답 읽기: JSON 이 없으면 틀린 답, 이유에 값이 없음", R.parse_json_1("0.37 쯤으로 봅니다", ids) == (None, "답의 끝에서 forecasts 가 든 JSON 을 찾지 못함")
          and R.parse_json_1('{"a":' * 1500, ids)[0] is None)

    # --- 요청과 응답
    url, headers, body = R.PROVIDERS["anthropic"][0]("KEY-A", good_recipe, system, user)
    check("요청(anthropic): 도구 없음, 지시문·본문·레시피 항목", "tools" not in body and body["system"] == system and body["messages"][0]["content"] == user
          and body["max_tokens"] == 4000 and headers["x-api-key"] == "KEY-A" and url.endswith("/v1/messages"), body)
    oa = dict(good_recipe, provider="openai", model="model-o", request={"reasoning": {"effort": "high"}, "max_output_tokens": 9000})
    url, headers, body = R.PROVIDERS["openai"][0]("KEY-O", oa, system, user)
    check("요청(openai): 도구 없음, 상대 서버에 남기지 않음", "tools" not in body and body["store"] is False and body["instructions"] == system
          and body["reasoning"] == {"effort": "high"} and headers["Authorization"] == "Bearer KEY-O" and url.endswith("/v1/responses"), body)
    got = R.PROVIDERS["anthropic"][1](anthropic_doc("본문"))
    check("응답(anthropic): 생각은 빼고 본문만", got["text"] == "본문" and got["done"] and got["tokens_out"] == 500, got)
    got = R.PROVIDERS["openai"][1](openai_doc("본문", "incomplete", "max_output_tokens"))
    check("응답(openai): 끝나지 않은 답을 구분", got["text"] == "본문" and not got["done"] and got["stop"] == "incomplete:max_output_tokens", got)
    odd = [R.PROVIDERS["anthropic"][1]({"content": [7, None, {"type": "text", "text": 3}, {"type": "text", "text": "글"}], "usage": ["x"], "stop_reason": "end_turn"}),
           R.PROVIDERS["anthropic"][1]({"content": None, "usage": None}),
           R.PROVIDERS["openai"][1]({"status": "completed", "output": [3, {"type": "message", "content": "x"}, {"type": "message", "content": [{"type": "output_text", "text": "글"}]}],
                                     "usage": {"input_tokens": "12", "output_tokens": 5}, "incomplete_details": "x"})]
    check("응답: 모양이 어긋나도 멈추지 않고 읽을 수 있는 것만 읽음", [o["text"] for o in odd] == ["글", "", "글"] and odd[2]["tokens_in"] is None and odd[2]["tokens_out"] == 5, odd)
    leak = [R.PROVIDERS["anthropic"][1]({"content": [], "stop_reason": "0.37 로 본다", "model": "낮게 0.37"}),
            R.PROVIDERS["openai"][1]({"status": "incomplete", "incomplete_details": {"reason": "p50 은 0.37"}, "model": ["x"]})]
    check("응답: 끝난 이유·모델 이름 자리에 다른 글이 와도 로그에 옮기지 않음", not any("0.37" in json.dumps(x, ensure_ascii=False) for x in leak) and leak[1]["stop"] == "incomplete:(알 수 없음)", leak)

    def once(resp, recipe=good_recipe):
        return R.call_once(recipe, system, user, ids, "KEY-A-SECRET", 30, send=lambda *a: resp + (None,))

    check("한 번 부르기: 맞는 답", once((200, anthropic_doc(answer(ids, 0.37)), ("", "")))["status"] == "ok")
    rec = once((200, anthropic_doc(answer(ids, 0.37), "max_tokens"), ("", "")))
    check("한 번 부르기: 중간에 끊긴 답은 쓰지 않음", rec["status"] == "invalid" and "values" not in rec, rec)
    check("한 번 부르기: 잠깐의 오류와 고칠 수 없는 오류를 구분", once((429, None, ("rate_limit_error", "")))["fatal"] is False and once((0, None, ("TimeoutError", "")))["fatal"] is False
          and once((400, None, ("invalid_request_error", "max_tokens: 너무 큼")))["fatal"] is True and once((529, None, ("overloaded_error", "")))["fatal"] is False)
    rec = once((401, None, ("invalid_api_key", "Incorrect API key provided: ****ALUE.")))
    check("한 번 부르기: 키 오류의 설명(키의 일부가 적혀 온다)은 남기지 않음", rec["fatal"] and "ALUE" not in rec["reason"] and "SECRET" not in rec["reason"] and "invalid_api_key" in rec["reason"], rec)
    rec = once((400, None, ("x", "bad header KEY-A-SECRET / sk-abc123DEF456")))
    check("한 번 부르기: 다른 오류 글에 섞인 키도 가림", "SECRET" not in rec["reason"] and "sk-abc" not in rec["reason"] and "bad header" in rec["reason"], rec)
    rec = R.call_once(good_recipe, system, user, ids, "K", 30, send=lambda *a: 1 / 0)
    check("한 번 부르기: 부르다 멈춰도 예외를 내지 않음(답이 아닌 오류로)", rec["status"] == "error" and rec["fatal"] is False, rec)
    rec = R.call_once(good_recipe, system, user, ids, "K", 30, send=lambda *a: ("200", {}, "x", "soon"))
    check("한 번 부르기: 보내는 쪽이 엉뚱한 것을 돌려줘도 예외를 내지 않음", rec["status"] == "error", rec)
    rec = once((429, None, ("rate_limit_error", "x" * 266 + "KEY-A-SECRET")))   # 키가 자르는 자리(300자)에 걸쳐 있다
    check("한 번 부르기: 긴 오류 글은 키를 가린 뒤에 자름", "KEY-A" not in rec["reason"] and len(rec["reason"]) <= 300, rec)
    rec = once((200, {"status": "failed", "error": {"code": "server_error"}, "output": []}, ("", "")), oa)
    check("한 번 부르기: 실패로 끝난 응답은 답이 아니라 오류", rec["status"] == "error" and "server_error" in rec["reason"], rec)

    # --- HTTP (가짜 연결)
    class Resp:
        status = 200

        def __init__(self, raw):
            self.raw = raw

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return self.raw

    def send(result):
        def urlopen(req, timeout=None):
            if isinstance(result, Exception):
                raise result
            return Resp(result)
        return R.http_send("https://x", {"x-api-key": "K"}, {"a": 1}, 5, urlopen=urlopen)

    def http_error(code, raw, headers):
        return urllib.error.HTTPError("https://x", code, "x", headers, io.BytesIO(raw))

    check("HTTP: 정상 응답", send(b'{"ok": 1}') == (200, {"ok": 1}, ("", ""), None))
    check("HTTP: 오류의 종류·설명·다시 부르라는 시간", send(http_error(429, b'{"error": {"type": "rate_limit_error", "message": "slow"}}', {"retry-after": "7"}))
          == (429, None, ("rate_limit_error", "slow"), 7.0))
    check("HTTP: 읽을 수 없는 오류 본문과 이상한 대기 시간", send(http_error(500, b"<html>", {"retry-after": "nan"})) == (500, None, ("", ""), None)
          and send(http_error(503, b"{}", {"retry-after": "-3"}))[3] is None)
    check("HTTP: 닿지 못함, 응답이 JSON 이 아님", send(urllib.error.URLError("refused"))[0] == 0 and send(b"not json")[:2] == (0, None))
    check("HTTP: 요청을 만들다 난 오류는 종류만 남김", send(ValueError("Invalid header value b'KEY-SECRET\\n'")) == (0, None, ("ValueError", ""), None))


def flow_checks(check, tmp, db, sched):
    # --- 1. 한 엔진이 먼저 끝나면 바로 봉인하고, 다른 엔진은 오류가 풀릴 때까지 이어 간다
    w = World(tmp, "flow", db, sched)
    reg = [read_private(w.prv, e)["payload"] for e in w.ledger() if e["kind"] == "engine"]
    check("명령 register: 레시피의 모델·횟수 그대로 등록", w.registered == [0, 0] and [(p["engine"], p["model"], p["n_runs"], p["mode"]) for p in reg]
          == [("alpha", "model-a", 5, "api"), ("beta", "model-o", 5, "api")], reg)
    code, out = quiet(R.main, ["check"] + w.common)
    check("명령 check: 등록된 레시피 둘", code == 0 and out.count("등록됨, 폴더 그대로") == 2, out)
    write_recipe(os.path.join(w.eng, "alpha", "v1.5"))
    code, out = quiet(R.main, ["register", "--name", "alpha", "--version", "1.5", "--no-ots"] + w.common)
    check("명령 register: 숫자가 아닌 버전은 거부", code == 2 and "숫자" in out and len(w.ledger()) == 4, out)
    n0 = len(w.ledger())
    w.api.plan = {"anthropic": good("anthropic", CPI, A_VALS), "openai": [(429, None, ("insufficient_quota", "충전이 필요함"))]}

    res = w.go(datetime(2099, 2, 11, 6, 0, tzinfo=timezone.utc))
    check("실행: 봉인 마감이 지났으면 부르지 않고 미제출", res["state"] == "missed" and sum(w.api.calls.values()) == 0 and not os.path.exists(w.runs), res)
    recipe_file = os.path.join(w.eng, "alpha", "v1", "prompt.md")
    original = open(recipe_file, encoding="utf-8").read()
    with open(recipe_file, "a", encoding="utf-8") as f:
        f.write("몰래 한 줄\n")
    res = w.go(T0)
    check("실행: 등록 뒤 레시피가 바뀐 엔진은 부르지 않음(다른 엔진은 그대로)", res["state"] == "pending" and res["ok"] is False and w.api.calls == {"anthropic": 0, "openai": 10}
          and res["engines"] == {"alpha@1": "blocked", "beta@1": "pending"} and "등록 때와 다름" in said(res) and "insufficient_quota" in said(res), (res, w.api.calls))
    with open(recipe_file, "w", encoding="utf-8") as f:
        f.write(original)
    res = w.go(T0 + timedelta(minutes=5), budget_sec=5)
    check("실행: 쓸 시간이 한 번 부를 시간보다 짧으면 부르지 않고 그 까닭을 알림", res["state"] == "pending" and res["ok"] is False and "짧아" in said(res)
          and w.api.calls == {"anthropic": 0, "openai": 10}, (res, w.api.calls))

    res = w.go(T0 + timedelta(minutes=10))
    first = w.ledger()[-1]
    check("실행: 답이 다 모인 엔진은 다른 엔진을 기다리지 않고 봉인", res["state"] == "pending" and res["result"].startswith("봉인함 · alpha@1") and res["ok"] is False
          and w.api.calls == {"anthropic": 5, "openai": 20} and len(w.ledger()) == n0 + 1 and first["engines"] == ["alpha@1", "prev"], (res, w.api.calls))
    check("실행: 요청에 도구가 없고 두 엔진이 같은 사실 표를 받음", all("tools" not in b for _, _, b in w.api.bodies)
          and len({(b.get("messages") or b.get("input"))[0]["content"] for _, _, b in w.api.bodies[-15:]}) == 1, len(w.api.bodies))
    for i in range(4):
        res = w.go(T0 + timedelta(minutes=30 + 20 * i))
    check("실행: 오류는 답이 아니므로 몇 번을 겪어도 미제출이 되지 않음", res["state"] == "pending" and res["engines"] == {"alpha@1": "sealed", "beta@1": "pending"}
          and w.api.calls == {"anthropic": 5, "openai": 60} and len(w.ledger()) == n0 + 1, (res, w.api.calls))
    w.api.plan["openai"] = [(429, None, ("x", ""))] * 60 + good("openai", CPI, O_VALS)
    res = w.go(T0 + timedelta(hours=3))
    second = w.ledger()[-1]
    check("실행: 오류가 풀리면 남은 엔진만 불러 한 건 더 봉인", res["state"] == "sealed" and w.api.calls == {"anthropic": 5, "openai": 65}
          and second["engines"] == ["beta@1", "prev"] and len(w.ledger()) == n0 + 2, (res, w.api.calls, second))
    p1, fc1 = w.sealed_values(first)
    p2, fc2 = w.sealed_values(second)
    check("봉인된 값: 다섯 번의 가운데 값과 범위, 번마다의 답, 기준선", fc1[("alpha", "CPI_MOM")]["p50"] == 0.37 and fc1[("alpha", "CPI_MOM")]["p10"] == 0.27
          and len(fc1[("alpha", "CPI_MOM")]["runs"]) == 5 and fc2[("beta", "CPI_YOY")]["p50"] == 0.57 and fc1[("prev", "CPI_MOM")]["p50"] == 0.2, (fc1, fc2))
    check("두 봉인이 같은 묶음·같은 기준선: 첫 답을 받은 뒤로 묶음을 바꾸지 않음", p1["bundle_sha256"] == p2["bundle_sha256"] and p1["data_cutoff_utc"] == p2["data_cutoff_utc"] == "2099-02-10T00:10:00Z"
          and fc1[("prev", "CPI_YOY")] == fc2[("prev", "CPI_YOY")] and w.builds == ["2099-02-10T00:00:00Z", "2099-02-10T00:05:00Z", "2099-02-10T00:10:00Z"], w.builds)
    ex = p1["execution"]
    check("봉인 원문에 실행 기록: 보낸 글의 해시, 응답한 모델, 맞는 답의 수", ex["runner"] == R.RUNNER and ex["engines"][0]["valid_runs"] == 5 and ex["others"] == {"beta@1": "pending"}
          and ex["engines"][0]["models_reported"] == ["model-a-snapshot"] and len(ex["engines"][0]["prompt_sha256"]) == 64 and p2["execution"]["others"] == {"alpha@1": "sealed"}, ex)
    public = open(os.path.join(w.led, "ledger.jsonl"), encoding="utf-8").read()
    logs = "".join(open(os.path.join(b, n), encoding="utf-8").read() for b, _, names in os.walk(w.runs) for n in names if n == "errors.jsonl")
    check("엔진이 낸 값·키가 결과 글·공개 장부·오류 기록에 없음", not any(("%.2f" % v) in text for v in A_VALS + O_VALS for text in (said(res), public, logs))
          and "SECRET" not in said(res) + public + logs and "model-a" not in public and '"p50"' not in public and "insufficient_quota" in logs, said(res))
    res = w.go(T0 + timedelta(hours=4))
    check("실행: 이미 봉인된 발표는 부르지 않음", res["state"] == "already" and w.api.calls == {"anthropic": 5, "openai": 65} and len(w.ledger()) == n0 + 2, res)

    # --- 2. 형식이 틀린 답만 내는 엔진은 미제출, 다른 엔진은 봉인
    w = World(tmp, "invalid", db, sched)
    w.api.plan = {"anthropic": [(200, anthropic_doc("0.37 쯤으로 봅니다"), ("", ""))], "openai": good("openai", CPI, O_VALS)}
    res = w.go(parallel=1)
    check("실행: 형식이 틀린 답은 정해진 횟수만 다시 받고, 모자랄 것이 확실해지면 그만 부름", res["state"] == "sealed" and "미제출: alpha@1" in res["result"]
          and w.api.calls == {"anthropic": 6, "openai": 5} and w.ledger()[-1]["engines"] == ["beta@1", "prev"] and "0.37" not in said(res), (res, w.api.calls))
    res = w.go(T0 + timedelta(minutes=20))
    check("실행: 미제출을 뒤늦게 채우지 않음", res["state"] == "already" and "미제출: alpha@1" in res["result"] and w.api.calls == {"anthropic": 6, "openai": 5}, (res, w.api.calls))

    # --- 3. 마감이 가까우면 받은 답으로 마무리 / 고칠 수 없는 오류(키)는 그 실행에서 더 부르지 않음
    w = World(tmp, "final", db, sched)
    w.api.plan = {"anthropic": good("anthropic", CPI, (0.31, 0.37, 0.41)) + [(503, None, ("api_error", "잠깐의 오류"))],
                  "openai": [(401, None, ("invalid_api_key", "Incorrect API key provided: sk-proj-****ALUE"))]}
    res = w.go(parallel=1)
    check("실행: 키 오류는 한 번만 부르고 멈추며, 키의 일부가 적힌 설명을 남기지 않음", res["state"] == "pending" and w.api.calls == {"anthropic": 7, "openai": 1}
          and "invalid_api_key" in said(res) and "ALUE" not in said(res) and "SECRET" not in said(res), (res, w.api.calls))
    with open(os.path.join(w.eng, "beta", "v1", "prompt.md"), "a", encoding="utf-8") as f:
        f.write("등록 뒤에 고침\n")   # 쓸 수 없게 된 엔진도 마감이 가까우면 미제출로 닫힌다
    res = w.go(datetime(2099, 2, 11, 0, 45, tzinfo=timezone.utc))   # 발표 12.75시간 전: 마감 한 시간 안쪽
    _, fc = w.sealed_values(w.ledger()[-1])
    check("실행: 마감이 가까우면 더 부르지 않고 받은 답(3번)으로 봉인, 못 받은 엔진은 미제출", res["state"] == "sealed" and w.api.calls == {"anthropic": 7, "openai": 1}
          and fc[("alpha", "CPI_MOM")]["n_runs"] == 3 and fc[("alpha", "CPI_MOM")]["p50"] == 0.37 and "미제출: beta@1" in res["result"]
          and res["engines"] == {"alpha@1": "sealed", "beta@1": "missed"} and "등록 때와 다름" in said(res), (res, w.api.calls))
    res = w.go(datetime(2099, 2, 11, 2, 0, tzinfo=timezone.utc))
    check("실행: 마감 뒤에는 봉인된 것만 알려 주고 아무것도 하지 않음", res["state"] == "already" and "마감" in res["result"] and w.api.calls == {"anthropic": 7, "openai": 1}, res)

    # --- 4. 키가 없는 엔진이 있어도 다른 엔진은 봉인된다 / 이 발표에 쓸 엔진은 처음 정한 대로
    w = World(tmp, "nokey", db, sched)
    w.env = {"ANTHROPIC_API_KEY": " KEY-A-SECRET-VALUE\n"}
    w.api.plan = {"anthropic": good("anthropic", CPI, A_VALS), "openai": good("openai", CPI, O_VALS)}
    res = w.go()
    check("실행: 키가 없는 엔진은 기다리고(알림), 키가 있는 엔진은 봉인", res["state"] == "pending" and res["ok"] is False and res["engines"] == {"alpha@1": "sealed", "beta@1": "pending"}
          and "OPENAI_API_KEY" in said(res) and w.api.calls == {"anthropic": 5, "openai": 0} and w.api.bodies[0][1]["x-api-key"] == "KEY-A-SECRET-VALUE", res)
    write_recipe(os.path.join(w.eng, "beta", "v2"), provider="openai", model="model-o2", request={"max_output_tokens": 9000})
    quiet(R.main, ["register", "--name", "beta", "--label", "베타", "--version", "2", "--no-ots"] + w.common)
    w.env = dict(ENV)
    res = w.go(T0 + timedelta(minutes=20))
    check("실행: 중간에 새 버전이 등록돼도 이 발표는 처음 정한 엔진으로 끝냄", res["state"] == "sealed" and w.ledger()[-1]["engines"] == ["beta@1", "prev"]
          and w.api.bodies[-1][2]["model"] == "model-o", (res, w.ledger()[-1]))

    # --- 5. 어긋난 응답·중간의 예외·상한 파일·봉인 실패가 있어도 받은 답을 잃지 않고 멈추지 않는다
    w = World(tmp, "odd", db, sched)
    weird = [(200, anthropic_doc(answer(CPI, v), usage={"input_tokens": "천", "output_tokens": [5]}), ("", "")) for v in A_VALS]
    w.api.plan = {"anthropic": [RuntimeError("연결이 끊김")] + weird, "openai": [(429, None, ("rate_limit_error", ""))]}
    res = w.go(parallel=1)
    _, fc = w.sealed_values(w.ledger()[-1])
    check("실행: 토큰 수가 이상한 응답과 부르다 난 예외가 있어도 받은 답 다섯 개로 봉인", res["state"] == "pending" and res["engines"]["alpha@1"] == "sealed"
          and w.api.calls == {"anthropic": 6, "openai": 10} and fc[("alpha", "CPI_MOM")]["p50"] == 0.37, (res, w.api.calls))
    with open(os.path.join(w.work, "beta@1", "run01_ans01.json"), "w", encoding="utf-8") as f:
        f.write("{반쯤 쓰다 만 파일")
    w.api.plan["openai"] = [(429, None, ("x", ""))] * 10 + [(200, openai_doc("JSON 없음"), ("", ""))] + good("openai", CPI, O_VALS)
    seal_main = R.S.main
    R.S.main = lambda argv, now=None: 2
    try:
        res = w.go(T0 + timedelta(minutes=20), parallel=1)
    finally:
        R.S.main = seal_main
    calls = dict(w.api.calls)
    check("실행: 읽을 수 없는 답 파일은 틀린 답 하나로 셈(그 번은 한 번만 더 받는다)", calls == {"anthropic": 6, "openai": 15} and "형식이 틀린 답 2번" in said(res), (res, calls))
    check("실행: 봉인 명령이 멈추면 받은 답은 그대로 두고 알림", res["state"] == "blocked" and res["ok"] is False and "봉인 명령이 멈춤" in res["result"], res)
    res = w.go(T0 + timedelta(minutes=40), parallel=1)
    _, fc = w.sealed_values(w.ledger()[-1])
    check("실행: 다시 돌리면 더 부르지 않고 봉인부터(남은 네 번의 가운데 값)", res["state"] == "sealed" and w.api.calls == calls and fc[("beta", "CPI_MOM")]["n_runs"] == 4
          and fc[("beta", "CPI_MOM")]["p50"] == 0.55, (res, w.api.calls, fc[("beta", "CPI_MOM")]))

    # --- 6. 겹쳐 도는 실행, 한 번의 실행에 쓸 시간, 받아 둔 답과 다른 글, 상한 묶음
    w = World(tmp, "guard", db, sched)
    plan = {"anthropic": good("anthropic", CPI, A_VALS[:2]) + [(503, None, ("api_error", ""))], "openai": [(503, None, ("api_error", ""))]}
    w.api.plan = plan
    with R.work_lock(w.work) as held:
        res = w.go()
        try:
            import fcntl   # noqa: F401
            locked = held and res["state"] == "pending" and "다른 실행" in res["result"] and sum(w.api.calls.values()) == 0
        except ImportError:
            locked = True   # Windows: 잠금이 없다. 실제 실행은 서버에서만 한다
    check("실행: 같은 발표를 다른 실행이 다루는 중이면 아무것도 하지 않음", locked, res)
    clock = Clock()
    w.api = FakeApi(clock, takes=50)
    w.api.plan = plan
    w.env = {"ANTHROPIC_API_KEY": "KEY-A-SECRET-VALUE"}   # 시계를 한 엔진만 움직이게(두 엔진은 따로 돌아서 순서가 정해져 있지 않다)
    res = w.go(clock=clock, budget_sec=100, parallel=1)
    check("실행: 남은 시간이 한 번 부를 시간보다 짧아지면 그만 부름(받다 만 답을 만들지 않는다)", res["state"] == "pending" and w.api.calls == {"anthropic": 1, "openai": 0}, (res, w.api.calls))
    w.env = dict(ENV)
    res = w.go(T0 + timedelta(minutes=20), parallel=1)
    name = os.path.join(w.work, "alpha@1", "run01_ans01.json")
    with open(name, encoding="utf-8") as f:
        rec = json.load(f)
    with open(name, "w", encoding="utf-8") as f:
        json.dump(dict(rec, prompt_sha256="0" * 64), f)
    before = dict(w.api.calls)
    res = w.go(T0 + timedelta(minutes=40), parallel=1)
    check("실행: 받아 둔 답이 지금 보낼 글과 다른 글의 답이면 그 엔진을 멈춤", res["engines"]["alpha@1"] == "blocked" and "다른 글" in said(res)
          and w.api.calls["anthropic"] == before["anthropic"] and before["anthropic"] > 1, (res, w.api.calls))
    with open(name, "w", encoding="utf-8") as f:
        json.dump(rec, f)
    bundle_file = os.path.join(w.work, "bundle.json")
    with open(bundle_file, encoding="utf-8") as f:
        changed = json.load(f)
    changed["notes"].append("답을 받은 뒤에 끼워 넣은 줄")
    with open(bundle_file, "w", encoding="utf-8") as f:
        json.dump(changed, f, ensure_ascii=False)
    before = dict(w.api.calls)
    res = w.go(T0 + timedelta(minutes=60))
    check("실행: 답을 받은 뒤에 사실 묶음이 바뀌었으면 아무 엔진도 부르지 않음", res["state"] == "blocked" and "다른 묶음" in res["result"] and w.api.calls == before, res)
    for text, word in (("{", "읽지 못함"), ('{"targets": []}', "모양이 틀림"), ("[" * 100000, "읽지 못함")):
        with open(bundle_file, "w", encoding="utf-8") as f:
            f.write(text)
        res = w.go(T0 + timedelta(minutes=60))
        check("실행: 상한 묶음 파일(%d자)은 멈추지 않고 알림" % len(text), res["state"] == "blocked" and word in res["result"] and w.api.calls == before, res)
    with open(os.path.join(w.work, "plan.json"), "w", encoding="utf-8") as f:
        f.write('{"engines": "x"}')
    res = w.go(T0 + timedelta(minutes=60))
    check("실행: 받아 둔 답이 있는데 엔진 목록을 읽지 못하면 새로 정하지 않고 알림", res["state"] == "blocked" and "plan.json" in res["result"] and w.api.calls == before, res)

    # --- 8. 엔진 고르기(가장 높은 버전, 자동 호출만), 답을 남길 수 없는 폴더, 답을 받기 전의 엔진 목록
    w = World(tmp, "choose", db, sched)
    write_recipe(os.path.join(w.eng, "beta", "v2"), provider="openai", model="model-o2", request={"max_output_tokens": 9000})
    quiet(R.main, ["register", "--name", "beta", "--label", "베타", "--version", "2", "--no-ots"] + w.common)
    write_recipe(os.path.join(w.eng, "delta", "v1"))
    quiet(E.main, ["register", "--name", "delta", "--version", "1", "--model", "m", "--mode", "manual", "--dir", os.path.join(w.eng, "delta", "v1"), "--no-ots"] + w.common[2:])
    check("엔진 고르기: 이름마다 가장 높은 버전, 손으로 넣는 엔진은 빼고", R.choose_tags(w.ledger(), w.prv) == ["alpha@1", "beta@2"], R.choose_tags(w.ledger(), w.prv))
    os.makedirs(w.work)
    with open(os.path.join(w.work, "plan.json"), "w", encoding="utf-8") as f:
        f.write("{쓰다 만")
    with open(os.path.join(w.work, "beta@2"), "w", encoding="utf-8") as f:
        f.write("폴더가 있어야 할 자리에 놓인 파일")
    w.api.plan = {"anthropic": good("anthropic", CPI, A_VALS), "openai": good("openai", CPI, O_VALS)}
    res = w.go()
    check("실행: 답을 남길 수 없는 엔진은 부르지 않음(받은 답을 버리고 다시 받지 않게)", res["engines"] == {"alpha@1": "sealed", "beta@2": "pending"} and res["ok"] is False
          and w.api.calls == {"anthropic": 5, "openai": 0} and "쓸 수 없음" in said(res), (res, w.api.calls))
    os.remove(os.path.join(w.work, "beta@2"))
    res = w.go(T0 + timedelta(minutes=20))
    check("실행: 길이 열리면 이어서 받아 봉인(엔진 목록은 첫 답을 받을 때 정한 대로)", res["state"] == "sealed" and w.ledger()[-1]["engines"] == ["beta@2", "prev"]
          and w.api.bodies[-1][2]["model"] == "model-o2", (res, w.ledger()[-1]))
    with open(os.path.join(w.work, "forecast_x.json"), "w", encoding="utf-8") as f:
        f.write("{}")
    code, out = quiet(R.S.main, ["--file", os.path.join(w.work, "forecast_x.json"), "--min-lead-hours", "1", "--no-ots"] + w.common[2:])
    check("봉인 명령: 마감을 12시간보다 늦추는 선택은 거부", code == 2 and "늦출 수 없습니다" in out, out)

    # --- 9. 한 엔진이 늦어도 다른 엔진이 밀리지 않는다 / 두 엔진이 함께 끝나면 한 건으로 봉인
    w = World(tmp, "slow", db, sched)
    beta_done, seen = threading.Event(), []
    w.api.plan = {"anthropic": good("anthropic", CPI, A_VALS), "openai": good("openai", CPI, O_VALS)}
    plain = w.api.send

    def slow_alpha(url, headers, body, timeout):
        if "anthropic.com" in url:
            seen.append(beta_done.wait(5))   # 다른 엔진이 다 끝날 때까지 기다린다(밀려 있다면 끝내 오지 않는다)
        out = plain(url, headers, body, timeout)
        if w.api.calls["openai"] >= 5:
            beta_done.set()
        return out

    w.api.send = slow_alpha
    res = w.go(parallel=1)
    check("실행: 엔진마다 따로 불러 한 엔진이 늦어도 다른 엔진이 먼저 끝남", seen and all(seen) and res["state"] == "sealed"
          and w.ledger()[-1]["engines"] == ["alpha@1", "beta@1", "prev"], (seen, res))

    # --- 10. 외부 타임스탬프를 받지 못했으면 다음 실행에서 다시 받는다
    w = World(tmp, "stamp", db, sched)
    w.api.plan = {"anthropic": good("anthropic", CPI, A_VALS), "openai": good("openai", CPI, O_VALS)}
    stamp_file = ledger_commit.ots.stamp_file
    try:
        ledger_commit.ots.stamp_file = lambda path, timeout=15: (False, "캘린더에 닿지 못함")
        res = w.go(no_ots=False)
        first = (res["state"], res["stamped"])
        res = w.go(T0 + timedelta(minutes=20), no_ots=False)
        second = (res["state"], res["stamped"])
        ledger_commit.ots.stamp_file = lambda path, timeout=15: (True, "시험용 캘린더")
        res = w.go(T0 + timedelta(minutes=40), no_ots=False)
    finally:
        ledger_commit.ots.stamp_file = stamp_file
    check("실행: 타임스탬프를 받았는지 알려 주고, 못 받았으면 다시 돌릴 때 다시 받음", first == ("sealed", False) and second == ("already", False)
          and (res["state"], res["stamped"]) == ("already", True) and "타임스탬프 받음" in said(res), (first, second, res))
    w = World(tmp, "stamp2", db, sched)
    w.api.plan = {"anthropic": good("anthropic", CPI, A_VALS), "openai": good("openai", CPI, O_VALS)}
    try:
        ledger_commit.ots.stamp_file = lambda path, timeout=15: (True, "시험용 캘린더")
        res = w.go(no_ots=False)
    finally:
        ledger_commit.ots.stamp_file = stamp_file
    check("실행: 봉인하면서 타임스탬프를 받으면 받았다고 알림", (res["state"], res["stamped"]) == ("sealed", True), res)

    # --- 11. 무엇이 놓여 있어도 예외를 내지 않는다
    w = World(tmp, "crash", db, sched)
    w.api.plan = {"anthropic": good("anthropic", CPI, A_VALS), "openai": good("openai", CPI, O_VALS)}
    load_engine = R.load_engine
    R.load_engine = lambda *a: 1 / 0
    try:
        res = w.go()
    finally:
        R.load_engine = load_engine
    check("실행: 실행기 안에서 난 오류는 종류와 자리만 알리고 멈추지 않음", res["state"] == "blocked" and res["ok"] is False and "ZeroDivisionError" in res["result"]
          and sum(w.api.calls.values()) == 0, res)
    with open(os.path.join(w.led, "ledger.jsonl"), "a", encoding="utf-8") as f:
        f.write('{"seq": 99, "쓰다 만 줄')
    res = w.go()
    check("실행: 장부의 마지막 줄이 쓰다 만 줄이어도 멈추지 않고 알림", res["state"] == "blocked" and sum(w.api.calls.values()) == 0, res)
    bad_sched = os.path.join(tmp, "schedule_bad.csv")
    with open(bad_sched, "w", encoding="utf-8") as f:
        f.write("event_kind,title_ko,ref_period,release_at_utc,targets\nCPI,소비자물가,2099-01,2099-13-41T25:00:00Z,CPI_MOM\n")
    w = World(tmp, "badtime", db, sched)
    res = w.go(schedule=bad_sched)
    check("실행: 일정표의 발표 시각이 틀려도 멈추지 않고 알림", res["state"] == "blocked" and "일정표" in res["result"], res)

    # --- 7. 미리 보기와 probe: 저장하지 않고 값도 글도 찍지 않는다
    w = World(tmp, "preview", db, sched)
    w.api.plan = {"anthropic": good("anthropic", CPI, (0.37,)), "openai": [(200, openai_doc("직전보다 낮은 0.57 로 봅니다 {", "incomplete", "max_output_tokens"), ("", ""))]}
    write_recipe(os.path.join(w.eng, "gamma", "v1"), model="model-g")   # 등록 전 레시피도 미리 볼 수 있다
    files_before = sorted(os.path.join(b, n) for b, _, names in os.walk(tmp) for n in names)
    argv = ["preview", "--event", "CPI", "--ref", "2099-01", "--db", db, "--schedule", sched] + w.common
    code, out = quiet(lambda: R.cmd_preview(R.parse_args(argv), send=w.api.send, env=ENV))
    files_after = sorted(os.path.join(b, n) for b, _, names in os.walk(tmp) for n in names)
    check("미리 보기: 엔진마다 한 번, 등록 전 레시피도, 형식만 알려 줌", code == 1 and w.api.calls == {"anthropic": 2, "openai": 1} and out.count("형식 맞음") == 2
          and "형식이 틀림" in out and "max_output_tokens" in out and "중괄호 있음" in out, out)
    check("미리 보기: 답의 값도 글도 찍지 않고 아무것도 저장하지 않음", "0.37" not in out and "0.57" not in out and "낮은" not in out and "SECRET" not in out
          and files_before == files_after, out)
    asked = []

    def counter(url, headers, body, timeout):   # 토큰을 세어 주는 주소만 흉내 낸다. 한 회사는 세어 주고 한 회사는 실패한다
        asked.append(url)
        return (200, {"input_tokens": 5000}, ("", ""), None) if "count_tokens" in url else (404, None, ("not_found", ""), None)

    argv = ["estimate", "--event", "CPI", "--ref", "2099-01", "--db", db, "--schedule", sched] + w.common
    code, out = quiet(lambda: R.cmd_estimate(R.parse_args(argv), send=counter, env=ENV))
    check("명령 estimate: 엔진을 부르지 않고 입력은 세어서, 출력은 레시피의 상한으로", code == 0 and w.api.calls == {"anthropic": 2, "openai": 1}
          and all(u.endswith(("/count_tokens", "/input_tokens")) for u in asked) and "입력 5000토큰(API가 센 값)" in out and "글자 수로 넉넉하게" in out
          and "5번 불러 최대 45000토큰" in out and "최악은 10번, 90000토큰" in out, out)
    b = R.usage_bounds(dict(RECIPE, model="claude-fable-5-1", request={"max_tokens": 16000}), 6000)
    check("토큰 상한 계산: 한 번·발표 한 번·최악, 요금 어림", (b["per_call"], b["event"], b["worst"]) == (22000, 110000, 220000)
          and [round(b[k], 2) for k in ("usd_event", "usd_worst", "usd_half")] == [4.3, 8.6, 2.3], b)
    code, out = quiet(lambda: R.cmd_probe(R.parse_args(["probe"] + w.common), send=w.api.send, env=ENV))
    check("명령 probe: 레시피의 모델을 한 번씩", code == 0 and out.count("닿음") == 3 and "0.37" not in out and "낮은" not in out, out)


def run_checks(check):
    with tempfile.TemporaryDirectory() as tmp:
        unit_checks(check, tmp)
        db = os.path.join(tmp, "t.db")
        con = store.connect(db)
        parsed, _ = bls.parse(collect_selftest.fake_response())
        bls.ingest(con, parsed, "2020-01-01T00:00:00Z", None)
        con.commit()
        con.close()
        sched = os.path.join(tmp, "schedule_test.csv")
        with open(sched, "w", encoding="utf-8", newline="") as f:
            f.write("event_kind,title_ko,ref_period,release_at_utc,targets\n")
            f.write("CPI,소비자물가,2099-01,2099-02-11T13:30:00Z,CPI_MOM CPI_CORE_MOM CPI_YOY\n")
        flow_checks(check, tmp, db, sched)
