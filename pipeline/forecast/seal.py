"""예측을 발표 전에 장부에 봉인한다. 발표 한 번 = 장부 기록 한 건.

    python -m pipeline.forecast.seal --file 예측파일.json

예측 파일(엔진 실행기가 만든다. 형식은 pipeline/forecast/README.md):
{
  "event": {"kind": "CPI", "ref_period": "2026-09", "release_at_utc": "2026-10-14T12:30:00Z"},
  "data_cutoff_utc": "2026-10-12T15:00:00Z",        <- 엔진들이 본 자료의 마감 시각(모든 엔진 동일)
  "bundle_sha256": "...",                           <- 엔진들에게 준 사실 묶음의 해시(모든 엔진 동일)
  "forecasts": [
    {"engine": "adler", "version": "1", "target": "CPI_MOM", "p10": 0.2, "p50": 0.3, "p90": 0.4, "n_runs": 5},
    {"engine": "prev", "target": "CPI_MOM", "p50": 0.4}      <- 기준선(직전 발표값 그대로)
  ]
}

막는 것
- 발표 시각이 지났거나 마감(기본: 발표 12시간 전)을 넘긴 봉인
- 등록되지 않은 엔진·버전, 등록 뒤 레시피 폴더가 바뀐 엔진
- 같은 발표·같은 엔진·같은 지표의 두 번째 봉인 (예측은 고쳐 내지 않는다)
- 기준선이 빠진 지표, p10 <= p50 <= p90 이 아닌 값, 발표 자릿수보다 두 자리 이상 잘게 쓴 값
엔진이 낸 값은 사람이 고치지 않는다. 형식이 틀리면 고치지 말고 실행기를 고쳐 다시 받는다.
"""
import argparse
import json
import os
import re
import secrets
import sys
from datetime import datetime, timedelta, timezone

from ..ledger import core
from ..ledger.commit import ROOT, make_entry, read_private, seal, setup_console, write_private
from . import engine as E
from . import targets as T

UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def parse_utc(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def too_fine(value, places):
    """발표 자릿수보다 한 자리까지만 더 잘게 허용한다."""
    return abs(round(float(value), places + 1) - float(value)) > 1e-9


def validate(doc, reg, engines_dir, now, min_lead_hours):
    """문제 목록과 정리된 payload 조각을 돌려준다."""
    errs = []
    ev = doc.get("event") or {}
    kind, ref, rel = ev.get("kind"), ev.get("ref_period"), ev.get("release_at_utc")
    if kind not in T.EVENTS:
        return ["event.kind 가 대상 목록에 없음: %r" % kind], None
    if not T.ref_period_ok(kind, ref):
        errs.append("event.ref_period 표기가 맞지 않음: %r" % ref)
    if not (isinstance(rel, str) and UTC_RE.match(rel)):
        return errs + ["event.release_at_utc 는 2026-10-14T12:30:00Z 형식(UTC)"], None
    lead = (parse_utc(rel) - now).total_seconds() / 3600.0
    if lead <= 0:
        errs.append("발표 시각이 이미 지났습니다. 봉인하지 않습니다.")
    elif lead < min_lead_hours:
        errs.append("봉인 마감(발표 %g시간 전)을 넘겼습니다. 남은 시간 %.1f시간." % (min_lead_hours, lead))
    for k in ("data_cutoff_utc",):
        if not (isinstance(doc.get(k), str) and UTC_RE.match(doc[k])):
            errs.append("%s 가 없거나 형식이 다름" % k)
    if isinstance(doc.get("data_cutoff_utc"), str) and UTC_RE.match(doc["data_cutoff_utc"]) and parse_utc(doc["data_cutoff_utc"]) > now:
        errs.append("data_cutoff_utc 가 지금보다 뒤입니다.")
    if not re.match(r"^[0-9a-f]{64}$", str(doc.get("bundle_sha256", ""))):
        errs.append("bundle_sha256 이 없거나 형식이 다름 (사실 묶음 파일의 sha256)")

    fcs = doc.get("forecasts") or []
    if not fcs:
        errs.append("forecasts 가 비어 있음")
    seen, clean, engine_targets, base_targets = set(), [], set(), set()
    for i, fc in enumerate(fcs, 1):
        name, target = fc.get("engine"), fc.get("target")
        tag = "forecasts[%d] %s/%s" % (i, name, target)
        if target not in T.TARGETS or T.TARGETS[target][0] != kind:
            errs.append("%s: 이 발표(%s)의 지표가 아님" % (tag, kind))
            continue
        places = T.decimals(target)
        if not isinstance(fc.get("p50"), (int, float)) or isinstance(fc.get("p50"), bool):
            errs.append("%s: p50 이 숫자가 아님" % tag)
            continue
        if name in T.BASELINES:
            if fc.get("p10") is not None or fc.get("p90") is not None:
                errs.append("%s: 기준선에는 구간을 쓰지 않음" % tag)
            ver = ""
            base_targets.add(target)
            item = {"engine": name, "version": ver, "target": target, "p50": fc["p50"]}
        else:
            ver = str(fc.get("version", ""))
            if (name, ver) not in reg:
                errs.append("%s: 등록되지 않은 엔진·버전 (%s@%s)" % (tag, name, ver))
                continue
            lo, hi = fc.get("p10"), fc.get("p90")
            if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (lo, hi)):
                errs.append("%s: p10·p90 이 없음" % tag)
                continue
            if not (lo <= fc["p50"] <= hi):
                errs.append("%s: p10 <= p50 <= p90 이 아님" % tag)
            if any(too_fine(v, places) for v in (lo, fc["p50"], hi)):
                errs.append("%s: 발표 자릿수(소수 %d자리)보다 두 자리 이상 잘게 씀" % (tag, places))
            folder = os.path.join(engines_dir, name, "v" + ver)
            if os.path.isdir(folder):
                if E.recipe_hash(folder)[0] != reg[(name, ver)]["recipe_sha256"]:
                    errs.append("%s: 레시피 폴더가 등록 때와 다름 (%s). 바꿨다면 새 버전으로 등록" % (tag, folder))
            else:
                errs.append("%s: 레시피 폴더를 찾지 못함 (%s)" % (tag, folder))
            engine_targets.add(target)
            item = {"engine": name, "version": ver, "target": target, "p10": lo, "p50": fc["p50"], "p90": hi,
                    "n_runs": int(fc.get("n_runs", 1))}
            if isinstance(fc.get("runs"), list):
                item["runs"] = fc["runs"]
        if (name, ver, target) in seen:
            errs.append("%s: 파일 안에서 중복" % tag)
        seen.add((name, ver, target))
        clean.append(item)
    for t in sorted(engine_targets - base_targets):
        errs.append("%s: 기준선(prev)이 빠짐" % t)
    if not engine_targets and not errs:
        errs.append("엔진 예측이 하나도 없음 (기준선만 있음)")
    payload = {"event": {"kind": kind, "ref_period": ref, "release_at_utc": rel},
               "data_cutoff_utc": doc.get("data_cutoff_utc"), "bundle_sha256": doc.get("bundle_sha256"),
               "forecasts": clean, "lead_hours": round(lead, 1)}
    if isinstance(doc.get("bundle_spec"), str):
        payload["bundle_spec"] = doc["bundle_spec"]   # 사실 묶음의 형식 버전 (pipeline/forecast/bundle.py)
    if isinstance(doc.get("execution"), dict):
        payload["execution"] = doc["execution"]       # 실행기가 남기는 기록: 보낸 글의 해시, 응답한 모델, 맞는 답의 수 (pipeline/forecast/runner.py). 원문에만 남는다
    return errs, payload


def already_sealed(entries, private_dir, kind, ref):
    """같은 발표에 대해 이미 봉인된 (엔진, 버전, 지표) -> 가운데 값. 원문이 없으면 공개 기록의 목록으로 판단한다(값은 None)."""
    done = {}
    for e in entries:
        if e.get("kind") != "forecast" or e.get("event_kind") != kind or e.get("ref_period") != ref:
            continue
        priv = read_private(private_dir, e)
        if priv:
            for fc in priv["payload"]["forecasts"]:
                done[(fc["engine"], str(fc.get("version", "")), fc["target"])] = fc["p50"]
        else:
            for tag in e.get("engines", []):
                name, _, ver = tag.partition("@")
                for t in e.get("targets", []):
                    done.setdefault((name, ver, t), None)
    return done


def main(argv=None, now=None):
    setup_console()
    ap = argparse.ArgumentParser(description="예측을 발표 전에 장부에 봉인")
    ap.add_argument("--file", required=True, help="예측 파일(JSON)")
    ap.add_argument("--ledger-dir", default=os.path.join(ROOT, "data", "ledger", "public"))
    ap.add_argument("--private-dir", default=os.path.join(ROOT, "data", "private", "ledger"))
    ap.add_argument("--engines-dir", default=os.path.join(ROOT, "data", "private", "engines"))
    ap.add_argument("--min-lead-hours", type=float, default=12.0, help="봉인 마감: 발표 몇 시간 전까지 (기본 12, 그보다 작게는 안 됨)")
    ap.add_argument("--no-ots", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    now = now or datetime.now(timezone.utc)
    if a.min_lead_hours < 12.0:   # 마감은 당길 수만 있다. 발표 12시간 전보다 늦게 봉인하는 길을 두지 않는다 (docs/12 §6)
        print("[중단] 봉인 마감은 발표 12시간 전보다 늦출 수 없습니다 (--min-lead-hours 는 12 이상).")
        return 2

    with open(a.file, encoding="utf-8-sig") as f:
        doc = json.load(f)
    ledger_path = os.path.join(a.ledger_dir, "ledger.jsonl")
    entries = core.read_ledger(ledger_path)
    problems = core.verify_chain(entries)
    if problems:
        print("[중단] 기존 장부에 문제가 있습니다. 쓰지 않고 멈춥니다:")
        for p in problems:
            print("   - " + p)
        return 1
    errs, part = validate(doc, E.registered(entries), a.engines_dir, now, a.min_lead_hours)
    if part:
        done = already_sealed(entries, a.private_dir, part["event"]["kind"], part["event"]["ref_period"])
        for fc in part["forecasts"]:
            key = (fc["engine"], fc["version"], fc["target"])
            if key not in done:
                continue
            if fc["engine"] in T.BASELINES:   # 나중에 등록한 엔진을 같은 발표에 추가할 때 기준선은 같은 값으로 다시 들어온다
                if done[key] is not None and abs(float(done[key]) - float(fc["p50"])) > 1e-9:
                    errs.append("%s/%s: 먼저 봉인된 기준선 값(%s)과 다름" % (fc["engine"], fc["target"], done[key]))
                continue
            errs.append("%s@%s/%s: 이 발표에 이미 봉인되어 있음. 예측은 고쳐 내지 않습니다." % key)
    if errs:
        print("[중단] 봉인하지 않았습니다:")
        for p in errs:
            print("   - " + p)
        return 2

    asof = (now + timedelta(hours=9)).strftime("%Y-%m-%d")   # 봉인한 날(한국 날짜). 장부 공통 필드 이름이 week_asof 라 그대로 쓴다
    payload = dict(part, schema=core.SCHEMA, kind="forecast", week_asof=asof)
    ev = payload["event"]
    engines = sorted({("%s@%s" % (fc["engine"], fc["version"])) if fc["version"] else fc["engine"] for fc in payload["forecasts"]})
    tlist = sorted({fc["target"] for fc in payload["forecasts"]})
    print("발표: %s %s (%s UTC, 남은 시간 %.1f시간)" % (ev["kind"], ev["ref_period"], ev["release_at_utc"], payload["lead_hours"]))
    print("예측 값 %d개 — %s / 지표 %s" % (len(payload["forecasts"]), ", ".join(engines), ", ".join(tlist)))
    if a.dry_run:
        print("--dry-run: 아무것도 쓰지 않았습니다.")
        return 0
    nonce = secrets.token_hex(16)
    prev = entries[-1]["entry_hash"] if entries else core.ZERO
    extra = {"event_kind": ev["kind"], "ref_period": ev["ref_period"], "release_at": ev["release_at_utc"],
             "n_forecasts": len(payload["forecasts"]), "engines": engines, "targets": tlist, "lead_hours": payload["lead_hours"]}
    e = make_entry(len(entries) + 1, "forecast", asof, payload, prev, nonce, extra)
    write_private(a.private_dir, e, nonce, payload, os.path.basename(a.file))
    core.append_entry(ledger_path, e)
    _, info = seal(a.ledger_dir, e, not a.no_ots)
    print("기록 #%d (예측 봉인). 봉인: %s" % (e["seq"], info))
    return 0


if __name__ == "__main__":
    sys.exit(main())
