"""엔진 등록. 엔진 = 이름 + 버전 + 기반 모델 + 레시피(프롬프트·설정 파일 묶음).

    python -m pipeline.forecast.engine register --name 이름 --version 1 --model 모델ID --dir data/private/engines/이름/v1
    python -m pipeline.forecast.engine list

- 레시피 폴더의 내용은 밖에 내지 않는다(비공개 로직). 장부에는 폴더 전체의 해시만 공개로 남는다.
  → 나중에 "그때 그 레시피 그대로였다"를 증명할 수 있고, 몰래 고치면 봉인 단계에서 걸린다.
- 레시피나 모델을 바꾸려면 새 버전을 먼저 등록한다. 성적은 버전별로 따로 센다.
- 이름에는 모델 회사·모델 이름을 넣지 않는다 (D18).
"""
import argparse
import os
import re
import secrets
import sys
from datetime import datetime, timedelta, timezone

from ..ledger import core
from ..ledger.commit import ROOT, make_entry, seal, setup_console, write_private

NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,23}$")
VENDOR_WORDS = ("claude", "anthropic", "gpt", "openai", "astra", "gemini", "google", "sonnet", "opus", "fable")
MODES = ("api", "manual")


def kst_today():
    return (datetime.now(timezone.utc) + timedelta(hours=9)).strftime("%Y-%m-%d")


def recipe_hash(folder):
    """폴더 안 모든 파일의 (상대 경로, 내용 해시) 목록을 해시한다. 파일이 하나라도 바뀌면 값이 달라진다."""
    items = []
    for base, dirs, files in os.walk(folder):
        dirs.sort()
        for name in sorted(files):
            if name.startswith(".") or name.endswith(".pyc"):
                continue
            path = os.path.join(base, name)
            with open(path, "rb") as f:
                digest = core.sha256_hex(f.read())
            items.append([os.path.relpath(path, folder).replace(os.sep, "/"), digest])
    items.sort()
    return core.sha256_hex(core.canonical(items)), items


def registered(entries):
    """장부에 등록된 엔진: (이름, 버전) -> 공개 기록."""
    return {(e["engine"], str(e["version"])): e for e in entries if e.get("kind") == "engine"}


def cmd_register(a):
    if not NAME_RE.match(a.name):
        print("[중단] 이름은 영문 소문자로 시작하는 2~24자(소문자·숫자·밑줄)로 적습니다. 화면에 보일 한글 이름은 --label 로.")
        return 2
    if any(w in a.name.lower() or w in (a.label or "").lower() for w in VENDOR_WORDS):
        print("[중단] 엔진 이름에 모델 회사·모델 이름을 넣지 않습니다 (D18).")
        return 2
    if not os.path.isdir(a.dir):
        print("[중단] 레시피 폴더가 없습니다: %s" % a.dir)
        return 2
    digest, files = recipe_hash(a.dir)
    if not files:
        print("[중단] 레시피 폴더가 비어 있습니다: %s" % a.dir)
        return 2
    ledger_path = os.path.join(a.ledger_dir, "ledger.jsonl")
    entries = core.read_ledger(ledger_path)
    problems = core.verify_chain(entries)
    if problems:
        print("[중단] 기존 장부에 문제가 있습니다. 쓰지 않고 멈춥니다:")
        for p in problems:
            print("   - " + p)
        return 1
    if not entries:
        print("[중단] 장부가 비어 있습니다. 기점 기록(ledger_commit.bat 첫 실행)이 먼저 있어야 합니다.")
        return 2
    if (a.name, str(a.version)) in registered(entries):
        print("[중단] %s 버전 %s 은 이미 등록되어 있습니다. 바꾸려면 새 버전 번호로 등록하세요." % (a.name, a.version))
        return 2
    asof = kst_today()
    payload = {"schema": core.SCHEMA, "kind": "engine", "week_asof": asof, "engine": a.name, "version": str(a.version),
               "label": a.label or a.name, "mode": a.mode, "model": a.model, "n_runs": a.n_runs,
               "recipe_sha256": digest, "recipe_files": files, "note": a.note or ""}
    nonce = secrets.token_hex(16)
    prev = entries[-1]["entry_hash"]
    e = make_entry(len(entries) + 1, "engine", asof, payload, prev, nonce,
                   {"engine": a.name, "version": str(a.version), "recipe_sha256": digest})
    write_private(a.private_dir, e, nonce, payload, os.path.basename(os.path.abspath(a.dir)))
    core.append_entry(ledger_path, e)
    _, info = seal(a.ledger_dir, e, not a.no_ots)
    print("기록 #%d: 엔진 %s 버전 %s 등록 (레시피 파일 %d개, 해시 %s)" % (e["seq"], a.name, a.version, len(files), digest[:16]))
    print("봉인: %s" % info)
    return 0


def cmd_list(a):
    entries = core.read_ledger(os.path.join(a.ledger_dir, "ledger.jsonl"))
    reg = registered(entries)
    if not reg:
        print("등록된 엔진이 없습니다.")
        return 0
    for (name, ver), e in sorted(reg.items()):
        print("%s 버전 %s — 기록 #%d, 등록 %s, 레시피 해시 %s" % (name, ver, e["seq"], e["committed_at"], e["recipe_sha256"][:16]))
    return 0


def main(argv=None):
    setup_console()
    ap = argparse.ArgumentParser(description="엔진 등록")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("register")
    r.add_argument("--name", required=True, help="영문 소문자 이름 (예: adler)")
    r.add_argument("--label", default=None, help="화면에 보일 이름 (예: 아들러)")
    r.add_argument("--version", required=True)
    r.add_argument("--model", required=True, help="기반 모델 ID. 비공개 원문에만 남는다")
    r.add_argument("--mode", choices=MODES, default="api", help="api=자동 호출 / manual=앱에 붙여 넣어 받은 값")
    r.add_argument("--n-runs", type=int, default=1, help="한 번 예측에 모델을 몇 번 돌려 합치는가")
    r.add_argument("--dir", required=True, help="레시피 폴더")
    r.add_argument("--note", default=None)
    r.add_argument("--no-ots", action="store_true")
    ls = sub.add_parser("list")
    for p in (r, ls):
        p.add_argument("--ledger-dir", default=os.path.join(ROOT, "data", "ledger", "public"))
        p.add_argument("--private-dir", default=os.path.join(ROOT, "data", "private", "ledger"))
    a = ap.parse_args(argv)
    return cmd_register(a) if a.cmd == "register" else cmd_list(a)


if __name__ == "__main__":
    sys.exit(main())
