"""장부가 손대지 않은 그대로인지 확인한다.

실행 (프로젝트 루트에서):
    python -m pipeline.ledger.verify                 장부 전체 점검
    python -m pipeline.ledger.verify --reveal 파일    공개된 원문 한 건을 장부와 대조

점검 내용: 순번, 앞 기록과의 연결(prev), 기록 해시, 봉인 파일의 해시,
그리고 비공개 원문이 있으면 원문+nonce가 봉인 해시와 맞는지.
"""
import argparse
import glob
import json
import os
import re
import sys

from . import core
from .commit import ROOT, read_private, setup_console


def main(argv=None):
    setup_console()
    ap = argparse.ArgumentParser(description="장부 점검")
    ap.add_argument("--ledger-dir", default=os.path.join(ROOT, "data", "ledger", "public"))
    ap.add_argument("--private-dir", default=os.path.join(ROOT, "data", "private", "ledger"))
    ap.add_argument("--reveal", default=None, help="공개 원문 파일(seq, nonce, payload 포함)")
    a = ap.parse_args(argv)

    entries = core.read_ledger(os.path.join(a.ledger_dir, "ledger.jsonl"))
    if not entries:
        print("장부가 비어 있습니다.")
        return 0
    problems = core.verify_chain(entries)
    by_seq = {e["seq"]: e for e in entries}

    checked = 0
    for e in entries:
        priv = read_private(a.private_dir, e) if os.path.isdir(a.private_dir) else None
        if priv is None:
            continue
        checked += 1
        if core.commit_hash(priv["nonce"], priv["payload"]) != e["commit"]:
            problems.append("seq %d: 비공개 원문이 봉인 해시와 다름" % e["seq"])

    seals = 0
    stamped = 0
    for path in sorted(glob.glob(os.path.join(a.ledger_dir, "seals", "seal_*.txt"))):
        seals += 1
        stamped += os.path.exists(path + ".ots")
        with open(path, encoding="utf-8") as f:
            m = re.search(r"seq=(\d+) .*head=([0-9a-f]{64})", f.read())
        if not m or int(m.group(1)) not in by_seq or by_seq[int(m.group(1))]["entry_hash"] != m.group(2):
            problems.append("봉인 파일이 장부와 다름: %s" % os.path.basename(path))

    if a.reveal:
        with open(a.reveal, encoding="utf-8") as f:
            doc = json.load(f)
        e = by_seq.get(doc.get("seq"))
        if e is None:
            problems.append("공개 원문의 seq %r 가 장부에 없음" % doc.get("seq"))
        elif core.commit_hash(doc["nonce"], doc["payload"]) != e["commit"]:
            problems.append("공개 원문이 seq %d 의 봉인 해시와 다름" % e["seq"])
        else:
            print("공개 원문 seq %d: 봉인 해시와 일치" % e["seq"])

    print("기록 %d건 / 원문 대조 %d건 / 봉인 %d건 (타임스탬프 %d건)" % (len(entries), checked, seals, stamped))
    if problems:
        print("[문제 %d건]" % len(problems))
        for p in problems:
            print("   - " + p)
        return 1
    print("이상 없음. 마지막 해시 %s" % entries[-1]["entry_hash"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
