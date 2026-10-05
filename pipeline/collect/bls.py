"""노동통계국(BLS) 공개 API에서 물가·고용·생산자물가 계열을 받아 DB에 쌓는다. 표준 라이브러리만 사용.

    python -m pipeline.collect.bls              받아서 저장
    python -m pipeline.collect.bls --dry-run    받아서 확인만 하고 저장하지 않음 (PC의 collect_indicators.bat 과 같음)

서버에서는 예약 작업 일꾼(pipeline/console/jobs.py)이 collect() 를 부른다: 매일 아침과 발표 직후. 기록은 서버 한 곳에만 쌓는다.

하는 일
1. catalog.py 의 계열을 한 번의 요청으로 받는다. .env 의 BLS_API_KEY 를 쓴다(없어도 돌지만 제목 대조를 못 하고 하루 25회 제한).
2. 받은 원문을 data/raw/bls/ 에 그대로 둔다(키는 응답에 들어 있지 않다).
3. 계열 제목이 목록의 기대와 맞는지 대조한다. 맞지 않으면 '불일치'로 표시한다(사실 묶음에서 빠진다).
4. 수준값과 파생값(전월비·전년비·증감)을 DB에 쌓는다. 이미 있는 값과 같으면 넣지 않고, 다르면 새 줄로 쌓는다.
   전월비·전년비는 발표된 지수(문자열 그대로)로 계산해 소수 1자리로 반올림한다. 노동통계국이 발표 수치를 만드는 방식과 같다.
5. 일정표(data/forecast/schedule_*.csv)에서 발표가 지난 대상의 '처음 발표값'을 data/forecast/actuals.csv 에 덧붙인다.
"""
import argparse
import csv
import glob
import hashlib
import http.client
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from calendar import monthrange
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from ..forecast import targets as T
from ..forecast.score import ACTUAL_FIELDS
from . import catalog as C
from . import env, store

API_V2 = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
API_V1 = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
DEFAULT_SCHEDULE = os.path.join(store.ROOT, "data", "forecast", "schedule_*.csv")
DEFAULT_ACTUALS = os.path.join(store.ROOT, "data", "forecast", "actuals.csv")
RETRY_WAITS = (5, 20)   # 서버 쪽 오류(5xx)나 접속 실패면 이만큼(초) 쉬고 두 번 더 받아 본다. 노동통계국 API는 가끔 503을 낸다
LATE_DAYS = 20   # 발표 뒤 이보다 늦게 처음 받은 값은 수정치일 수 있어 '처음 발표값'으로 쓰지 않는다


def setup_console():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except Exception:
            pass


def fetch(series_ids, start_year, end_year, key, timeout=40):
    """(http_status, 응답 본문 bytes, 쓴 주소). 키는 요청 본문에만 들어가고 어디에도 저장하지 않는다."""
    body = {"seriesid": list(series_ids), "startyear": str(start_year), "endyear": str(end_year)}
    url = API_V1
    if key:
        url = API_V2
        body.update({"registrationkey": key, "catalog": True, "calculations": True})
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "User-Agent": "checksumlab-collector/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read(), url


def fetch_retry(fetcher, ids, start_year, end_year, key, waits=RETRY_WAITS, say=print, sleep=time.sleep):
    """잠깐의 장애는 그 자리에서 다시 받는다. 키·요청이 틀린 경우(4xx)는 다시 받지 않는다."""
    for i in range(len(waits) + 1):
        try:
            return fetcher(ids, start_year, end_year, key)
        except urllib.error.HTTPError as e:
            if e.code < 500 or i == len(waits):
                raise
            why = "HTTP %s" % e.code
        except (urllib.error.URLError, OSError, http.client.HTTPException) as e:
            if i == len(waits):
                raise
            why = type(e).__name__
        say("   받지 못함(%s). %d초 뒤 다시 받습니다 (%d/%d)" % (why, waits[i], i + 1, len(waits)))
        sleep(waits[i])


def month_end(year, month):
    return "%04d-%02d-%02d" % (year, month, monthrange(year, month)[1])


def parse(doc):
    """응답 -> {계열 번호: {"title", "values": {(년, 월): '문자열 값'}, "calc": {(년, 월): {"pc1": '0.3', ...}}}}, 메시지 목록."""
    out = {}
    for s in ((doc.get("Results") or {}).get("series") or []):
        sid = s.get("seriesID")
        cat = s.get("catalog") or {}
        item = {"title": cat.get("series_title"), "values": {}, "calc": {}}
        for d in s.get("data") or []:
            period = str(d.get("period", ""))
            if not (len(period) == 3 and period[0] == "M" and period[1:].isdigit() and 1 <= int(period[1:]) <= 12):
                continue   # M13(연평균) 등은 쓰지 않는다
            ym = (int(d["year"]), int(period[1:]))
            raw = str(d.get("value", "")).strip()
            try:
                Decimal(raw)
            except InvalidOperation:
                continue   # '-' 처럼 값이 비어 있는 달 (예: 조사가 없었던 달)
            item["values"][ym] = raw
            calc = d.get("calculations")
            if isinstance(calc, dict):
                got = {}
                for src, name in (("pct_changes", "pc"), ("net_changes", "nc")):
                    part = calc.get(src)
                    if isinstance(part, dict):
                        for k, v in part.items():
                            got[name + str(k)] = str(v)
                item["calc"][ym] = got
        out[sid] = item
    return out, [str(m) for m in (doc.get("message") or [])]


def _shift(ym, months):
    y, m = ym
    idx = y * 12 + (m - 1) - months
    return (idx // 12, idx % 12 + 1)


def derive(values, kind):
    """발표된 문자열 값으로 파생값을 만든다. 비교할 달이 비어 있으면 그 달은 만들지 않는다."""
    lag = 12 if kind == "pc12" else 1
    out = {}
    for ym, raw in values.items():
        prev = values.get(_shift(ym, lag))
        if prev is None:
            continue
        cur, old = Decimal(raw), Decimal(prev)
        if kind.startswith("pc"):
            if old == 0:
                continue
            out[ym] = ((cur / old - 1) * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        else:
            out[ym] = cur - old
    return out


def check_title(title, keywords):
    if not title:
        return "unknown"
    low = title.lower()
    return "ok" if all(k in low for k in keywords) else "mismatch"


def ingest(con, parsed, known_at, fetch_id):
    """DB에 쌓고 요약을 돌려준다."""
    rep = {"new": 0, "revised": 0, "same": 0, "missing": [], "mismatch": [], "unknown": 0, "calc_diff": [], "latest": {}}
    for bls_id, group, name_ko, unit, keywords, derived in C.BLS:
        item = parsed.get(bls_id)
        if item is None or not item["values"]:
            rep["missing"].append(bls_id)
            continue
        status = check_title(item["title"], keywords)
        store.set_meta(con, "series_check." + C.series_id(bls_id), status + "\t" + (item["title"] or ""))
        if status == "mismatch":
            rep["mismatch"].append("%s (%s): %s" % (bls_id, name_ko, item["title"]))
        elif status == "unknown":
            rep["unknown"] += 1
        store.ensure_series(con, C.series_id(bls_id), name_ko, unit, "M", "bls", note=group)
        for ym, raw in item["values"].items():
            rep[store.put(con, C.series_id(bls_id), month_end(*ym), raw, known_at, fetch_id)] += 1
        rep["latest"][bls_id] = max(item["values"])
        for kind in derived:
            label = {"pc1": "전월비", "pc12": "전년비", "nc1": "전월 대비 증감"}[kind]
            sid = C.series_id(bls_id, kind)
            store.ensure_series(con, sid, "%s %s" % (name_ko, label), "%" if kind.startswith("pc") else unit, "M", "bls", note=group)
            for ym, val in derive(item["values"], kind).items():
                rep[store.put(con, sid, month_end(*ym), val, known_at, fetch_id)] += 1
                api = (item["calc"].get(ym) or {}).get(kind)
                if api is not None and kind.startswith("pc"):
                    try:
                        if Decimal(api) != val:
                            rep["calc_diff"].append("%s %04d-%02d %s: 계산 %s / API %s" % (bls_id, ym[0], ym[1], kind, val, api))
                    except InvalidOperation:
                        pass
    return rep


def ref_to_obs_date(event_kind, ref_period):
    if T.EVENTS[event_kind][2] != "M":
        return None
    y, m = ref_period.split("-")
    return month_end(int(y), int(m))


def record_actuals(con, schedule_glob, actuals_path, now):
    """발표가 지난 대상의 처음 발표값을 actuals.csv 에 덧붙인다. 이미 있는 줄은 건드리지 않는다."""
    have = set()
    if os.path.exists(actuals_path):
        with open(actuals_path, encoding="utf-8-sig", newline="") as f:
            have = {(r["target"], r["ref_period"]) for r in csv.DictReader(f)}
    added, notes = [], []
    for path in sorted(glob.glob(schedule_glob)):
        with open(path, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        for r in rows:
            targets = [t for t in (r.get("targets") or "").split() if t in C.TARGET_SERIES]
            if not targets:
                continue   # 수집기가 없는 발표는 날짜가 비어 있어도 상관없다
            try:
                released = datetime.strptime(r["release_at_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                if r["event_kind"] not in T.EVENTS or not T.ref_period_ok(r["event_kind"], r["ref_period"]):
                    raise ValueError("event_kind/ref_period")
            except (TypeError, ValueError, KeyError):
                notes.append("일정표에서 읽을 수 없는 줄(건너뜀): %s %s %r" % (r.get("event_kind"), r.get("ref_period"), r.get("release_at_utc")))
                continue
            if released > now:
                continue
            for target in targets:
                if (target, r["ref_period"]) in have:
                    continue
                obs_date = ref_to_obs_date(r["event_kind"], r["ref_period"])
                row = store.first_known(con, C.target_series_id(target), obs_date) if obs_date else None
                if row is None:
                    if now - released > timedelta(days=1):
                        notes.append("%s %s: 발표가 지났는데 값이 아직 없습니다" % (target, r["ref_period"]))
                    continue
                value, known_at = row
                known = datetime.strptime(known_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                if known - released > timedelta(days=LATE_DAYS):
                    notes.append("%s %s: 발표 %d일 뒤에 처음 받은 값이라 넣지 않았습니다(수정치일 수 있음). 발표문에서 확인해 직접 넣으세요"
                                 % (target, r["ref_period"], (known - released).days))
                    continue
                places = T.decimals(target)
                added.append({"event_kind": r["event_kind"], "ref_period": r["ref_period"], "target": target,
                              "actual": ("%." + str(places) + "f") % value, "released_at_utc": r["release_at_utc"],
                              "source_url": C.SOURCE_URL.get(r["event_kind"], r.get("source_url", "")),
                              "known_at_utc": known_at, "note": ""})
                have.add((target, r["ref_period"]))
    if added:
        os.makedirs(os.path.dirname(actuals_path), exist_ok=True)
        fresh = not os.path.exists(actuals_path)
        with open(actuals_path, "a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=ACTUAL_FIELDS, lineterminator="\n")
            if fresh:
                w.writeheader()
            w.writerows(added)
    return added, notes


def redact(text, key):
    """문구에 키가 섞여 있으면 가린다. 잘못된 키로 요청하면 오류 문구에 그 키가 그대로 실려 올 수 있다(대소문자가 바뀌어 와도 가린다)."""
    return re.sub(re.escape(key), "(키 가림)", str(text), flags=re.IGNORECASE) if key else str(text)


def collect(db=None, raw_dir=None, schedule=None, actuals=None, years=5, from_file=None, dry_run=False, now=None, say=print, key=None, fetcher=None, retry_waits=None):
    """한 번 수집한다. (종료 코드, 요약)을 돌려준다. 화면에 낼 줄은 say 로 보낸다.

    요약은 서버의 예약 작업 일꾼이 조종판 '오늘 현황'에 적는 재료다. 키 값은 요약·화면·원문 어디에도 남기지 않는다.
    """
    db = db or store.DEFAULT_DB
    raw_dir = raw_dir or os.path.join(store.ROOT, "data", "raw", "bls")
    schedule = schedule or DEFAULT_SCHEDULE
    actuals = actuals or DEFAULT_ACTUALS
    fetcher = fetcher or fetch
    now = now or datetime.now(timezone.utc)
    known_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    key = env.get("BLS_API_KEY") if key is None else key
    ids = [row[0] for row in C.BLS]
    rep = {"ok": False, "error": "", "error_kind": "", "received": 0, "listed": len(ids), "new": 0, "revised": 0, "same": 0, "newest": None,
           "unknown": 0, "mismatch": [], "missing": [], "calc_diff": [], "added": [], "notes": [], "raw_path": "", "dry_run": bool(dry_run)}

    def fail(code, kind, text):
        rep["error"], rep["error_kind"] = text, kind
        say("[%s] %s" % ("중단" if kind == "no_key" else "실패", text))
        return code, rep

    if from_file:
        with open(from_file, "rb") as f:
            status, raw, url = 200, f.read(), "file:" + os.path.basename(from_file)
    else:
        if not key:
            say("[알림] .env 에 BLS_API_KEY 가 없습니다. 키 없이 받습니다(제목 대조 불가, 하루 25회, 계열 25개까지).")
            if len(ids) > 25:
                return fail(2, "no_key", "계열이 %d개라 키 없이는 한 번에 받을 수 없습니다. https://data.bls.gov/registrationEngine/ 에서 키를 받아 .env 에 넣으세요." % len(ids))
        try:
            status, raw, url = fetch_retry(fetcher, ids, now.year - years + 1, now.year, key, RETRY_WAITS if retry_waits is None else retry_waits, say)
        except (urllib.error.URLError, OSError, http.client.HTTPException) as e:
            return fail(1, "network", "노동통계국 API에 닿지 못했습니다: %s" % redact(e, key))
    if key and len(key) >= 16 and not from_file and key.encode("utf-8") in raw:   # 원문에도 키를 남기지 않는다(실제 키는 32자. 짧은 값은 자료와 겹칠 수 있어 건드리지 않는다)
        raw = raw.replace(key.encode("utf-8"), "(키 가림)".encode("utf-8"))
    try:
        doc = json.loads(raw.decode("utf-8"))
    except ValueError:
        return fail(1, "unreadable", "응답을 읽을 수 없습니다 (HTTP %s)." % status)
    if doc.get("status") != "REQUEST_SUCCEEDED":
        return fail(1, "api", "API 상태 %r: %s" % (doc.get("status"), redact("; ".join(str(m) for m in doc.get("message") or []), key)[:400]))
    parsed, messages = parse(doc)
    rep["received"] = len(parsed)
    say("받은 계열 %d개 / 목록 %d개 (%s)" % (len(parsed), len(ids), "키 사용" if key and not from_file else "키 없음 또는 파일"))
    for m in messages[:8]:
        say("   API 메시지: " + redact(m, key)[:160])

    if dry_run:
        for bls_id, group, name_ko, unit, keywords, derived in C.BLS:
            item = parsed.get(bls_id)
            if not item or not item["values"]:
                say("   없음        %s %s" % (bls_id, name_ko))
                continue
            ym = max(item["values"])
            say("   %-9s %s %s — 최신 %04d-%02d = %s" % (check_title(item["title"], keywords), bls_id, name_ko, ym[0], ym[1], item["values"][ym]))
        say("--dry-run: 저장하지 않았습니다.")
        rep["ok"] = True
        return 0, rep

    con = store.connect(db)
    try:   # 도중에 멈춰도 쓰던 것을 쥔 채로 남지 않게 한다(남으면 같은 프로세스의 다음 연결이 'database is locked'로 멈춘다)
        os.makedirs(raw_dir, exist_ok=True)
        raw_path = os.path.join(raw_dir, "bls_%s.json" % now.strftime("%Y%m%dT%H%M%SZ"))
        with open(raw_path, "wb") as f:
            f.write(raw)
        fetch_id = store.add_fetch(con, "bls", url, known_at, status, hashlib.sha256(raw).hexdigest(), os.path.relpath(raw_path, store.ROOT))
        got = ingest(con, parsed, known_at, fetch_id)
        added, notes = record_actuals(con, schedule, actuals, now)
        con.execute("INSERT INTO job_run(job_id,started_at,finished_at,status,detail) VALUES ('collect_indicators',?,?,?,?)",
                    (known_at, store.utc_now(), "ok", "new=%d revised=%d same=%d" % (got["new"], got["revised"], got["same"])))
        con.commit()
    except BaseException:
        con.rollback()
        raise
    finally:
        con.close()
    for k in ("new", "revised", "same", "unknown", "mismatch", "missing", "calc_diff"):
        rep[k] = got[k]
    rep.update({"ok": True, "added": added, "notes": notes, "raw_path": raw_path,
                "newest": max(got["latest"].values()) if got["latest"] else None})

    say("저장: 새 값 %d / 수정된 값 %d / 그대로 %d" % (rep["new"], rep["revised"], rep["same"]))
    if rep["newest"]:
        say("가장 최근 달: %04d-%02d" % rep["newest"])
    if rep["unknown"]:
        say("[알림] 제목을 대조하지 못한 계열 %d개 (키가 없으면 제목이 오지 않습니다)" % rep["unknown"])
    for line in rep["mismatch"]:
        say("[주의] 제목 불일치 — 사실 묶음에서 빠집니다: " + line)
    if rep["missing"]:
        say("[주의] 값이 오지 않은 계열: " + ", ".join(rep["missing"]))
    if rep["calc_diff"]:
        say("[주의] 계산값이 API 계산과 다른 곳 %d건 (처음 5건):" % len(rep["calc_diff"]))
        for line in rep["calc_diff"][:5]:
            say("   " + line)
    for r in added:
        say("처음 발표값 기록: %s %s = %s" % (r["target"], r["ref_period"], r["actual"]))
    for n in notes:
        say("[주의] " + n)
    say("원문: %s" % raw_path)
    return 0, rep


def main(argv=None):
    setup_console()
    ap = argparse.ArgumentParser(description="노동통계국 지표 수집")
    ap.add_argument("--db", default=store.DEFAULT_DB)
    ap.add_argument("--raw-dir", default=os.path.join(store.ROOT, "data", "raw", "bls"))
    ap.add_argument("--schedule", default=DEFAULT_SCHEDULE)
    ap.add_argument("--actuals", default=DEFAULT_ACTUALS)
    ap.add_argument("--years", type=int, default=5, help="올해 포함 몇 해를 받을지 (키 없으면 최대 10, 있으면 20)")
    ap.add_argument("--from-file", default=None, help="시험용: API 대신 저장된 응답 파일을 읽는다")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    code, _ = collect(db=a.db, raw_dir=a.raw_dir, schedule=a.schedule, actuals=a.actuals, years=a.years, from_file=a.from_file, dry_run=a.dry_run)
    return code


if __name__ == "__main__":
    sys.exit(main())
