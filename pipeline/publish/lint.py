"""발행 전 문구 검사 — 금지어 검출 시 발행 차단, 필수 문구 누락 시 차단.

실행: python -m pipeline.publish.lint data/newsletters/drafts/2026-10-14.md
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BANNED = [l.strip() for l in (ROOT / "templates" / "banned_terms.txt").read_text(encoding="utf-8").splitlines()
          if l.strip() and not l.startswith("#")]
REQUIRED = ["원금 손실", "투자 판단", "신고번호"]


def check(text: str):
    problems = []
    for term in BANNED:
        if re.search(term, text):
            problems.append(f"금지어: {term}")
    for req in REQUIRED:
        if req not in text:
            problems.append(f"필수 문구 누락: {req}")
    return problems


if __name__ == "__main__":
    p = Path(sys.argv[1])
    issues = check(p.read_text(encoding="utf-8"))
    if issues:
        print("발행 차단:\n  " + "\n  ".join(issues))
        sys.exit(1)
    print("OK")
