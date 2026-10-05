"""장부 공통 함수. 표준 라이브러리만 사용 (Python 3.9+).

구조
- 공개 장부  data/ledger/public/ledger.jsonl   : 한 줄 = 한 기록. 내용은 없고 해시와 건수만.
- 비공개 원문 data/private/ledger/NNNNNN_*.json : 원문(payload)과 nonce. T+7 공개 전까지 밖에 내지 않는다.
- 봉인 파일  data/ledger/public/seals/*.txt(.ots): 그 시점 장부의 마지막 해시 + 외부 타임스탬프 증명.

검증 원리
- commit     = sha256(nonce + "\\n" + canonical(payload))   -> 원문을 나중에 공개하면 누구나 대조
- entry_hash = sha256(canonical(entry_hash를 뺀 기록))       -> 기록 자체의 위변조 탐지
- prev       = 직전 기록의 entry_hash                        -> 중간 삭제·순서 변경 탐지
"""
import hashlib
import json
import os
from datetime import datetime, timezone

SCHEMA = "checksum-ledger/0.1"
ZERO = "0" * 64


def canonical(obj):
    """키 정렬·공백 없는 JSON 문자열. 같은 내용이면 항상 같은 문자열이 나온다."""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_hex(data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def commit_hash(nonce_hex, payload):
    return sha256_hex(nonce_hex + "\n" + canonical(payload))


def entry_hash(entry):
    body = {k: v for k, v in entry.items() if k != "entry_hash"}
    return sha256_hex(canonical(body))


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_ledger(path):
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                raise SystemExit("장부 %d번째 줄을 읽을 수 없습니다: %s" % (n, path))
    return out


def append_entry(path, entry):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(canonical(entry) + "\n")


def verify_chain(entries):
    """문제 목록을 돌려준다. 빈 목록이면 정상."""
    problems = []
    prev = ZERO
    for i, e in enumerate(entries, 1):
        if e.get("seq") != i:
            problems.append("순번 불일치: %d번째 줄의 seq=%r" % (i, e.get("seq")))
        if e.get("prev") != prev:
            problems.append("seq %s: prev가 직전 기록의 해시와 다름" % e.get("seq"))
        if entry_hash(e) != e.get("entry_hash"):
            problems.append("seq %s: entry_hash 불일치 (기록이 수정됨)" % e.get("seq"))
        prev = e.get("entry_hash")
    return problems


def private_name(seq, kind, week_asof):
    return "%06d_%s_%s.json" % (seq, kind, week_asof)
