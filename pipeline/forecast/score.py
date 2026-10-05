"""채점. 표준 라이브러리만 사용.

    python -m pipeline.forecast.score            장부에 봉인된 예측을 발표값과 대조해 채점

- 예측 원문: data/private/ledger/ 의 forecast 기록 (봉인 시각이 발표 시각보다 앞선 것만 채점)
- 발표값:   data/forecast/actuals.csv  (한 줄 = 한 값. 수정치는 줄을 덧붙이고, 채점은 처음 알게 된 값으로 한다)
- 결과:     data/private/forecast/scores.csv  (공개 형태를 정하기 전까지 내부용)

보는 것: 가운데 값의 오차, 구간(p10~p90) 안에 들어왔는지, 구간 점수(좁고 맞을수록 작다), 같은 발표에서 기준선과의 비교.
단위가 다른 지표의 오차를 한 숫자로 합치지 않는다.
"""
import argparse
import csv
import os
import sys

from ..ledger import core
from ..ledger.commit import ROOT, read_private, setup_console
from . import targets as T

ACTUAL_FIELDS = ["event_kind", "ref_period", "target", "actual", "released_at_utc", "source_url", "known_at_utc", "note"]
SCORE_FIELDS = ["seq", "event_kind", "ref_period", "target", "engine", "version", "p10", "p50", "p90",
                "actual", "abs_error", "in_interval", "interval_score", "sealed_at", "released_at"]


def abs_error(p50, actual):
    return abs(float(p50) - float(actual))


def in_interval(p10, p90, actual):
    return float(p10) <= float(actual) <= float(p90)


def interval_score(p10, p90, actual, coverage=T.INTERVAL):
    """구간 점수(Winkler). 폭 + 벗어난 거리 x (2/알파). 작을수록 좋다."""
    lo, hi, y, alpha = float(p10), float(p90), float(actual), 1.0 - coverage
    s = hi - lo
    if y < lo:
        s += (2.0 / alpha) * (lo - y)
    elif y > hi:
        s += (2.0 / alpha) * (y - hi)
    return s


def load_actuals(path):
    """(target, ref_period) -> 처음 알게 된 발표값 한 줄."""
    first = {}
    if not os.path.exists(path):
        return first
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if not (r.get("target") and r.get("actual")):
                continue
            k = (r["target"].strip(), r["ref_period"].strip())
            if k not in first or (r.get("known_at_utc") or "") < (first[k].get("known_at_utc") or ""):
                first[k] = r
    return first


def collect_forecasts(entries, private_dir):
    """장부의 forecast 기록 원문을 펼친다. 원문이 없는 기록은 건너뛴다."""
    rows, missing = [], 0
    for e in entries:
        if e.get("kind") != "forecast":
            continue
        priv = read_private(private_dir, e)
        if priv is None or core.commit_hash(priv["nonce"], priv["payload"]) != e["commit"]:
            missing += 1
            continue
        p = priv["payload"]
        for fc in p["forecasts"]:
            rows.append({"seq": e["seq"], "event_kind": p["event"]["kind"], "ref_period": p["event"]["ref_period"],
                         "released_at": p["event"]["release_at_utc"], "sealed_at": e["committed_at"],
                         "target": fc["target"], "engine": fc["engine"], "version": str(fc.get("version", "")),
                         "p10": fc.get("p10"), "p50": fc["p50"], "p90": fc.get("p90")})
    return rows, missing


def score_rows(rows, actuals):
    out, late = [], 0
    for r in rows:
        a = actuals.get((r["target"], r["ref_period"]))
        if a is None:
            continue
        if not (r["sealed_at"] < r["released_at"]):   # 둘 다 UTC "YYYY-MM-DDTHH:MM:SSZ"
            late += 1
            continue
        y = float(a["actual"])
        s = dict(r, actual=y, abs_error=round(abs_error(r["p50"], y), 6), in_interval="", interval_score="")
        if r["p10"] is not None and r["p90"] is not None:
            s["in_interval"] = int(in_interval(r["p10"], r["p90"], y))
            s["interval_score"] = round(interval_score(r["p10"], r["p90"], y), 6)
        out.append(s)
    return out, late


def summarize(scored):
    """엔진 버전별 요약과 지표별 요약. 기준선(prev)과는 같은 발표·같은 지표끼리만 비교한다."""
    base = {(s["target"], s["ref_period"]): s for s in scored if s["engine"] == "prev"}
    by_engine, by_target = {}, {}
    for s in scored:
        if s["engine"] in T.BASELINES:
            continue
        key = "%s@%s" % (s["engine"], s["version"])
        e = by_engine.setdefault(key, {"values": 0, "events": set(), "hit": 0, "with_interval": 0,
                                       "closer": 0, "same": 0, "farther": 0})
        e["values"] += 1
        e["events"].add((s["event_kind"], s["ref_period"]))
        if s["in_interval"] != "":
            e["with_interval"] += 1
            e["hit"] += s["in_interval"]
        t = by_target.setdefault((key, s["target"]), {"n": 0, "err": 0.0, "base_n": 0, "base_err": 0.0, "pair_err": 0.0})
        t["n"] += 1
        t["err"] += s["abs_error"]
        b = base.get((s["target"], s["ref_period"]))
        if b is not None:
            t["base_n"] += 1
            t["base_err"] += b["abs_error"]
            t["pair_err"] += s["abs_error"]
            d = s["abs_error"] - b["abs_error"]
            e["closer" if d < -1e-9 else "farther" if d > 1e-9 else "same"] += 1
    return by_engine, by_target


def print_summary(by_engine, by_target):
    if not by_engine:
        print("채점된 엔진 예측이 아직 없습니다.")
        return
    for key in sorted(by_engine):
        e = by_engine[key]
        n_ev = len(e["events"])
        flag = "" if n_ev >= T.MIN_SCORED_EVENTS else "  [표본 부족: 발표 %d회 미만]" % T.MIN_SCORED_EVENTS
        print("%s — 발표 %d회, 값 %d개%s" % (key, n_ev, e["values"], flag))
        if e["with_interval"]:
            print("   구간 적중 %d/%d (%.0f%%, 목표 %.0f%%)" % (e["hit"], e["with_interval"],
                  100.0 * e["hit"] / e["with_interval"], 100 * T.INTERVAL))
        print("   기준선(직전 값)보다 오차가 작음 %d / 같음 %d / 큼 %d" % (e["closer"], e["same"], e["farther"]))
        for (k, target) in sorted(by_target):
            if k != key:
                continue
            t = by_target[(k, target)]
            line = "   %-13s n=%d 평균 오차 %.3f %s" % (target, t["n"], t["err"] / t["n"], T.TARGETS[target][2])
            if t["base_n"]:
                line += " (같은 발표의 기준선 %.3f)" % (t["base_err"] / t["base_n"])
            print(line)


def main(argv=None):
    setup_console()
    ap = argparse.ArgumentParser(description="봉인된 예측 채점")
    ap.add_argument("--ledger-dir", default=os.path.join(ROOT, "data", "ledger", "public"))
    ap.add_argument("--private-dir", default=os.path.join(ROOT, "data", "private", "ledger"))
    ap.add_argument("--actuals", default=os.path.join(ROOT, "data", "forecast", "actuals.csv"))
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "private", "forecast", "scores.csv"))
    a = ap.parse_args(argv)

    entries = core.read_ledger(os.path.join(a.ledger_dir, "ledger.jsonl"))
    problems = core.verify_chain(entries)
    if problems:
        print("[중단] 장부에 문제가 있습니다:")
        for p in problems:
            print("   - " + p)
        return 1
    rows, missing = collect_forecasts(entries, a.private_dir)
    scored, late = score_rows(rows, load_actuals(a.actuals))
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SCORE_FIELDS, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        for s in scored:
            w.writerow({k: ("" if s.get(k) is None else s.get(k)) for k in SCORE_FIELDS})
    print("봉인된 예측 값 %d개 / 채점 %d개 / 발표 전(대기) %d개" % (len(rows), len(scored), len(rows) - len(scored) - late))
    if missing:
        print("원문이 없거나 맞지 않아 건너뛴 기록 %d건" % missing)
    if late:
        print("[주의] 발표 뒤에 봉인되어 채점에서 뺀 값 %d개" % late)
    print_summary(*summarize(scored))
    print("결과 파일: %s (내부용)" % a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
