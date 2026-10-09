"""사실 묶음: 두 엔진에게 똑같이 주는 입력 파일을 DB에서 만든다. 숫자는 전부 코드가 넣는다.

    python -m pipeline.forecast.bundle --event CPI --ref 2026-09
    python -m pipeline.forecast.bundle --event CPI --ref 2026-09 --cutoff 2026-10-12T12:00:00Z

규칙
- 자료 마감 시각(cutoff)까지 '알려진' 값만 넣는다. 나중에 수정된 값이 섞이지 않는다.
- 맞혀야 할 값(그 발표의 기준 기간)은 넣지 않는다. 이미 DB에 있으면(발표가 지났으면) 만들지 않는다.
- 제목 대조가 맞은 계열만 넣는다(--allow-unverified 로 풀 수 있지만 기록에 남는다).
- 같은 DB·같은 마감 시각이면 항상 같은 파일, 같은 해시가 나온다. 해시는 봉인 기록에 들어간다.
- 시장 예상치, 기사, 웹 검색 결과는 넣지 않는다 (D18).
- 전월비·전년비는 발표값(소수 첫째 자리)과 함께, 발표된 지수로 다시 계산한 소수 둘째 자리 값도 넣는다(형식 0.2, D34).
  0.24 와 0.16 은 발표값으로는 같은 0.2 다. 맞힐 값과 기준선은 발표값 그대로다.
"""
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from ..collect import catalog as C
from ..collect import store
from . import targets as T

SPEC = "0.2"
HISTORY_MONTHS = 36
COMPONENT_MONTHS = 13
UNITS = {"pc1": "%", "pc12": "%"}


def setup_console():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except Exception:
            pass


def _period(obs_date):
    return obs_date[:7]


def _prev_period(period, months=1):
    y, m = int(period[:4]), int(period[5:7])
    idx = y * 12 + (m - 1) - months
    return "%04d-%02d" % (idx // 12, idx % 12 + 1)


def _tail(rows, ref_period, n):
    """기준 기간보다 앞선 값 가운데 최근 n개. [{"period", "value"}]"""
    picked = [{"period": _period(d), "value": v} for d, v in rows if _period(d) < ref_period]
    return picked[-n:]


def _fine(con, bls_id, kind, cutoff):
    """발표된 지수로 다시 계산한 전월비(pc1)·전년비(pc12), 소수 둘째 자리. {기간: 값}. 비교할 달의 지수가 없으면 그 달은 만들지 않는다."""
    lag = 12 if kind == "pc12" else 1
    level = {_period(d): v for d, v in store.asof(con, C.series_id(bls_id), cutoff)}
    out = {}
    for p, v in level.items():
        old = level.get(_prev_period(p, lag))
        if old:
            out[p] = float(((Decimal(repr(v)) / Decimal(repr(old)) - 1) * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    return out


def _verified(con, sid, allow_unverified):
    base = ".".join(sid.split(".")[:2])
    status = (store.get_meta(con, "series_check." + base) or "unknown").split("\t")[0]
    return status == "ok" or (allow_unverified and status == "unknown"), status


def build(con, event_kind, ref_period, cutoff, release_at_utc=None, allow_unverified=False):
    """(묶음 dict, 문제 목록). 문제가 있으면 묶음은 None."""
    if event_kind not in C.RELATED:
        return None, ["%s 묶음은 아직 만들 수 없습니다(수집기 없음)" % event_kind]
    if not T.ref_period_ok(event_kind, ref_period):
        return None, ["기준 기간 표기가 맞지 않음: %r" % ref_period]
    problems, used, skipped = [], [], []
    tlist = [t for t, v in T.TARGETS.items() if v[0] == event_kind and t in C.TARGET_SERIES]
    targets, history, history_fine = [], {}, {}
    for t in tlist:
        sid = C.target_series_id(t)
        ok, status = _verified(con, sid, allow_unverified)
        if not ok:
            problems.append("%s: 대상 계열(%s)의 제목 대조가 %s 입니다" % (t, sid, status))
            continue
        rows = store.asof(con, sid, cutoff)
        if any(_period(d) >= ref_period for d, _ in rows):
            problems.append("%s: 기준 기간(%s)의 값이 이미 알려져 있습니다. 발표 뒤에는 묶음을 만들지 않습니다" % (t, ref_period))
            continue
        hist = _tail(rows, ref_period, HISTORY_MONTHS)
        if not hist:
            problems.append("%s: 과거 값이 없습니다. 수집을 먼저 돌리세요" % t)
            continue
        last = hist[-1]
        note = "" if last["period"] == _prev_period(ref_period) else "직전 달 값이 비어 있어 그보다 앞선 값입니다"
        targets.append({"target": t, "name": T.TARGETS[t][1], "unit": T.TARGETS[t][2], "decimals": T.TARGETS[t][3],
                        "prev": dict(last, note=note)})
        history[t] = hist
        used.append(sid)
        bls_id, kind = C.TARGET_SERIES[t]
        if kind in ("pc1", "pc12"):   # 같은 기간들의 소수 둘째 자리 값(지수로 계산)
            fine = _fine(con, bls_id, kind, cutoff)
            history_fine[t] = [{"period": h["period"], "value": fine[h["period"]]} for h in hist if h["period"] in fine]
            used.append(C.series_id(bls_id))
    if problems:
        return None, problems

    def group_block(group, months):
        block = []
        for bls_id, g, name_ko, unit, keywords, derived in C.BLS:
            if g != group:
                continue
            kinds = [k for k in derived if k in ("pc1", "nc1")] or [""]
            sid = C.series_id(bls_id, kinds[0])
            ok, status = _verified(con, sid, allow_unverified)
            if not ok:
                skipped.append("%s(%s)" % (sid, status))
                continue
            source = sorted(_fine(con, bls_id, "pc1", cutoff).items()) if kinds[0] == "pc1" else store.asof(con, sid, cutoff)
            rows = _tail(source, "9999-99" if group != event_kind else ref_period, months)
            if rows:
                label = {"pc1": "전월비 % (지수로 계산, 소수 둘째 자리)", "nc1": "전월 대비 증감 (" + unit + ")", "": unit}[kinds[0]]
                block.append({"series": bls_id, "name": name_ko, "measure": label, "values": rows})
                used.append(C.series_id(bls_id) if kinds[0] == "pc1" else sid)
        return block

    bundle = {
        "bundle_spec": "%s/%s" % (event_kind, SPEC),
        "event": {"kind": event_kind, "title": T.EVENTS[event_kind][0], "ref_period": ref_period, "release_at_utc": release_at_utc},
        "data_cutoff_utc": cutoff,
        "targets": targets,
        "history": history,
        "history_fine": history_fine,
        "components": group_block(event_kind, COMPONENT_MONTHS),
        "related": {g: group_block(g, COMPONENT_MONTHS) for g in C.RELATED[event_kind]},
        "notes": ["모든 값은 자료 마감 시각까지 알려진 발표값이거나, 그 발표값으로 계산한 값입니다.", "기준 기간의 값은 들어 있지 않습니다.",
                  "전월비·전년비의 발표값은 소수 첫째 자리로 반올림되어 나옵니다. '지수로 계산'이라고 적힌 소수 둘째 자리 값은 발표된 지수로 같은 식을 다시 계산한 것입니다.",
                  "시장 예상치·기사·웹 검색 결과는 들어 있지 않습니다."],
    }
    if event_kind == "CPI":   # 전년비를 따질 재료: 원계열 지수의 직전 달·작년 같은 달 수준, 같은 달의 과거 전월비
        base = {}
        for bls_id in ("CUUR0000SA0", "CUUR0000SA0L1E"):
            ok, _ = _verified(con, C.series_id(bls_id), allow_unverified)
            if not ok:
                continue
            level = {_period(d): v for d, v in store.asof(con, C.series_id(bls_id), cutoff)}
            mom = _fine(con, bls_id, "pc1", cutoff)   # 원계열 전월비도 소수 둘째 자리로
            same_month = [{"period": p, "value": v} for p, v in sorted(mom.items()) if p[5:7] == ref_period[5:7] and p < ref_period][-5:]
            base[bls_id] = {"index_prev_month": {"period": _prev_period(ref_period), "value": level.get(_prev_period(ref_period))},
                            "index_same_month_last_year": {"period": _prev_period(ref_period, 12), "value": level.get(_prev_period(ref_period, 12))},
                            "nsa_mom_same_month_past_years": same_month}
            used.append(C.series_id(bls_id))
        bundle["yoy_ingredients"] = base
    bundle["coverage"] = {"series_used": sorted(set(used)), "series_skipped": sorted(set(skipped)), "allow_unverified": bool(allow_unverified)}
    return bundle, []


def dumps(bundle):
    return (json.dumps(bundle, ensure_ascii=False, sort_keys=True, indent=1) + "\n").encode("utf-8")


def lookup_release(schedule_glob, event_kind, ref_period):
    """일정표에서 그 발표의 시각(UTC 글). 시각을 읽을 수 없는 줄은 건너뛴다(예약 작업의 예정과 같은 줄을 쓰도록). 없으면 None."""
    import csv
    import glob
    for path in sorted(glob.glob(schedule_glob)):
        with open(path, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                if r.get("event_kind") == event_kind and r.get("ref_period") == ref_period:
                    try:
                        datetime.strptime(r.get("release_at_utc") or "", "%Y-%m-%dT%H:%M:%SZ")
                    except ValueError:
                        continue
                    return r["release_at_utc"]
    return None


def main(argv=None):
    setup_console()
    ap = argparse.ArgumentParser(description="사실 묶음 만들기")
    ap.add_argument("--event", required=True)
    ap.add_argument("--ref", required=True, help="기준 기간 (예: 2026-09)")
    ap.add_argument("--cutoff", default=None, help="자료 마감 시각 UTC (기본: 지금)")
    ap.add_argument("--db", default=store.DEFAULT_DB)
    ap.add_argument("--schedule", default=os.path.join(store.ROOT, "data", "forecast", "schedule_*.csv"))
    ap.add_argument("--out-dir", default=os.path.join(store.ROOT, "data", "private", "forecast", "bundles"))
    ap.add_argument("--allow-unverified", action="store_true", help="제목 대조를 못 한 계열도 넣는다(불일치는 여전히 뺀다)")
    a = ap.parse_args(argv)

    cutoff = a.cutoff or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if not os.path.exists(a.db):
        print("[중단] DB가 없습니다. 수집을 먼저 돌리세요: python -m pipeline.collect.bls")
        return 2
    con = store.connect(a.db)
    bundle, problems = build(con, a.event, a.ref, cutoff, lookup_release(a.schedule, a.event, a.ref), a.allow_unverified)
    con.close()
    if problems:
        print("[중단] 묶음을 만들지 않았습니다:")
        for p in problems:
            print("   - " + p)
        return 2
    data = dumps(bundle)
    digest = hashlib.sha256(data).hexdigest()
    os.makedirs(a.out_dir, exist_ok=True)
    path = os.path.join(a.out_dir, "%s_%s_%s.json" % (a.event, a.ref, cutoff.replace(":", "").replace("-", "")))
    with open(path, "wb") as f:
        f.write(data)
    cov = bundle["coverage"]
    print("묶음: %s" % path)
    print("대상 %d개 / 계열 %d개 사용 / %d개 제외 / 크기 %d바이트" % (len(bundle["targets"]), len(cov["series_used"]), len(cov["series_skipped"]), len(data)))
    for t in bundle["targets"]:
        print("   %s 직전 값(%s) = %s %s %s" % (t["target"], t["prev"]["period"], t["prev"]["value"], t["unit"], t["prev"]["note"]))
    if cov["series_skipped"]:
        print("   제외: " + ", ".join(cov["series_skipped"]))
    print("sha256 %s" % digest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
