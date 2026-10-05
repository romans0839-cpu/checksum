"""OpenTimestamps 캘린더 서버에 해시를 보내 타임스탬프 증명(.ots)을 받는다. 표준 라이브러리만 사용.

- 무료, 가입·키 불필요. 실패해도 장부 기록에는 영향이 없다(최선 노력).
- 받은 .ots는 '대기' 상태다. 몇 시간 뒤 비트코인 블록에 들어가며, 공식 도구로 완성한다:
      pip install opentimestamps-client
      ots upgrade <파일>.ots      (완성)
      ots verify  <파일>.ots      (검증)
- 파일 형식: MAGIC + 버전(1) + sha256 태그(0x08) + 파일 해시(32바이트) + 캘린더 응답
"""
import hashlib
import urllib.request

MAGIC = b"\x00OpenTimestamps\x00\x00Proof\x00\xbf\x89\xe2\xe8\x84\xe8\x92\x94"
CALENDARS = [
    "https://a.pool.opentimestamps.org",
    "https://b.pool.opentimestamps.org",
    "https://alice.btc.calendar.opentimestamps.org",
    "https://bob.btc.calendar.opentimestamps.org",
    "https://finney.calendar.eternitywall.com",
]


def frame(digest, calendar_response):
    return MAGIC + b"\x01" + b"\x08" + digest + calendar_response


def stamp_file(path, timeout=15):
    """path의 sha256을 캘린더에 제출하고 path + '.ots'를 쓴다. (성공 여부, 설명)을 돌려준다."""
    with open(path, "rb") as f:
        digest = hashlib.sha256(f.read()).digest()
    last = "캘린더 서버에 연결하지 못함"
    for cal in CALENDARS:
        req = urllib.request.Request(
            cal + "/digest", data=digest, method="POST",
            headers={"Accept": "application/vnd.opentimestamps.v1",
                     "Content-Type": "application/x-www-form-urlencoded",
                     "User-Agent": "checksum-ledger/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read(10001)
            if not body or len(body) > 10000:
                last = "%s: 응답 크기 이상" % cal
                continue
            with open(path + ".ots", "wb") as f:
                f.write(frame(digest, body))
            return True, cal
        except Exception as e:  # 네트워크 오류는 장부 기록을 막지 않는다
            last = "%s: %s" % (cal, e)
    return False, last
