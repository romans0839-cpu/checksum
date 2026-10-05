"""이번 주 신호를 장부에 봉인한다.

실행 (프로젝트 루트 C:\\usstock-sub 에서):
    python -m pipeline.ledger.commit
또는 ledger_commit.bat 더블클릭.

하는 일
1. 봇 폴더의 최신 라이브 신호 파일(signals/target_YYYYMMDD.json, 후보 A)을 읽는다. 봇 폴더는 읽기만 한다.
2. 장부가 비어 있으면 먼저 '기점 이전 보유 종목'(종목명만)을 1번 기록으로 남긴다.
3. 이번 주 신호(청산 종목, 진입 후보 전체와 순서, 주도 업종, 보유 종목명)를 봉인한다.
   공개 장부에는 해시와 건수만, 원문과 nonce는 data/private/ledger/ 에만 쓴다.
4. 그 시점 장부의 마지막 해시를 봉인 파일로 쓰고 외부 타임스탬프(.ots)를 받는다(실패해도 계속).
5. 새로 나온 진입 후보를 data/track_record/signals.csv 에 추가한다.

기록하지 않는 것: 수량, 계좌 금액, 가격, 지표 값 (decisions D3, 데이터 라이선스 docs/10).
같은 주에 다시 실행해도 중복 기록되지 않는다. 신호가 바뀐 경우에만 개정 기록이 추가된다.
"""
import argparse
import csv
import glob
import json
import os
import secrets
import sys

from . import core, ots

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CSV_FIELDS = ["signal_id", "ts_signal", "ts_exit", "system", "symbol", "side", "entry", "stop",
              "exit", "r_multiple", "outcome", "published_tier", "notes"]


def setup_console():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except Exception:
            pass


def default_bot_dir():
    return os.environ.get("CHECKSUM_BOT_DIR") or os.path.join(os.path.dirname(ROOT), "us_swing_bot")


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def find_source(bot_dir, explicit, allow_shadow):
    if explicit:
        return explicit
    live = sorted(glob.glob(os.path.join(bot_dir, "signals", "target_*.json")))
    if live:
        newest = live[-1]
        try:
            if str(load_json(newest).get("generator", "")).startswith("live_signal_a"):
                return newest
        except ValueError:
            pass
    if allow_shadow:
        shadow = sorted(glob.glob(os.path.join(bot_dir, "signals_shadow", "target_A_*.json")))
        if shadow:
            return shadow[-1]
    return None


def symbols_only(items):
    return [x["symbol"] if isinstance(x, dict) else str(x) for x in (items or [])]


def weekly_payload(src):
    ctx = src.get("context") or {}
    orders = src.get("orders") or {}
    entries = [{"rank": i, "symbol": e["symbol"], "group": e.get("group", "")}
               for i, e in enumerate(orders.get("entry") or [], 1)]
    return {
        "schema": core.SCHEMA,
        "kind": "weekly",
        "week_asof": src["asof_week"],
        "system": {"generator": src.get("generator"), "engine": src.get("engine"),
                   "params": src.get("params") or {}},
        "lead_groups": list(ctx.get("lead_groups_now") or []),
        "exits": symbols_only(orders.get("exit")),
        "entry_candidates": entries,
        "holdings": sorted(symbols_only(src.get("model_positions"))),
        "holdings_known": bool(ctx.get("holdings_known", True)),
        "cooldown": list(ctx.get("cooldown") or []),
    }


def genesis_payload(src):
    return {
        "schema": core.SCHEMA,
        "kind": "genesis",
        "week_asof": src["asof_week"],
        "note": "장부 기점 이전부터 보유한 종목. 성과 통계에서 제외한다.",
        "holdings": sorted(symbols_only(src.get("model_positions"))),
    }


def make_entry(seq, kind, week_asof, payload, prev, nonce, extra):
    entry = {"schema": core.SCHEMA, "seq": seq, "kind": kind, "week_asof": week_asof,
             "committed_at": core.utc_now(), "commit": core.commit_hash(nonce, payload), "prev": prev}
    entry.update(extra)
    entry["entry_hash"] = core.entry_hash(entry)
    return entry


def write_private(private_dir, entry, nonce, payload, source_name):
    os.makedirs(private_dir, exist_ok=True)
    path = os.path.join(private_dir, core.private_name(entry["seq"], entry["kind"], entry["week_asof"]))
    doc = {"seq": entry["seq"], "kind": entry["kind"], "week_asof": entry["week_asof"],
           "nonce": nonce, "payload": payload, "commit": entry["commit"], "source_file": source_name}
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return path


def read_private(private_dir, entry):
    path = os.path.join(private_dir, core.private_name(entry["seq"], entry["kind"], entry["week_asof"]))
    return load_json(path) if os.path.exists(path) else None


def seal(public_dir, head, use_ots):
    """마지막 기록의 해시를 봉인 파일로 쓰고 외부 타임스탬프를 시도한다."""
    seals = os.path.join(public_dir, "seals")
    os.makedirs(seals, exist_ok=True)
    path = os.path.join(seals, "seal_%06d.txt" % head["seq"])
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write("%s seq=%d week_asof=%s head=%s\n" % (core.SCHEMA, head["seq"], head["week_asof"], head["entry_hash"]))
    if not use_ots:
        return path, "타임스탬프 생략(--no-ots)"
    if os.path.exists(path + ".ots"):
        return path, "타임스탬프 있음"
    ok, info = ots.stamp_file(path)
    return path, ("타임스탬프 받음: " + info) if ok else ("타임스탬프 실패(다음 실행 때 다시 시도): " + info)


def append_signals_csv(csv_path, payload, seq):
    """아직 열려 있지 않은 진입 후보만 추가한다. 가격·결과는 체결 기준 확정 뒤에 채운다."""
    rows = []
    if os.path.exists(csv_path):
        with open(csv_path, encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
    open_syms = {r["symbol"] for r in rows if r.get("outcome") == "open"}
    known_ids = {r["signal_id"] for r in rows}
    engine = (payload["system"].get("engine") or "A")
    new = []
    for c in payload["entry_candidates"]:
        sid = "%s-%s-%s" % (engine, payload["week_asof"], c["symbol"])
        if c["symbol"] in open_syms or sid in known_ids:
            continue
        new.append({"signal_id": sid, "ts_signal": payload["week_asof"], "ts_exit": "", "system": engine,
                    "symbol": c["symbol"], "side": "long", "entry": "", "stop": "", "exit": "",
                    "r_multiple": "", "outcome": "open", "published_tier": "ledger",
                    "notes": "candidate rank=%d; ledger seq=%d" % (c["rank"], seq)})
    if new:
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=CSV_FIELDS, lineterminator="\n")
            w.writeheader()
            for r in rows + new:
                w.writerow({k: r.get(k, "") for k in CSV_FIELDS})
    return [r["symbol"] for r in new]


def main(argv=None):
    setup_console()
    ap = argparse.ArgumentParser(description="이번 주 신호를 장부에 봉인")
    ap.add_argument("--bot", default=default_bot_dir(), help="봇 폴더 (기본: 옆 폴더 us_swing_bot)")
    ap.add_argument("--file", default=None, help="신호 파일을 직접 지정")
    ap.add_argument("--ledger-dir", default=os.path.join(ROOT, "data", "ledger", "public"))
    ap.add_argument("--private-dir", default=os.path.join(ROOT, "data", "private", "ledger"))
    ap.add_argument("--signals-csv", default=os.path.join(ROOT, "data", "track_record", "signals.csv"))
    ap.add_argument("--allow-shadow", action="store_true", help="시험용: 라이브 파일이 없으면 섀도 신호 사용")
    ap.add_argument("--no-ots", action="store_true", help="외부 타임스탬프 생략")
    ap.add_argument("--dry-run", action="store_true", help="아무것도 쓰지 않고 내용만 표시")
    a = ap.parse_args(argv)

    src_path = find_source(a.bot, a.file, a.allow_shadow)
    if not src_path:
        print("[중단] 후보 A 라이브 신호 파일을 찾지 못했습니다: %s" % os.path.join(a.bot, "signals"))
        print("       화요일 신호 생성이 끝난 뒤 다시 실행하세요.")
        return 2
    src = load_json(src_path)
    src_hash = core.sha256_hex(core.canonical(src))
    asof = src["asof_week"]
    payload = weekly_payload(src)
    ledger_path = os.path.join(a.ledger_dir, "ledger.jsonl")
    entries = core.read_ledger(ledger_path)
    problems = core.verify_chain(entries)
    if problems:
        print("[중단] 기존 장부에 문제가 있습니다. 쓰지 않고 멈춥니다:")
        for p in problems:
            print("   - " + p)
        return 1

    print("신호 파일: %s" % src_path)
    print("기준 주 : %s (%s)" % (asof, src.get("generator")))
    print("청산 %d건 / 진입 후보 %d건 / 보유 %d종목 / 주도 업종 %d개"
          % (len(payload["exits"]), len(payload["entry_candidates"]), len(payload["holdings"]), len(payload["lead_groups"])))

    if a.dry_run:
        print("--dry-run: 아무것도 쓰지 않았습니다. 봉인될 원문:")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    written = []
    if not entries:
        g = genesis_payload(src)
        nonce = secrets.token_hex(16)
        e = make_entry(1, "genesis", asof, g, core.ZERO, nonce, {"n_holdings": len(g["holdings"])})
        write_private(a.private_dir, e, nonce, g, os.path.basename(src_path))
        core.append_entry(ledger_path, e)
        entries.append(e)
        written.append(e)
        print("기록 #1 (기점 이전 보유 %d종목, 통계 제외)" % len(g["holdings"]))

    same_week = [e for e in entries if e["kind"] == "weekly" and e["week_asof"] == asof]
    already = False
    if same_week:
        last = same_week[-1]
        priv = read_private(a.private_dir, last)
        if priv and core.commit_hash(priv["nonce"], payload) == last["commit"]:
            already = True
        elif last.get("source_sha256") == src_hash:
            already = True
    if already:
        print("이번 주(%s)는 이미 봉인되어 있습니다. 새로 쓰지 않습니다." % asof)
    else:
        nonce = secrets.token_hex(16)
        extra = {"n_exits": len(payload["exits"]), "n_entry_candidates": len(payload["entry_candidates"]),
                 "n_holdings": len(payload["holdings"]), "n_lead_groups": len(payload["lead_groups"]),
                 "source_generated_at": src.get("generated_at"), "source_sha256": src_hash}
        if same_week:
            extra["revision"] = len(same_week) + 1
        e = make_entry(len(entries) + 1, "weekly", asof, payload, entries[-1]["entry_hash"], nonce, extra)
        write_private(a.private_dir, e, nonce, payload, os.path.basename(src_path))
        core.append_entry(ledger_path, e)
        entries.append(e)
        written.append(e)
        print("기록 #%d (이번 주 신호%s)" % (e["seq"], ", 개정 %d" % extra["revision"] if same_week else ""))
        added = append_signals_csv(a.signals_csv, payload, e["seq"])
        print("signals.csv 추가: %s" % (", ".join(added) if added else "없음(새 후보 없음)"))

    head = entries[-1]
    seal_path, seal_info = seal(a.ledger_dir, head, not a.no_ots)
    print("봉인: %s" % seal_info)
    print("장부 %d건, 마지막 해시 %s" % (len(entries), head["entry_hash"][:16]))
    print("공개 장부 : %s" % ledger_path)
    print("비공개 원문: %s (밖에 내지 않음)" % a.private_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
