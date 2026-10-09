"""엔진 실행기: 사실 묶음을 엔진(모델 API)에 주고, 여러 번 받은 답을 합쳐 예측 파일을 만들고, 봉인한다 (docs/12 §4~§7).

    python -m pipeline.forecast.runner check                              레시피 폴더 검사 (호출 없음)
    python -m pipeline.forecast.runner probe                              레시피의 모델을 짧게 한 번씩 불러 본다 (키·모델·잔액 확인. 레시피의 요청 항목은 보내지 않는다)
    python -m pipeline.forecast.runner render --event CPI --ref 2026-09   엔진에 줄 사실 표를 화면에 (호출 없음)
    python -m pipeline.forecast.runner estimate --event CPI --ref 2026-09 쓸 토큰과 요금의 상한: 보낼 글의 토큰 수(API가 세어 준다. 무료)와 레시피의 출력 상한으로 계산. 엔진은 부르지 않는다
    python -m pipeline.forecast.runner preview --event CPI --ref 2026-09  미리 보기: 엔진마다 한 번 불러 형식만 본다. 답은 저장도 표시도 하지 않는다
    python -m pipeline.forecast.runner register --name adler --label 아들러 --version 1   레시피의 모델·횟수 그대로 장부에 등록
    python -m pipeline.forecast.runner run --event CPI --ref 2026-09      실제 실행: 묶음 → 엔진 호출 → 합치기 → 봉인

레시피 폴더 (data/private/engines/<이름>/v<버전>/ — 저장소에 올리지 않는다. 등록하면 폴더 전체의 해시가 장부에 남는다)
    recipe.json   설정. 아래 항목을 모두 적는다(기본값 없음 — 레시피가 그대로면 실행 조건도 그대로여야 한다)
        {"format": "recipe/1", "provider": "anthropic" 또는 "openai", "model": "<모델 ID>",
         "n_runs": 5, "min_valid_runs": 3, "max_attempts": 2, "timeout_sec": 300,
         "render": "table/1", "answer": "json/1", "aggregate": "median",
         "request": {<그 회사 API의 요청 항목. anthropic: max_tokens(필수)·thinking·output_config 등 / openai: max_output_tokens(필수)·reasoning 등>}}
    prompt.md     사용자 메시지 틀. {{FACTS}} 자리에 사실 표, {{ANSWER_FORMAT}} 자리에 답 형식이 들어간다
    system.md     시스템 지시문 (없어도 된다)

규칙 (코드가 지키는 것)
- 엔진이 낸 값과 답의 글은 화면·로그·조종판 어디에도 찍지 않는다(D20). 서버의 data/private/ 에만 남는다. 찍는 것은 건수·해시·토큰 수·상태뿐이다.
- 웹 검색과 도구를 켤 수 없다. 레시피의 request 에는 정해 둔 항목만 넣을 수 있다 (docs/12 §5).
- 사실 표를 그리는 방식(render)·답 형식(answer)·합치는 방식(aggregate)은 이름과 번호로 고정한다. 고치려면 새 번호를 더하고
  옛 것은 그대로 둔다(자체 시험이 옛 것을 지킨다). 그래야 "레시피가 그대로면 엔진이 본 것도 그대로"가 된다.
- 한 번(run)의 답은 형식이 맞으면 그대로 확정이다. 다시 부르지 않는다. 형식이 틀린 답만 max_attempts 까지 다시 받는다.
  API·통신 오류는 답이 아니므로 세지 않는다 — 마감 전까지 실행할 때마다 다시 부른다. 중간에 멈춰도 받은 답은 남는다.
- 형식이 맞는 답이 min_valid_runs 에 못 미친 엔진은 그 발표를 내지 않는다("미제출"). 못 미칠 것이 확실해지면 더 부르지 않는다.
- 답이 다 모인 엔진은 다른 엔진을 기다리지 않고 바로 봉인한다. 늦게 모인 엔진은 같은 묶음·같은 기준선으로 한 건 더 봉인한다.
- 등록 뒤 레시피 폴더가 바뀐 엔진은 부르지 않는다(다른 엔진은 그대로 간다).
- 봉인 마감(발표 12시간 전)을 바꾸는 길이 없고, 사람이 값을 고치는 길도 없다. 합친 값은 발표 자릿수보다 한 자리 더 잘게 반올림할 뿐이다.
- 발표 하나는 한 번에 한 실행만 다룬다(작업 폴더 잠금). 겹쳐 돌면 뒤의 것은 아무것도 하지 않는다.
- 쓰는 토큰에는 상한이 있다: 한 번 부를 때 입력은 보낸 글 그대로, 출력은 레시피의 상한(max_tokens / max_output_tokens)까지.
  발표 한 번에 엔진 하나가 받는 답은 많아야 n_runs × max_attempts 개다. estimate 가 이 상한을 토큰과 요금으로 보여 준다.

작업 폴더 (data/private/forecast/runs/<발표>_<기간>/)
    plan.json                      이 발표에 쓰기로 한 엔진·버전. 처음 정한 대로 끝까지 간다
    bundle.json                    사실 묶음. 첫 답을 받은 뒤로는 바꾸지 않는다
    <엔진@버전>/runNN_ansMM.json   받은 답 하나(형식이 맞은 것과 틀린 것). errors.jsonl 은 답이 오지 않은 호출의 기록
    forecast_*.json                봉인에 넣은 예측 파일
"""
import argparse
import concurrent.futures
import contextlib
import hashlib
import http.client
import io
import json
import math
import os
import re
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, localcontext

from ..collect import env as envmod
from ..collect import store
from ..ledger import commit as ledger_commit
from ..ledger import core
from ..ledger.commit import ROOT, read_private, setup_console
from . import bundle as B
from . import engine as E
from . import seal as S
from . import targets as T

RUNNER = "runner/0.1"
RECIPE_FORMAT = "recipe/1"
UTC_FMT = "%Y-%m-%dT%H:%M:%SZ"
RECIPE_KEYS = ("format", "provider", "model", "n_runs", "min_valid_runs", "max_attempts", "timeout_sec", "render", "answer", "aggregate", "request")
# 레시피의 request 에 넣을 수 있는 항목(회사별). 여기 없는 것은 받지 않는다 — 모델·본문은 실행기가 채우고,
# 도구·검색·이어 붙이기는 켤 수 없어야 "같은 자료만 본다"가 지켜진다. 새 항목이 필요하면 여기에 더한다(코드로 남는다)
ALLOWED_REQUEST = {"anthropic": ("max_tokens", "thinking", "output_config", "temperature", "top_p", "top_k", "stop_sequences", "service_tier"),
                   "openai": ("max_output_tokens", "reasoning", "text", "temperature", "top_p", "service_tier")}
KEY_NAME = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}
CAP_NAME = {"anthropic": "max_tokens", "openai": "max_output_tokens"}   # 한 번 부를 때 나오는 토큰(생각 포함)의 상한. 레시피에 반드시 적는다
# 100만 토큰당 달러 (입력, 출력). estimate 의 어림에만 쓴다. 2026-10-09 요금표 기준 — Astra 는 공식 요금표에서 확인하지 못한 값이다(docs/12 §7)
PRICES = {"claude-fable-5-1": (10.0, 50.0), "claude-opus-5-5": (4.0, 20.0), "gpt-6-astra": (10.0, 50.0)}
MIN_LEAD_H = 12.0        # 봉인 마감: 발표 몇 시간 전까지. 실행기에는 이 값을 바꾸는 선택 항목이 없다 (docs/12 §6)
FINAL_MARGIN_H = 1.0     # 마감이 이만큼 남으면 더 부르지 않고, 받은 답이 min_valid_runs 를 넘는 엔진은 그것으로 마무리한다
ERRORS_PER_RUN = 2       # 한 번의 실행에서 한 번(run)이 겪어도 되는 오류 수. 넘으면 다음 실행으로 미룬다
RETRY_WAIT = 5           # 오류 뒤 다시 부르기 전에 기다리는 초(상대가 알려 준 시간이 있으면 그 시간, 최대 60초)
SEAL_RESERVE_SEC = 300   # 봉인 마감 이만큼 전에는 끝나 있도록, 그 안에 끝나지 못할 호출은 시작하지 않는다
VALUE_LIMIT = 1e12       # 크기가 이 이상인 숫자는 답으로 치지 않는다(형식 오류)
PARSE_TAIL = 20000       # 답의 끝에서 이만큼만 읽는다(답은 맨 끝에 있고, 아주 긴 글을 훑느라 멈추지 않게)


def utc_text(now):
    return now.strftime(UTC_FMT)


def write_json(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, path)


# --- 레시피

def load_recipe(folder):
    """(레시피 dict 또는 None, 문제 목록). 레시피 dict 에는 system·prompt 글과 폴더가 함께 들어 있다."""
    problems = []
    path = os.path.join(folder, "recipe.json")
    if not os.path.isfile(path):
        return None, ["recipe.json 이 없음: %s" % folder]
    try:
        with open(path, encoding="utf-8-sig") as f:
            r = json.load(f)
    except (ValueError, OSError) as e:
        return None, ["recipe.json 을 읽지 못함: %s" % str(e)[:120]]
    if not isinstance(r, dict):
        return None, ["recipe.json 의 맨 바깥은 { } 여야 함"]
    for k in RECIPE_KEYS:
        if k not in r:
            problems.append("recipe.json 에 %s 가 없음 (모든 항목을 적습니다)" % k)
    for k in sorted(set(r) - set(RECIPE_KEYS)):
        problems.append("recipe.json 에 모르는 항목: %s" % k)
    if problems:
        return None, problems

    def named(name, table):
        if not (isinstance(r[name], str) and r[name] in table):
            problems.append("%s 는 %s 가운데 하나" % (name, " / ".join(sorted(table))))
            return False
        return True

    def whole(name, lo, hi):
        v = r[name]
        if isinstance(v, bool) or not isinstance(v, int) or not (lo <= v <= hi):
            problems.append("%s 는 %d~%d 의 정수" % (name, lo, hi))
            return False
        return True

    named("format", (RECIPE_FORMAT,))
    provider_ok = named("provider", PROVIDERS)
    named("render", RENDERERS)
    named("answer", ANSWERS)
    named("aggregate", AGGREGATORS)
    if not (isinstance(r["model"], str) and r["model"] and not re.search(r"\s", r["model"])):
        problems.append("model 은 빈칸 없는 모델 ID")
    if whole("n_runs", 1, 15) and whole("min_valid_runs", 1, 15) and r["min_valid_runs"] > r["n_runs"]:
        problems.append("min_valid_runs 가 n_runs 보다 큼")
    whole("max_attempts", 1, 4)
    whole("timeout_sec", 30, 900)
    req = r["request"]
    if not isinstance(req, dict):
        problems.append("request 는 { } (비어 있어도 됨)")
    elif provider_ok:
        allowed = ALLOWED_REQUEST[r["provider"]]
        for k in sorted(set(req) - set(allowed)):
            problems.append("request 에 넣을 수 없는 항목: %s (도구·검색은 켜지 않고, 모델·본문은 실행기가 채웁니다. 쓸 수 있는 것: %s)" % (k, ", ".join(allowed)))
        cap = req.get(CAP_NAME[r["provider"]])
        if not (isinstance(cap, int) and not isinstance(cap, bool) and 256 <= cap <= 64000):
            problems.append("request.%s 가 있어야 함(256~64000 의 정수). 한 번 부를 때 나오는 토큰의 상한이고, 생각하는 토큰도 여기에 들어갑니다" % CAP_NAME[r["provider"]])
    texts = {}
    for name, needed in (("prompt.md", True), ("system.md", False)):
        p = os.path.join(folder, name)
        if os.path.isfile(p):
            try:
                with open(p, encoding="utf-8-sig") as f:
                    texts[name] = f.read().replace("\r\n", "\n")
            except (ValueError, OSError):
                problems.append("%s 를 읽지 못함 (UTF-8 로 저장합니다)" % name)
        elif needed:
            problems.append("%s 가 없음" % name)
    prompt = texts.get("prompt.md", "")
    for mark in ("{{FACTS}}", "{{ANSWER_FORMAT}}"):
        if "prompt.md" in texts and prompt.count(mark) != 1:
            problems.append("prompt.md 에 %s 가 정확히 한 번 있어야 함" % mark)
    for name, text in texts.items():
        marks = set(re.findall(r"\{\{[^{}]*\}\}", text)) - ({"{{FACTS}}", "{{ANSWER_FORMAT}}"} if name == "prompt.md" else set())
        if marks:
            problems.append("%s 에 모르는 자리 표시: %s" % (name, ", ".join(sorted(marks))))
    if problems:
        return None, problems
    return dict(r, system=texts.get("system.md", "").strip(), prompt=prompt, folder=folder), []


def latest_folders(engines_dir):
    """엔진 폴더에서 이름마다 가장 높은 버전의 레시피 폴더: [(이름, 버전, 폴더)]. 버전 폴더는 v<숫자> 만 본다."""
    out = []
    for name in sorted(os.listdir(engines_dir)) if os.path.isdir(engines_dir) else []:
        base = os.path.join(engines_dir, name)
        vers = [int(v[1:]) for v in (os.listdir(base) if os.path.isdir(base) else []) if re.match(r"^v[1-9]\d{0,3}$", v) and os.path.isdir(os.path.join(base, v))]
        if vers:
            out.append((name, str(max(vers)), os.path.join(base, "v%d" % max(vers))))
    return out


# --- 사실 표 (render). 묶음(JSON)을 엔진이 읽을 글로 바꾼다. 묶음만 보고 그린다 — 같은 묶음이면 항상 같은 글이 나온다

def _num(v):
    return "–" if v is None else repr(v)


def _series_table(blocks):
    periods = sorted({v["period"] for b in blocks for v in b["values"]})
    lines = ["계열 | 이름 | 값의 뜻 | " + " | ".join(periods)]
    for b in blocks:
        got = {v["period"]: v["value"] for v in b["values"]}
        lines.append(" | ".join([b["series"], b["name"], b["measure"]] + [_num(got.get(p)) for p in periods]))
    return lines


def render_table_1(bundle):
    ev = bundle["event"]
    out = ["[발표] %s (%s) · 기준 기간 %s · 발표 시각(UTC) %s" % (ev["title"], ev["kind"], ev["ref_period"], ev.get("release_at_utc") or "미정"),
           "[자료 마감(UTC)] %s — 이 시각까지 발표된 값만 있습니다. 기준 기간(%s)의 값은 없습니다." % (bundle["data_cutoff_utc"], ev["ref_period"]),
           "", "## 맞힐 값", "id | 이름 | 단위 | 발표 자릿수 | 직전 발표값(기간)"]
    for t in bundle["targets"]:
        prev = t["prev"]
        out.append("%s | %s | %s | 소수 %d자리 | %s (%s)%s" % (t["target"], t["name"], t["unit"], t["decimals"], _num(prev["value"]), prev["period"],
                                                             " — " + prev["note"] if prev.get("note") else ""))
    ids = [t["target"] for t in bundle["targets"]]
    hist = {t: {h["period"]: h["value"] for h in bundle["history"].get(t, [])} for t in ids}
    fine = {t: {h["period"]: h["value"] for h in rows} for t, rows in (bundle.get("history_fine") or {}).items() if t in ids and rows}
    cols = [(t, hist[t]) for t in ids] + [(t + " 계산값", fine[t]) for t in ids if t in fine]
    periods = sorted({p for _, got in cols for p in got})
    out += ["", "## 맞힐 값의 과거 (오래된 기간부터)" + (". '계산값'은 발표된 지수로 같은 식을 다시 계산한 소수 둘째 자리 값" if fine else ""),
            "기간 | " + " | ".join(name for name, _ in cols)]
    out += ["%s | %s" % (p, " | ".join(_num(got.get(p)) for _, got in cols)) for p in periods]
    if bundle.get("components"):
        out += ["", "## 같은 발표의 구성 항목"] + _series_table(bundle["components"])
    for group in sorted(bundle.get("related") or {}):
        if bundle["related"][group]:
            out += ["", "## 이미 나온 다른 발표 (%s)" % group] + _series_table(bundle["related"][group])
    yoy = bundle.get("yoy_ingredients") or {}
    if yoy:
        out += ["", "## 전년비를 따질 재료 (원계열 지수)"]
        for sid in sorted(yoy):
            y = yoy[sid]
            same = ", ".join("%s %s" % (v["period"], _num(v["value"])) for v in y["nsa_mom_same_month_past_years"])
            out.append("%s | 직전 달 지수(%s) %s | 기준 기간의 열두 달 전 지수(%s) %s | 같은 달의 과거 원계열 전월비 %%: %s"
                       % (sid, y["index_prev_month"]["period"], _num(y["index_prev_month"]["value"]),
                          y["index_same_month_last_year"]["period"], _num(y["index_same_month_last_year"]["value"]), same or "없음"))
    out += ["", "## 알아 둘 것"] + ["- " + n for n in bundle.get("notes") or []] + ["- 표의 – 는 그 기간의 값이 없다는 뜻입니다."]
    return "\n".join(out) + "\n"


RENDERERS = {"table/1": render_table_1}


# --- 답 형식 (answer)

def answer_text_json_1(bundle):
    ids = [t["target"] for t in bundle["targets"]]
    shape = ", ".join('"%s": {"p10": <숫자>, "p50": <숫자>, "p90": <숫자>}' % t for t in ids)
    return "\n".join([
        "답의 맨 끝에 아래 모양의 JSON 객체 하나를 적습니다. JSON 뒤에는 아무것도 적지 않습니다.",
        '{"forecasts": {%s}}' % shape,
        "- p50 은 발표될 값의 가운데 추정(중앙값)입니다. p10 은 발표값이 그보다 낮을 확률이 10%인 값, p90 은 그보다 높을 확률이 10%인 값입니다.",
        "  그래서 발표값이 p10~p90 안에 들어올 확률이 80%가 되어야 합니다. p10 ≤ p50 ≤ p90.",
        "- '맞힐 값' 표의 직전 발표값과 같은 단위로 숫자만 적습니다(기호·단위·따옴표 없이. 퍼센트는 퍼센트 값 그대로).",
        "- 발표 자릿수보다 한 자리까지만 더 잘게 적습니다.",
        "- 위 %d개 id 를 빠짐없이 적습니다." % len(ids)])


def _is_num(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return False
    if isinstance(v, int):
        return abs(v) < 10 ** 12   # 아주 큰 정수는 실수로 바꾸는 것부터 실패한다. 먼저 거른다
    return math.isfinite(v) and abs(v) < VALUE_LIMIT


def parse_json_1(text, ids):
    """(지표 -> {p10,p50,p90} 또는 None, 형식이 틀린 이유). 이유에는 값을 적지 않는다.

    답은 글의 끝에 있어야 한다: 글의 마지막 } 로 끝나고 맨 바깥에 forecasts 가 든 JSON 객체 하나. 그 앞에 적은 초안이나
    그 객체 안쪽에 든 다른 forecasts 는 보지 않는다. 끝의 객체가 읽히지 않으면 앞의 것을 대신 쓰지 않고 틀린 답으로 친다."""
    text = text[-PARSE_TAIL:]
    found, dec, at, last = None, json.JSONDecoder(), text.find("{"), text.rfind("}")
    while at != -1:
        try:
            obj, end = dec.raw_decode(text, at)
        except (ValueError, RecursionError):
            at = text.find("{", at + 1)
            continue
        if isinstance(obj, dict) and "forecasts" in obj and end == last + 1:
            found = obj
        at = text.find("{", end)
    if found is None:
        return None, "답의 끝에서 forecasts 가 든 JSON 을 찾지 못함"
    fc = found["forecasts"]
    if not isinstance(fc, dict):
        return None, "forecasts 가 { } 가 아님"
    out = {}
    for t in ids:
        v = fc.get(t)
        if not isinstance(v, dict):
            return None, "%s 가 빠짐" % t
        if not all(_is_num(v.get(k)) for k in ("p10", "p50", "p90")):
            return None, "%s 의 p10·p50·p90 이 숫자가 아니거나 너무 큼" % t
        if not (v["p10"] <= v["p50"] <= v["p90"]):
            return None, "%s 가 p10 <= p50 <= p90 이 아님" % t
        out[t] = {k: float(v[k]) for k in ("p10", "p50", "p90")}
    return out, ""


ANSWERS = {"json/1": (answer_text_json_1, parse_json_1)}


# --- 합치기 (aggregate)

def aggregate_median(runs, places):
    """여러 번의 답을 지표 하나의 범위로: 자리마다(p10·p50·p90) 가운데 값. 짝수 번이면 가운데 두 값의 평균.

    봉인 규칙에 맞춰 발표 자릿수보다 한 자리 더 잘게 반올림한다(사사오입). 계산은 십진수로 한다 — 공개된 번별 답으로 누구나 같은 값을 얻는다."""
    out = {}
    with localcontext() as ctx:
        ctx.prec = 60
        step = Decimal(1).scaleb(-(places + 1))
        for k in ("p10", "p50", "p90"):
            xs = sorted(Decimal(repr(float(r[k]))) for r in runs)
            n = len(xs)
            mid = xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2
            out[k] = float(mid.quantize(step, rounding=ROUND_HALF_UP)) + 0.0
    return out


AGGREGATORS = {"median": aggregate_median}


def build_prompt(recipe, bundle):
    """(시스템 지시문, 사용자 메시지, 둘의 해시). 엔진이 실제로 받는 글이다."""
    facts = RENDERERS[recipe["render"]](bundle)
    user = recipe["prompt"].replace("{{FACTS}}", facts).replace("{{ANSWER_FORMAT}}", ANSWERS[recipe["answer"]][0](bundle))
    digest = hashlib.sha256((recipe["system"] + "\n\x00\n" + user).encode("utf-8")).hexdigest()
    return recipe["system"], user, digest


# --- 두 회사 API. 요청을 만들고 응답에서 글·끝난 이유·토큰 수만 꺼낸다. 응답의 모양이 어긋나도 멈추지 않는다

def _count(v):
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def _part(doc, key, kind):
    v = doc.get(key)
    return v if isinstance(v, kind) else kind()


def _label(v, limit=60):
    """끝난 이유·상태·모델 이름처럼 로그에 적는 표지. 정해진 글자로 된 짧은 말만 그대로 적는다(답의 글이 섞여 들어올 길을 막는다)."""
    v = str(v)
    return v if re.match(r"^[A-Za-z0-9_.:/\-]{1,%d}$" % limit, v) else "(알 수 없음)"


def _anthropic_request(key, recipe, system, user):
    body = {"model": recipe["model"], "messages": [{"role": "user", "content": user}]}
    if system:
        body["system"] = system
    body.update(recipe["request"])
    return "https://api.anthropic.com/v1/messages", {"x-api-key": key, "anthropic-version": "2023-06-01"}, body


def _anthropic_read(doc):
    text = "".join(b["text"] for b in _part(doc, "content", list) if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str))
    u, stop = _part(doc, "usage", dict), _label(doc.get("stop_reason"))
    return {"text": text, "stop": stop, "done": stop in ("end_turn", "stop_sequence"), "failed": "", "model": _label(doc.get("model"), 80),
            "tokens_in": _count(u.get("input_tokens")), "tokens_out": _count(u.get("output_tokens"))}


def _openai_request(key, recipe, system, user):
    body = {"model": recipe["model"], "input": [{"role": "user", "content": user}], "store": False}
    if system:
        body["instructions"] = system
    body.update(recipe["request"])
    return "https://api.openai.com/v1/responses", {"Authorization": "Bearer " + key}, body


def _openai_read(doc):
    parts = [c["text"] for item in _part(doc, "output", list) if isinstance(item, dict) and item.get("type") == "message"
             for c in _part(item, "content", list) if isinstance(c, dict) and c.get("type") == "output_text" and isinstance(c.get("text"), str)]
    u, status = _part(doc, "usage", dict), _label(doc.get("status"), 40)
    why = _part(doc, "incomplete_details", dict).get("reason")
    failed = "" if status in ("completed", "incomplete") else "응답 상태 %s (%s)" % (status, _label(_part(doc, "error", dict).get("code")))
    return {"text": "".join(parts), "stop": "%s%s" % (status, ":" + _label(why) if why else ""), "done": status == "completed", "failed": failed,
            "model": _label(doc.get("model"), 80), "tokens_in": _count(u.get("input_tokens")), "tokens_out": _count(u.get("output_tokens"))}


PROVIDERS = {"anthropic": (_anthropic_request, _anthropic_read), "openai": (_openai_request, _openai_read)}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None   # 키가 든 요청을 다른 주소로 다시 보내지 않는다(넘기라는 응답은 오류로 돌아온다)


_OPENER = urllib.request.build_opener(_NoRedirect)


def http_send(url, headers, body, timeout, urlopen=_OPENER.open):
    """(HTTP 상태 — 닿지 못하면 0, 응답 JSON 또는 None, (오류 종류, 오류 설명), 다시 부르라는 초 또는 None)"""
    try:
        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST",
                                     headers=dict(headers, **{"Content-Type": "application/json", "User-Agent": "checksumlab-engine/0.1"}))
        with urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8")), ("", ""), None
    except urllib.error.HTTPError as e:
        kind, msg, after = "", "", None
        try:
            err = json.loads(e.read().decode("utf-8", "replace")).get("error") or {}
            kind, msg = _label(err.get("type") or err.get("code") or "-"), str(err.get("message") or "")[:2000]
        except Exception:   # 오류 본문을 읽지 못해도 상태 코드로 판단한다
            pass
        try:
            after = float(e.headers.get("retry-after"))
            after = after if math.isfinite(after) and after >= 0 else None
        except (TypeError, ValueError, AttributeError):
            after = None
        return e.code, None, (kind, msg), after
    except (urllib.error.URLError, OSError, http.client.HTTPException) as e:
        return 0, None, (type(e).__name__, str(getattr(e, "reason", ""))[:120]), None
    except Exception as e:   # 요청을 만들다 난 오류의 글에는 헤더(키)가 섞일 수 있다. 종류만 남긴다
        return 0, None, (type(e).__name__, ""), None


def scrub(text, keys=()):
    """오류 글에서 키를 가린다: 넘겨받은 키 값과, 키처럼 생긴 글(sk-…)."""
    for k in keys:
        if k:
            text = text.replace(k, "(가림)")
    return re.sub(r"sk-[A-Za-z0-9_*.…\-]{4,}", "(가림)", text)


def call_once(recipe, system, user, ids, key, timeout, send=http_send, clock=time.monotonic):
    """엔진을 한 번 부른다. 어떤 경우에도 예외를 내지 않고 기록 하나를 돌려준다.

    status: ok(형식이 맞는 답) / invalid(답은 왔지만 쓸 수 없음 — 다시 받는 횟수에 들어간다) / error(답이 오지 않음 — 세지 않는다)"""
    t0, arrived = clock(), False
    try:
        make, read = PROVIDERS[recipe["provider"]]
        url, headers, body = make(key, recipe, system, user)
        status, doc, (kind, msg), after = send(url, headers, body, timeout)
        rec = {"http": status, "seconds": round(clock() - t0, 1)}
        if status != 200 or not isinstance(doc, dict):
            fatal = 400 <= status < 500 and status not in (408, 409, 425, 429)
            if status in (401, 403):   # 이 오류의 설명에는 키의 일부가 적혀 오기도 한다. 종류만 남긴다
                why = "HTTP %d · 키가 틀리거나 권한이 없음 (%s)" % (status, kind)
            else:
                why = ("HTTP %d · " % status if status else "") + (" ".join(str(x) for x in (kind, msg) if x) or "응답을 읽지 못함")
            after = after if _is_num(after) and after >= 0 else None
            return dict(rec, status="error", fatal=fatal, retry_after=after, reason=scrub(why, [key])[:300])
        arrived = True
        got = read(doc)
        if got["failed"]:
            return dict(rec, status="error", fatal=False, retry_after=None, reason=got["failed"])
        rec.update({k: got[k] for k in ("stop", "model", "tokens_in", "tokens_out")}, text=got["text"])
        if not got["done"]:
            return dict(rec, status="invalid", reason="답이 끝나지 않음 (%s)" % got["stop"])
        values, why = ANSWERS[recipe["answer"]][1](got["text"], ids)
        if values is None:
            return dict(rec, status="invalid", reason=why)
        return dict(rec, status="ok", reason="", values=values)
    except Exception as e:
        rec = {"http": 200 if arrived else 0, "seconds": round(clock() - t0, 1)}
        if arrived:   # 응답은 왔다. 읽지 못했어도 답 한 번으로 센다(모르는 채 다시 받지 않는다)
            return dict(rec, status="invalid", reason="응답을 읽다가 오류 (%s)" % type(e).__name__)
        return dict(rec, status="error", fatal=False, retry_after=None, reason="호출 중 오류 (%s)" % type(e).__name__)


# --- 작업 폴더: 받은 답은 파일 하나씩. 한 발표는 한 번에 한 실행만 다룬다

ANSWER_RE = re.compile(r"^run(\d{1,3})_ans(\d{1,3})\.json$")


@contextlib.contextmanager
def work_lock(workdir):
    """작업 폴더를 잡는다. 다른 실행이 잡고 있으면 False 를 준다. (Windows 에는 이 잠금이 없다 — 실제 실행은 서버에서만 한다)"""
    os.makedirs(workdir, exist_ok=True)
    f = open(os.path.join(workdir, ".lock"), "a+")
    try:
        held = True
        try:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except ImportError:
            pass
        except OSError:
            held = False
        yield held
    finally:
        f.close()


def read_json(path):
    """파일을 JSON 으로 읽는다. 읽지 못하면 None (어떤 파일이 놓여 있어도 멈추지 않는다)."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def any_answers(workdir):
    """이 발표에서 답을 하나라도 받았는가(어느 엔진이든). 받은 뒤로는 엔진 목록과 사실 묶음을 바꾸지 않는다."""
    try:
        return any(ANSWER_RE.match(n) for d in os.listdir(workdir) if os.path.isdir(os.path.join(workdir, d)) for n in os.listdir(os.path.join(workdir, d)))
    except OSError:
        return False


def answers_of(workdir, tag):
    """그 엔진이 받은 답: {번: [기록, ...]}. 읽을 수 없는 파일은 틀린 답 하나로 센다(모르는 채 다시 받지 않는다)."""
    folder, out = os.path.join(workdir, tag), {}
    try:
        names = sorted(os.listdir(folder)) if os.path.isdir(folder) else []
    except OSError:
        names = []
    for name in names:
        m = ANSWER_RE.match(name)
        if not m:
            continue
        rec = read_json(os.path.join(folder, name))
        if not (isinstance(rec, dict) and rec.get("status") in ("ok", "invalid")) or (rec["status"] == "ok" and not isinstance(rec.get("values"), dict)):
            rec = {"status": "invalid", "reason": "기록 파일을 읽지 못함: %s" % name, "unreadable": True}
        out.setdefault(int(m.group(1)), []).append(dict(rec, file_no=int(m.group(2))))
    return out


def engine_progress(recipe, workdir, tag, final=False):
    """(상태, 확정된 답 {번: 기록}, 더 불러야 하는 번 목록). 상태: ready(모두 정해짐) / pending / missed(모자람)"""
    got, ok, pending = answers_of(workdir, tag), {}, []
    for k in range(1, recipe["n_runs"] + 1):
        recs = got.get(k, [])
        good = next((r for r in recs if r["status"] == "ok"), None)
        if good:
            ok[k] = good
        elif len(recs) < recipe["max_attempts"] and not final:
            pending.append(k)
    if len(ok) + len(pending) < recipe["min_valid_runs"]:
        return "missed", ok, []
    return ("pending" if pending else "ready"), ok, pending


def can_write(folder):
    try:
        os.makedirs(folder, exist_ok=True)
        probe = os.path.join(folder, ".probe")
        with open(probe, "w") as f:
            f.write("x")
        os.remove(probe)
        return True
    except OSError:
        return False


def log_error(folder, k, rec):
    try:
        with open(os.path.join(folder, "errors.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(dict(rec, run=k, at=utc_text(datetime.now(timezone.utc))), ensure_ascii=False) + "\n")
    except OSError:
        pass   # 오류 기록을 남기지 못해도 실행은 이어 간다(오류는 답이 아니다)


def work_run(eng, k, workdir, deadline, send, clock, sleep, lock, stats):
    """한 번(run)을 답이 정해질 때까지 부른다. 이번 실행에서 부를 수 있는 만큼만."""
    recipe, errors, folder = eng["recipe"], 0, os.path.join(workdir, eng["tag"])
    try:
        while not eng["stop"].is_set():
            with lock:
                state, _ok, pending = engine_progress(recipe, workdir, eng["tag"])
                recs = answers_of(workdir, eng["tag"]).get(k, [])
                writable = can_write(folder)
            if state != "pending" or k not in pending:
                return   # 답이 정해졌거나, 다시 받을 횟수를 다 썼거나, 이 엔진이 min_valid_runs 를 채울 수 없게 됐다
            if not writable:   # 답을 받아도 남길 수 없으면 부르지 않는다(받은 답을 버리고 다시 받는 일이 없게)
                eng["last_error"] = "작업 폴더에 쓸 수 없음 (%s)" % folder
                eng["stop"].set()
                return
            if deadline - clock() < recipe["timeout_sec"]:
                eng["short"] = True
                return   # 남은 시간 안에 끝난다는 보장이 없으면 부르지 않는다(받다 만 답을 만들지 않는다)
            path = os.path.join(folder, "run%02d_ans%02d.json" % (k, max([r["file_no"] for r in recs] + [0]) + 1))
            started = utc_text(datetime.now(timezone.utc))
            rec = call_once(recipe, eng["system"], eng["user"], eng["ids"], eng["key"], recipe["timeout_sec"], send, clock)
            with lock:
                stats["calls"] += 1
                stats["made"][eng["tag"]] = stats["made"].get(eng["tag"], 0) + 1
                if rec["status"] == "error":
                    stats["errors"][eng["tag"]] = stats["errors"].get(eng["tag"], 0) + 1
                    eng["last_error"] = rec["reason"]
                    log_error(folder, k, rec)
                else:
                    try:
                        write_json(path, dict(rec, engine=eng["name"], version=eng["version"], run=k, started_at=started,
                                              prompt_sha256=eng["prompt_sha256"], bundle_sha256=eng["bundle_sha256"]))
                    except OSError:   # 받은 답을 남기지 못했다. 이 엔진을 더 부르지 않는다
                        eng["last_error"] = "받은 답을 파일로 남기지 못함 (%s)" % folder
                        eng["stop"].set()
                        return
            if rec["status"] != "error":
                continue
            if rec.get("fatal"):   # 키·모델·요청 항목이 틀린 것이라 지금 다시 불러도 같다. 이번 실행에서는 이 엔진을 더 부르지 않는다
                eng["stop"].set()
                return
            errors += 1
            if errors >= ERRORS_PER_RUN:
                return   # 다음 실행이 이어서 부른다
            wait = min(rec.get("retry_after") or RETRY_WAIT, 60)
            if deadline - clock() < wait + recipe["timeout_sec"]:
                return
            sleep(wait)
    except Exception as e:   # 한 번(run)에서 난 문제가 다른 번과 다른 엔진을 멈추지 않게 한다
        eng["last_error"] = "실행기 오류 (%s)" % type(e).__name__


def work_engine(eng, pending, workdir, deadline, send, clock, sleep, lock, stats, parallel):
    """엔진 하나의 남은 번들을 부른다. 엔진마다 일꾼을 따로 둔다 — 한 엔진이 늦어도 다른 엔진이 밀리지 않는다."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=parallel) as pool:
        for f in [pool.submit(work_run, eng, k, workdir, deadline, send, clock, sleep, lock, stats) for k in pending]:
            f.result()


# --- 엔진 고르기

def choose_tags(entries, private_dir):
    """등록된 엔진마다 가장 높은 버전(숫자 버전, 자동 호출 방식만): ["adler@1", ...]"""
    best = {}
    for (name, ver), e in E.registered(entries).items():
        priv = read_private(private_dir, e)
        if not (ver.isascii() and ver.isdigit()) or (priv and priv["payload"].get("mode", "api") != "api"):
            continue
        if name not in best or int(ver) > int(best[name]):
            best[name] = ver
    return ["%s@%s" % kv for kv in sorted(best.items())]


def load_engine(tag, reg, private_dir, engines_dir):
    """(엔진 dict 또는 None, 쓸 수 없는 이유). 레시피 폴더가 등록 때 그대로인지를 먼저 본다 — 다르면 부르지 않는다."""
    name, _, ver = tag.partition("@")
    if (name, ver) not in reg:
        return None, "등록되지 않은 엔진·버전"
    folder = os.path.join(engines_dir, name, "v" + ver)
    if not os.path.isdir(folder):
        return None, "레시피 폴더가 없음 (%s)" % folder
    if E.recipe_hash(folder)[0] != reg[(name, ver)]["recipe_sha256"]:
        return None, "레시피 폴더가 등록 때와 다름. 바꿨다면 새 버전으로 등록"
    recipe, bad = load_recipe(folder)
    if bad:
        return None, "레시피 형식: " + " / ".join(bad)[:300]
    priv = read_private(private_dir, reg[(name, ver)])
    if priv:   # 등록 원문에 적힌 모델·횟수와 레시피가 같은지
        p = priv["payload"]
        if p.get("model") != recipe["model"] or p.get("n_runs") != recipe["n_runs"]:
            return None, "등록 원문의 모델·횟수가 레시피와 다름"
    return {"name": name, "version": ver, "tag": tag, "recipe": recipe, "stop": threading.Event(), "last_error": "", "key": "", "short": False}, ""


# --- 실제 실행

def default_paths(opts):
    return {"ledger": opts.get("ledger_dir") or os.path.join(ROOT, "data", "ledger", "public"),
            "private": opts.get("private_dir") or os.path.join(ROOT, "data", "private", "ledger"),
            "engines": opts.get("engines_dir") or os.path.join(ROOT, "data", "private", "engines"),
            "runs": opts.get("runs_dir") or os.path.join(ROOT, "data", "private", "forecast", "runs"),
            "schedule": opts.get("schedule") or os.path.join(ROOT, "data", "forecast", "schedule_*.csv"),
            "db": opts.get("db") or store.DEFAULT_DB}


def build_bundle_from_db(kind, ref, cutoff, release_at, opts):
    db = default_paths(opts)["db"]
    if not os.path.exists(db):
        return None, ["DB가 없습니다. 지표 수집이 먼저 돌아야 합니다"]
    con = store.connect(db)
    try:
        return B.build(con, kind, ref, cutoff, release_at)
    finally:
        con.close()


def ensure_stamp(ledger_dir, no_ots):
    """장부 마지막 기록의 봉인 파일과 외부 타임스탬프가 없으면 받는다. (받았는가 — 생략이면 None, 설명)"""
    entries = core.read_ledger(os.path.join(ledger_dir, "ledger.jsonl"))
    if not entries:
        return None, ""
    _, info = ledger_commit.seal(ledger_dir, entries[-1], not no_ots)
    return (None if no_ots else info.startswith(("타임스탬프 있음", "타임스탬프 받음"))), info


def run_event(kind, ref, opts=None, now=None, env=None, send=http_send, clock=time.monotonic, sleep=time.sleep, build=build_bundle_from_db):
    """발표 하나를 끝까지: 묶음 → 엔진 호출 → 합치기 → 봉인. 여러 번 불러도 된다(받은 답은 다시 받지 않는다).

    돌려주는 값: {"state", "ok", "result", "memo", "calls", "stamped", "engines"} — 글에는 엔진이 낸 값이 없다. 예외를 내지 않는다.
    state: sealed(이번에 봉인함) / already(앞서 봉인됨) / pending(더 해야 함 — 다시 돌리면 이어 간다) / missed(미제출) / blocked(하지 못함 — 사람이 봐야 한다)
    stamped: 외부 타임스탬프를 받았는가(True/False, 생략이면 None). False 면 다시 돌릴 때 다시 받는다
    engines: 엔진별 상태 {"adler@1": sealed / ready(답은 모였고 봉인 전) / pending / blocked(쓸 수 없음) / missed}
    opts: budget_sec(이번 실행에 쓸 시간. 0이면 봉인 마감까지), parallel(엔진마다 한꺼번에 부르는 수),
          engines(["adler@1", ...] — 첫 답을 받기 전까지만 쓰인다), no_ots, 그리고 폴더들
    """
    try:
        return _run_event(kind, ref, dict(opts or {}), now, env, send, clock, sleep, build)
    except (Exception, SystemExit) as e:   # 무엇이 놓여 있어도 일꾼을 멈추지 않는다. 오류의 글에는 값이 섞일 수 있어 종류와 자리만 남긴다
        tb = traceback.extract_tb(e.__traceback__)
        where = "%s:%d" % (os.path.basename(tb[-1].filename), tb[-1].lineno) if tb else "?"
        return {"state": "blocked", "ok": False, "result": "실행기가 멈춤 (%s, %s) · %s %s" % (type(e).__name__, where, str(kind)[:12], str(ref)[:12]),
                "memo": ["받은 답은 작업 폴더에 그대로 있습니다. 이 줄을 그대로 Claude에게 알려 주세요"], "calls": 0, "stamped": None, "engines": {}}


def _run_event(kind, ref, opts, now, env, send, clock, sleep, build):
    fixed_now = now is not None   # 시험에서만 시각을 고정한다. 실제로는 호출에 몇 분이 걸리므로 봉인할 때 시계를 다시 본다
    now = now or datetime.now(timezone.utc)
    env = envmod.load() if env is None else env
    paths = default_paths(opts)
    memo, res, states = [], {"calls": 0, "stamped": None}, {}

    def done(state, result, ok=None):
        return dict(res, state=state, ok=state in ("sealed", "already", "pending") if ok is None else ok, result=result, memo=memo, engines=states)

    def stamp():
        res["stamped"], info = ensure_stamp(paths["ledger"], opts.get("no_ots"))
        if info:
            memo.append("봉인: " + info)

    def ledger_state():
        entries = core.read_ledger(os.path.join(paths["ledger"], "ledger.jsonl"))
        sealed = {"%s@%s" % (n, v) for (n, v, _t) in S.already_sealed(entries, paths["private"], kind, ref) if n not in T.BASELINES}
        return entries, core.verify_chain(entries), sealed

    if kind not in T.EVENTS or not T.ref_period_ok(kind, ref):
        return done("blocked", "발표 종류나 기준 기간이 맞지 않음: %s %s" % (str(kind)[:12], str(ref)[:12]))
    try:
        release_at = B.lookup_release(paths["schedule"], kind, ref)
        lead = (S.parse_utc(release_at) - now).total_seconds() / 3600.0
    except Exception:
        return done("blocked", "일정표에서 이 발표의 시각을 읽지 못함: %s %s" % (kind, ref))
    entries, problems, sealed = ledger_state()
    if problems:
        memo.extend(problems[:5])
        return done("blocked", "장부에 문제가 있어 시작하지 않음")
    if lead < MIN_LEAD_H:   # 마감 뒤에는 아무것도 부르지 않고 아무것도 봉인하지 않는다
        if sealed:
            stamp()
            return done("already", "이미 봉인됨 · %s %s · %s · 봉인 마감이 지나 더 받지 않음" % (kind, ref, ", ".join(sorted(sealed))))
        return done("missed", "미제출 · %s %s · 봉인 마감(발표 %g시간 전)이 지남" % (kind, ref, MIN_LEAD_H), ok=False)

    workdir = os.path.join(paths["runs"], "%s_%s" % (kind, ref))
    with work_lock(workdir) as held:
        if not held:
            return done("pending", "다른 실행이 이 발표를 다루는 중 · %s %s" % (kind, ref))
        entries, problems, sealed = ledger_state()   # 잠금을 잡은 뒤의 장부로 본다
        if problems:
            memo.extend(problems[:5])
            return done("blocked", "장부에 문제가 있어 시작하지 않음")

        # 이 발표에 쓸 엔진과 사실 묶음: 첫 답을 받은 뒤로는 바꾸지 않는다. 그 전에는 실행할 때마다 새로 정한다
        reg, plan_path, bundle_path = E.registered(entries), os.path.join(workdir, "plan.json"), os.path.join(workdir, "bundle.json")
        asked = any_answers(workdir)
        if asked:
            plan = read_json(plan_path)
            tags = [t for t in plan["engines"] if isinstance(t, str)] if isinstance(plan, dict) and isinstance(plan.get("engines"), list) else []
            if not tags:
                return done("blocked", "받아 둔 답이 있는데 plan.json 을 읽지 못함: %s" % plan_path, ok=False)
        else:
            tags = list(dict.fromkeys(opts.get("engines") or choose_tags(entries, paths["private"])))
            unknown = [t for t in tags if tuple(str(t).partition("@")[::2]) not in reg]
            if unknown or not tags:
                return done("blocked", ("등록되지 않은 엔진·버전: %s" % ", ".join(map(str, unknown))) if unknown else
                            "등록된 엔진이 없습니다. 레시피를 만든 뒤: python -m pipeline.forecast.runner register --name <이름> --label <화면 이름> --version 1", ok=False)
            write_json(plan_path, {"event": kind, "ref_period": ref, "engines": tags, "created_at": utc_text(now)})
        tags = list(dict.fromkeys(tags))
        final = lead < MIN_LEAD_H + FINAL_MARGIN_H
        engines = []
        for tag in tags:
            if tag in sealed:
                states[tag] = "sealed"
                continue
            eng, why = load_engine(tag, reg, paths["private"], paths["engines"])
            if eng:
                engines.append(eng)
            else:
                states[tag] = "blocked"
                memo.append("[주의] %s: %s" % (tag, why))

        bundle_sha, ids, places, base, head, usable = "", [], {}, [], {}, []
        if engines:
            if asked:
                try:
                    with open(bundle_path, "rb") as f:
                        data = f.read()
                    bundle = json.loads(data.decode("utf-8"))
                except Exception:
                    return done("blocked", "작업 폴더의 사실 묶음을 읽지 못함: %s" % bundle_path, ok=False)
            else:
                bundle, problems = build(kind, ref, utc_text(now), release_at, opts)
                if problems:
                    memo.extend(problems)
                    return done("blocked", "사실 묶음을 만들지 못함 (%d건)" % len(problems), ok=False)
                data = B.dumps(bundle)
                with open(bundle_path + ".tmp", "wb") as f:
                    f.write(data)
                os.replace(bundle_path + ".tmp", bundle_path)
            bundle_sha = hashlib.sha256(data).hexdigest()
            try:   # 묶음에서 쓸 것을 미리 다 꺼내 본다. 모양이 틀리면 부르기 전에 멈춘다
                ids = [t["target"] for t in bundle["targets"]]
                places = {t["target"]: int(t["decimals"]) for t in bundle["targets"]}
                base = [{"engine": "prev", "target": t["target"], "p50": t["prev"]["value"]} for t in bundle["targets"]]
                head = {"data_cutoff_utc": bundle["data_cutoff_utc"], "bundle_spec": bundle["bundle_spec"]}
                if not ids or not all(isinstance(t, str) and T.TARGETS[t][0] == kind for t in ids) or not all(_is_num(b["p50"]) for b in base):
                    raise ValueError
                for e in engines:
                    e["system"], e["user"], e["prompt_sha256"] = build_prompt(e["recipe"], bundle)
                    e["ids"], e["bundle_sha256"] = ids, bundle_sha
            except Exception:
                return done("blocked", "작업 폴더의 사실 묶음이 이 발표의 것이 아니거나 모양이 틀림: %s" % bundle_path, ok=False)
            stored = [r for t in tags for recs in answers_of(workdir, t).values() for r in recs if not r.get("unreadable")]
            if any(str(r.get("bundle_sha256")) != bundle_sha for r in stored):   # 답을 받은 뒤에 묶음 파일이 바뀌었다. 엔진마다 다른 자료를 보게 두지 않는다
                return done("blocked", "받아 둔 답이 지금의 사실 묶음과 다른 묶음에 대한 것입니다: %s" % bundle_path, ok=False)
        for e in engines:
            mine = [r for recs in answers_of(workdir, e["tag"]).values() for r in recs if not r.get("unreadable")]
            if any(str(r.get("prompt_sha256")) != e["prompt_sha256"] for r in mine):   # 받아 둔 답이 지금과 다른 글에 대한 답이다. 섞지 않는다
                states[e["tag"]] = "blocked"
                memo.append("[주의] %s: 받아 둔 답이 지금 보낼 글과 다른 글에 대한 것입니다. 섞지 않으려고 이 엔진을 멈춥니다" % e["tag"])
            else:
                usable.append(e)

        # 호출. 마감이 가까우면 더 부르지 않고, 봉인 마감 전에 끝나지 못할 호출은 시작하지 않는다. 엔진마다 일꾼을 따로 둔다
        budget, to_seal = float(opts.get("budget_sec") or 0), (lead - MIN_LEAD_H) * 3600.0 - SEAL_RESERVE_SEC
        deadline = clock() + (min(budget, to_seal) if budget else to_seal)
        lock, stats, jobs = threading.Lock(), {"calls": 0, "errors": {}, "made": {}}, []
        for e in usable:
            _state, _ok, pending = engine_progress(e["recipe"], workdir, e["tag"], final)
            e["key"] = (env.get(KEY_NAME[e["recipe"]["provider"]]) or "").strip()
            if pending and not e["key"]:
                e["last_error"] = "서버 .env 에 %s 가 없음" % KEY_NAME[e["recipe"]["provider"]]
            elif pending:
                jobs.append((e, pending))
        if jobs:
            parallel = max(1, int(opts.get("parallel") or 5))
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(jobs)) as pool:
                for f in [pool.submit(work_engine, e, pending, workdir, deadline, send, clock, sleep, lock, stats, parallel) for e, pending in jobs]:
                    f.result()
        res["calls"] = stats["calls"]

        # 엔진마다 어디까지 왔는가. 답이 다 모인 엔진은 합친다
        ready, forecasts, trouble = [], [], False
        for e in usable:
            state, ok, _pending = engine_progress(e["recipe"], workdir, e["tag"], final)
            recs = [r for v in answers_of(workdir, e["tag"]).values() for r in v]
            t_in, t_out = (sum(r[k] for r in recs if _count(r.get(k))) for k in ("tokens_in", "tokens_out"))
            note = "%s: 맞는 답 %d/%d · 받은 답 %d · 토큰 입력 %d / 출력 %d" % (e["tag"], len(ok), e["recipe"]["n_runs"], len(recs), t_in, t_out)
            secs = [r["seconds"] for r in ok.values() if _is_num(r.get("seconds"))]
            if secs:
                note += " · 한 번에 %d~%d초" % (min(secs), max(secs))
            if stats["errors"].get(e["tag"]):
                note += " · 이번 실행의 오류 %d번" % stats["errors"][e["tag"]]
            if state != "ready" and e["last_error"]:
                note += " · 마지막 오류: " + e["last_error"][:200]
                trouble = True
            if state == "pending" and e["short"] and not stats["made"].get(e["tag"]):
                note += " · 이번 실행에 쓸 시간이 한 번 부르는 시간(%d초)보다 짧아 부르지 못함" % e["recipe"]["timeout_sec"]
                trouble = True
            bad = [str(r.get("reason"))[:80] for r in recs if r["status"] == "invalid"]
            if bad:
                note += " · 형식이 틀린 답 %d번(%s)" % (len(bad), bad[-1])
            memo.append(note)
            if state == "ready":
                try:
                    mine = []
                    for t in ids:
                        runs = []
                        for k in sorted(ok):
                            v = ok[k]["values"][t]
                            if not all(_is_num(v[q]) for q in ("p10", "p50", "p90")) or not (v["p10"] <= v["p50"] <= v["p90"]):
                                raise ValueError
                            runs.append({"p10": float(v["p10"]), "p50": float(v["p50"]), "p90": float(v["p90"]), "run": k})
                        mine.append(dict(AGGREGATORS[e["recipe"]["aggregate"]](runs, places[t]), engine=e["name"], version=e["version"], target=t, n_runs=len(runs), runs=runs))
                except Exception as err:   # 답 파일이 상했다. 이 엔진만 멈춘다
                    state = "blocked"
                    memo.append("[주의] %s: 받아 둔 답을 합치지 못함 (%s)" % (e["tag"], type(err).__name__))
                else:
                    forecasts += mine
                    ready.append(e)
                    e["summary"] = {"engine": e["name"], "version": e["version"], "provider": e["recipe"]["provider"], "model": e["recipe"]["model"],
                                    "models_reported": sorted({str(r.get("model")) for r in ok.values()}), "render": e["recipe"]["render"],
                                    "answer": e["recipe"]["answer"], "aggregate": e["recipe"]["aggregate"], "prompt_sha256": e["prompt_sha256"],
                                    "n_runs": e["recipe"]["n_runs"], "valid_runs": len(ok), "answers": len(recs), "tokens_in": t_in, "tokens_out": t_out}
            states[e["tag"]] = state

        # 답이 다 모인 엔진은 바로 봉인한다(다른 엔진을 기다리지 않는다)
        sealed_now = []
        if ready:
            doc = dict(head, event={"kind": kind, "ref_period": ref, "release_at_utc": release_at}, bundle_sha256=bundle_sha, forecasts=forecasts + base,
                       execution={"runner": RUNNER, "engines": [e["summary"] for e in ready], "others": {t: s for t, s in sorted(states.items()) if s != "ready"}})
            path = os.path.join(workdir, "forecast_%s_%s.json" % (utc_text(now).replace(":", "").replace("-", ""), "+".join(e["tag"] for e in ready)))
            write_json(path, doc)
            argv = ["--file", path, "--ledger-dir", paths["ledger"], "--private-dir", paths["private"], "--engines-dir", paths["engines"], "--min-lead-hours", str(MIN_LEAD_H)]
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = S.main(argv + (["--no-ots"] if opts.get("no_ots") else []), now=now if fixed_now else None)
            out = [x.strip() for x in buf.getvalue().splitlines() if x.strip()]
            if code != 0:
                memo.extend(x for x in out if x.startswith(("[중단]", "- ")))
                return done("blocked", "봉인 명령이 멈춤 (코드 %s) · 받은 답은 그대로 있고, 다시 돌리면 봉인부터 다시 합니다" % code, ok=False)
            memo.extend(x for x in out if x.startswith(("기록 #", "봉인:")))
            res["stamped"] = None if opts.get("no_ots") else any("타임스탬프 받음" in x or "타임스탬프 있음" in x for x in out)
            for e in ready:
                states[e["tag"]] = "sealed"
                sealed_now.append(e["tag"])
        elif sealed:
            stamp()

        # 전체 상태. 마감이 가까우면 쓸 수 없던 엔진도 미제출로 닫는다
        if final:
            states.update({t: "missed" for t, s in states.items() if s in ("blocked", "pending")})
        by = {s: [t for t in tags if states.get(t) == s] for s in ("sealed", "pending", "blocked", "missed")}
        tail = "".join(" · %s: %s" % (label, ", ".join(by[s])) for s, label in (("pending", "진행 중"), ("blocked", "쓸 수 없음"), ("missed", "미제출")) if by[s])
        if by["pending"] or by["blocked"]:
            head_text = "봉인함 · %s" % ", ".join(sealed_now) if sealed_now else "진행 중"
            return done("pending", "%s · %s %s%s · 다시 돌리면 남은 것만 합니다" % (head_text, kind, ref, tail), ok=not (trouble or by["blocked"]))
        if sealed_now:
            return done("sealed", "봉인함 · %s %s · %s · 묶음 %s…%s" % (kind, ref, ", ".join(sealed_now), bundle_sha[:12], tail))
        if by["sealed"]:
            return done("already", "이미 봉인됨 · %s %s · %s%s" % (kind, ref, ", ".join(by["sealed"]), tail))
        return done("missed", "미제출 — 형식이 맞는 답이 모자람 · %s %s%s" % (kind, ref, tail), ok=False)


# --- 명령

def _folders(a):
    """(이름, 버전, 폴더) 목록: --dir 로 준 폴더들, 없으면 엔진 폴더의 이름별 가장 높은 버전."""
    if a.dir:
        return [(os.path.basename(os.path.dirname(os.path.abspath(d))), os.path.basename(os.path.abspath(d)).lstrip("v"), d) for d in a.dir]
    return latest_folders(a.engines_dir)


def cmd_check(a):
    folders = _folders(a)
    if not folders:
        print("레시피 폴더가 없습니다: %s" % a.engines_dir)
        return 2
    reg = E.registered(core.read_ledger(os.path.join(a.ledger_dir, "ledger.jsonl")))
    bad = 0
    for name, ver, folder in folders:
        recipe, problems = load_recipe(folder)
        digest = E.recipe_hash(folder)[0]
        if (name, ver) not in reg:
            where = "등록 전"
        else:
            where = "등록됨, 폴더 그대로" if reg[(name, ver)]["recipe_sha256"] == digest else "[주의] 등록 때와 폴더가 다름"
        if problems:
            bad += 1
            print("%s v%s — 쓸 수 없음 (%s)" % (name, ver, where))
            for p in problems:
                print("   - " + p)
            continue
        print("%s v%s — 형식 맞음 · %s · %s · %d번 가운데 %d번 이상 · 한 번에 출력 최대 %d토큰 · %s · 해시 %s"
              % (name, ver, recipe["provider"], recipe["model"], recipe["n_runs"], recipe["min_valid_runs"], recipe["request"][CAP_NAME[recipe["provider"]]], where, digest[:16]))
    return 2 if bad else 0


def cmd_probe(a, send=http_send, env=None):
    env = envmod.load() if env is None else env
    pairs = []
    if a.provider and a.model:
        pairs.append((a.provider, a.model))
    else:
        for name, ver, folder in _folders(a):
            recipe, problems = load_recipe(folder)
            if recipe:
                pairs.append((recipe["provider"], recipe["model"]))
    if not pairs:
        print("부를 모델이 없습니다. 레시피를 만들었거나, --provider anthropic --model <모델 ID> 로 직접 적습니다.")
        return 2
    code = 0
    for provider, model in sorted(set(pairs)):
        key = (env.get(KEY_NAME[provider]) or "").strip()
        if not key:
            print("%s · %s — .env 에 %s 가 없음" % (provider, model, KEY_NAME[provider]))
            code = 1
            continue
        recipe = {"provider": provider, "model": model, "answer": "json/1", "request": {CAP_NAME[provider]: 256}}
        rec = call_once(recipe, "", "OK 라고만 답하세요.", [], key, 120, send)
        if rec["status"] == "error":
            code = 1
            print("%s · %s — 실패 · %s" % (provider, model, rec["reason"]))
        else:   # 답이 왔으면 닿은 것이다(짧게 끊긴 답이어도)
            print("%s · %s — 닿음 · 응답한 모델 %s · 끝난 이유 %s · 토큰 입력 %s / 출력 %s" % (provider, model, rec.get("model"), rec.get("stop"), rec.get("tokens_in"), rec.get("tokens_out")))
    return code


def _bundle_now(a, now):
    release_at = B.lookup_release(a.schedule, a.event, a.ref)
    if not release_at:
        return None, ["일정표에 없는 발표: %s %s" % (a.event, a.ref)]
    return build_bundle_from_db(a.event, a.ref, utc_text(now), release_at, {"db": a.db})


def cmd_render(a):
    bundle, problems = _bundle_now(a, datetime.now(timezone.utc))
    if problems:
        print("[중단] " + " / ".join(problems))
        return 2
    print(RENDERERS[a.render](bundle), end="")
    return 0


def cmd_preview(a, send=http_send, env=None):
    """엔진마다 한 번 불러 형식만 본다. 답은 메모리에서 형식만 확인하고 버린다 — 저장하지 않고, 찍지 않고, 봉인에 쓰지 않는다."""
    env = envmod.load() if env is None else env
    folders = _folders(a)
    if not folders:
        print("레시피 폴더가 없습니다: %s" % a.engines_dir)
        return 2
    bundle, problems = _bundle_now(a, datetime.now(timezone.utc))
    if problems:
        print("[중단] " + " / ".join(problems))
        return 2
    ids = [t["target"] for t in bundle["targets"]]
    print("미리 보기 — %s %s · 대상 %d개 · 묶음 %d바이트. 답은 저장하지 않고 화면에도 찍지 않습니다." % (a.event, a.ref, len(ids), len(B.dumps(bundle))))
    code = 0
    for name, ver, folder in folders:
        recipe, problems = load_recipe(folder)
        if problems:
            code = 1
            print("%s v%s — 레시피를 쓸 수 없음: %s" % (name, ver, " / ".join(problems)))
            continue
        key = (env.get(KEY_NAME[recipe["provider"]]) or "").strip()
        if not key:
            code = 1
            print("%s v%s — .env 에 %s 가 없음" % (name, ver, KEY_NAME[recipe["provider"]]))
            continue
        system, user, _digest = build_prompt(recipe, bundle)
        rec = call_once(recipe, system, user, ids, key, recipe["timeout_sec"], send)
        head = "%s v%s (%s · %s) — 보낸 글 %d자" % (name, ver, recipe["provider"], recipe["model"], len(system) + len(user))
        tail = " · %s초 · 토큰 입력 %s / 출력 %s · 끝난 이유 %s" % (rec["seconds"], rec.get("tokens_in"), rec.get("tokens_out"), rec.get("stop"))
        if rec["status"] == "ok":
            print("%s · 형식 맞음(값 %d개)%s · 응답한 모델 %s" % (head, 3 * len(ids), tail, rec.get("model")))
            continue
        code = 1
        if rec["status"] == "error":
            print("%s · 실패 · %s" % (head, rec["reason"]))
        else:   # 답의 글은 한 글자도 찍지 않는다(숫자를 가려도 방향이 읽힌다). 모양만 알려 준다
            text = rec.get("text") or ""
            print("%s · 형식이 틀림 · %s%s · 답의 글자 수 %d · 중괄호 %s · forecasts 라는 말 %s"
                  % (head, rec["reason"], tail, len(text), "있음" if "{" in text else "없음", "있음" if "forecasts" in text else "없음"))
    return code


def count_input_tokens(recipe, system, user, key, send=http_send):
    """보낼 글의 입력 토큰 수를 그 회사 API에 물어본다(엔진을 부르지 않는다. 무료). 묻지 못하면 None."""
    try:
        if recipe["provider"] == "anthropic":
            body = {"model": recipe["model"], "messages": [{"role": "user", "content": user}]}
            if system:
                body["system"] = system
            url, headers = "https://api.anthropic.com/v1/messages/count_tokens", {"x-api-key": key, "anthropic-version": "2023-06-01"}
        else:
            body = {"model": recipe["model"], "input": [{"role": "user", "content": user}]}
            if system:
                body["instructions"] = system
            url, headers = "https://api.openai.com/v1/responses/input_tokens", {"Authorization": "Bearer " + key}
        status, doc, _err, _after = send(url, headers, body, 60)
        return _count(doc.get("input_tokens")) if status == 200 and isinstance(doc, dict) else None
    except Exception:
        return None


def usage_bounds(recipe, tokens_in):
    """레시피와 입력 토큰 수로 정해지는 상한. 돌려주는 값의 토큰은 입력+출력 합계, 요금은 달러(요금표에 없는 모델이면 None)."""
    cap, n, tries = recipe["request"][CAP_NAME[recipe["provider"]]], recipe["n_runs"], recipe["max_attempts"]
    price = PRICES.get(recipe["model"])

    def usd(calls, out_per_call):
        return None if price is None else calls * (tokens_in * price[0] + out_per_call * price[1]) / 1e6

    return {"cap": cap, "per_call": tokens_in + cap, "event": n * (tokens_in + cap), "worst": n * tries * (tokens_in + cap),
            "usd_event": usd(n, cap), "usd_worst": usd(n * tries, cap), "usd_half": usd(n, cap / 2), "price": price}


def cmd_estimate(a, send=http_send, env=None):
    """레시피대로 돌리면 토큰을 얼마나 쓰는지: 입력은 세어 보고, 출력은 레시피의 상한으로 계산한다. 엔진은 부르지 않는다."""
    env = envmod.load() if env is None else env
    folders = _folders(a)
    if not folders:
        print("레시피 폴더가 없습니다: %s" % a.engines_dir)
        return 2
    bundle, problems = _bundle_now(a, datetime.now(timezone.utc))
    if problems:
        print("[중단] " + " / ".join(problems))
        return 2
    print("토큰 어림 — %s %s · 발표 한 번 기준. 엔진은 부르지 않았습니다." % (a.event, a.ref))
    code, total_event, total_worst = 0, 0.0, 0.0
    for name, ver, folder in folders:
        recipe, problems = load_recipe(folder)
        if problems:
            code = 1
            print("%s v%s — 레시피를 쓸 수 없음: %s" % (name, ver, " / ".join(problems)))
            continue
        system, user, _digest = build_prompt(recipe, bundle)
        key = (env.get(KEY_NAME[recipe["provider"]]) or "").strip()
        counted = count_input_tokens(recipe, system, user, key, send) if key else None
        tokens_in = counted if counted is not None else len(system) + len(user)   # 못 세면 글자 수만큼으로 넉넉하게 잡는다(실제는 이보다 적다)
        b = usage_bounds(recipe, tokens_in)
        print("%s v%s (%s · %s) — 보낼 글 %d자 · 입력 %d토큰(%s)" % (name, ver, recipe["provider"], recipe["model"], len(system) + len(user), tokens_in,
                                                               "API가 센 값" if counted is not None else "세지 못해 글자 수로 넉넉하게 잡음"))
        print("   한 번 부를 때: 입력 %d + 출력 최대 %d(생각하는 토큰 포함. 넘으면 답이 끊기고 그 답은 쓰지 않는다)" % (tokens_in, b["cap"]))
        print("   발표 한 번: %d번 불러 최대 %d토큰 · 형식이 틀린 답을 모두 다시 받는 최악은 %d번, %d토큰" % (recipe["n_runs"], b["event"], recipe["n_runs"] * recipe["max_attempts"], b["worst"]))
        if b["price"]:
            print("   요금(100만 토큰당 입력 $%g · 출력 $%g 로 어림): 발표 한 번 최대 $%.2f · 최악 $%.2f · 출력이 상한의 절반이면 $%.2f" % (b["price"] + (b["usd_event"], b["usd_worst"], b["usd_half"])))
            total_event, total_worst = total_event + b["usd_event"], total_worst + b["usd_worst"]
        else:
            print("   요금: 이 모델의 요금이 코드의 요금표(PRICES)에 없어 계산하지 않음")
    if total_event:
        print("합계: 발표 한 번 최대 $%.2f · 최악 $%.2f. 실제로 나온 토큰은 preview 가 한 번 불러서 알려 줍니다." % (total_event, total_worst))
    return code


def cmd_register(a):
    if not re.match(r"^[1-9]\d{0,3}$", str(a.version)):
        print("[중단] 버전은 1, 2, 3 … 숫자로 적습니다.")
        return 2
    folder = os.path.join(a.engines_dir, a.name, "v" + str(a.version))
    recipe, problems = load_recipe(folder)
    if problems:
        print("[중단] 레시피를 쓸 수 없습니다: %s" % folder)
        for p in problems:
            print("   - " + p)
        return 2
    argv = ["register", "--name", a.name, "--version", str(a.version), "--model", recipe["model"], "--mode", "api", "--n-runs", str(recipe["n_runs"]),
            "--dir", folder, "--ledger-dir", a.ledger_dir, "--private-dir", a.private_dir]
    return E.main(argv + (["--label", a.label] if a.label else []) + (["--note", a.note] if a.note else []) + (["--no-ots"] if a.no_ots else []))


def cmd_run(a):
    opts = {"ledger_dir": a.ledger_dir, "private_dir": a.private_dir, "engines_dir": a.engines_dir, "runs_dir": a.runs_dir, "schedule": a.schedule, "db": a.db,
            "budget_sec": a.budget_sec, "parallel": a.parallel, "no_ots": a.no_ots, "engines": [x for x in (a.engines or "").split(",") if x] or None}
    res = run_event(a.event, a.ref, opts)
    print(res["result"])
    for m in res["memo"]:
        print("   " + m)
    return {"sealed": 0, "already": 0, "pending": 3, "missed": 1}.get(res["state"], 2)


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="엔진 실행기")
    sub = ap.add_subparsers(dest="cmd", required=True)
    cmds = {}
    for name in ("check", "probe", "render", "estimate", "preview", "register", "run"):
        p = cmds[name] = sub.add_parser(name)
        p.add_argument("--engines-dir", default=os.path.join(ROOT, "data", "private", "engines"))
        p.add_argument("--ledger-dir", default=os.path.join(ROOT, "data", "ledger", "public"))
        p.add_argument("--private-dir", default=os.path.join(ROOT, "data", "private", "ledger"))
    for name in ("check", "probe", "estimate", "preview"):
        cmds[name].add_argument("--dir", action="append", help="레시피 폴더를 직접 지정(여러 번 쓸 수 있음). 없으면 엔진 폴더의 이름별 가장 높은 버전")
    for name in ("render", "estimate", "preview", "run"):
        cmds[name].add_argument("--event", required=True, choices=sorted(T.EVENTS))
        cmds[name].add_argument("--ref", required=True, help="기준 기간 (예: 2026-09)")
        cmds[name].add_argument("--db", default=store.DEFAULT_DB)
        cmds[name].add_argument("--schedule", default=os.path.join(ROOT, "data", "forecast", "schedule_*.csv"))
    cmds["probe"].add_argument("--provider", choices=sorted(PROVIDERS))
    cmds["probe"].add_argument("--model")
    cmds["render"].add_argument("--render", default="table/1", choices=sorted(RENDERERS))
    r = cmds["register"]
    r.add_argument("--name", required=True)
    r.add_argument("--label", default=None, help="화면에 보일 이름 (예: 아들러)")
    r.add_argument("--version", required=True)
    r.add_argument("--note", default=None)
    r.add_argument("--no-ots", action="store_true")
    u = cmds["run"]
    u.add_argument("--runs-dir", default=os.path.join(ROOT, "data", "private", "forecast", "runs"))
    u.add_argument("--engines", default=None, help="쓸 엔진을 직접 지정 (예: adler@1,fletcher@1). 없으면 등록된 엔진마다 가장 높은 버전. 이 발표의 첫 답을 받기 전까지만 쓰인다")
    u.add_argument("--budget-sec", type=float, default=0, help="이번 실행에 쓸 시간(초). 0이면 봉인 마감까지. 모자라면 '진행 중'으로 끝나고 다시 돌리면 이어 간다")
    u.add_argument("--parallel", type=int, default=5, help="엔진마다 한꺼번에 부르는 수")
    u.add_argument("--no-ots", action="store_true")
    return ap.parse_args(argv)


def main(argv=None):
    setup_console()
    a = parse_args(argv)
    return {"check": cmd_check, "probe": cmd_probe, "render": cmd_render, "estimate": cmd_estimate, "preview": cmd_preview, "register": cmd_register, "run": cmd_run}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
