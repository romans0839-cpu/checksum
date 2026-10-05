"""고친 기록: 조종판에서 Nick이 고친 문장을 모아 '고친 기록' 탭에 적는다. 다음 초안의 말투 기준이 된다 (D17, docs/15 §5-4).

- 게시 대기열에서 상태가 승인·게시 중·게시됨인 줄만 본다. 고치는 중인 초안과 보류한 줄은 보지 않는다.
- '처음 문안'과 '본문'을 문장 단위로 견줘 달라진 곳만 남긴다: 바꿈 / 지움 / 더함 / 채움([채울 것: …]을 채운 것).
- 같은 고침은 한 번만 적는다(DB의 sns_edit). 탭에는 최근 것부터 적고, 한 칸은 짧게 자른다 —
  세션이 드라이브 도구로 시트를 읽을 때 긴 칸과 뒤쪽 줄이 잘리기 때문이다.
- 이 탭은 서버가 통째로 다시 쓴다. 사람이 고치는 자리가 아니다.
"""
import difflib
import re
from datetime import datetime, timedelta, timezone

from . import board as B

KST = timezone(timedelta(hours=9))
FINAL_STATES = (B.ST_OK, B.ST_POSTING, B.ST_DONE)
KIND_CHANGE, KIND_DELETE, KIND_ADD, KIND_FILL = "바꿈", "지움", "더함", "채움"
CELL_MAX = 220     # 한 칸의 글자 수. 이보다 길면 잘라 적는다
TAB_ROWS = 80      # 탭에 적는 최근 고침의 수
_SENT = re.compile(r"(?<=[.!?…])\s+")


def units(text):
    """글 -> 견줄 단위의 목록. 줄을 나누고, 긴 줄은 문장으로 다시 나눈다."""
    out = []
    for line in (text or "").replace("\r\n", "\n").split("\n"):
        line = line.strip()
        if not line:
            continue
        out.extend(p.strip() for p in _SENT.split(line) if p.strip())
    return out


def _pairs(olds, news):
    """바뀐 덩어리 안에서 어느 문장이 어느 문장으로 바뀌었는지 짝을 짓는다(순서를 지키며, 닮은 것끼리).
    돌려주는 값: [(처음 또는 None, 고친 뒤 또는 None)] — 짝이 없는 처음 문장은 지움, 짝이 없는 새 문장은 더함."""
    n, m = len(olds), len(news)
    sim = [[difflib.SequenceMatcher(None, a, b, autojunk=False).ratio() for b in news] for a in olds]
    for i, a in enumerate(olds):   # 채울 칸은 닮지 않아도 그 자리의 새 문장과 짝이 된다
        if "채울 것" in a:
            fixed = re.split(r"\[?\s*채울\s*것[^\]]*\]?", a)
            for j, b in enumerate(news):
                if all(part.strip() in b for part in fixed if part.strip()):
                    sim[i][j] = max(sim[i][j], 0.9)
    best = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            take = sim[i][j] + best[i + 1][j + 1] if sim[i][j] >= 0.4 else -1.0
            best[i][j] = max(take, best[i + 1][j], best[i][j + 1])
    out, i, j = [], 0, 0
    while i < n and j < m:
        if sim[i][j] >= 0.4 and best[i][j] == sim[i][j] + best[i + 1][j + 1]:
            out.append((olds[i], news[j]))
            i, j = i + 1, j + 1
        elif best[i][j] == best[i + 1][j]:
            out.append((olds[i], None))
            i += 1
        else:
            out.append((None, news[j]))
            j += 1
    out.extend((a, None) for a in olds[i:])
    out.extend((None, b) for b in news[j:])
    return out


def diff(before, after):
    """처음 문안과 고친 문안 -> [(종류, 처음, 고친 뒤)]. 달라진 곳만."""
    a, b = units(before), units(after)
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        for old, new in _pairs(a[i1:i2], b[j1:j2]):
            if old is None:
                out.append((KIND_ADD, "", new))
            elif new is None:
                out.append((KIND_DELETE, old, ""))
            else:
                out.append((KIND_FILL if "채울 것" in old else KIND_CHANGE, old, new))
    return out


def record(con, rows, now):
    """대기열의 줄에서 새로 생긴 고침을 DB에 남긴다. 돌려주는 값: 새로 남긴 수."""
    seen_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    new = 0
    for r in rows:
        if (r.get("상태") or "").strip() not in FINAL_STATES:
            continue
        before, after = (r.get("처음 문안") or "").strip(), (r.get("본문") or "").strip()
        if not before or not after or before == after:
            continue
        draft = (r.get("메모") or "").split(" · ")[0].strip()[:60]
        for kind, old, fresh in diff(before, after):
            cur = con.execute("INSERT OR IGNORE INTO sns_edit(board_no,draft,channel,kind,before,after,seen_at) VALUES (?,?,?,?,?,?,?)",
                              (str(r.get("번호") or ""), draft, (r.get("채널") or "").strip(), kind, old, fresh, seen_at))
            new += cur.rowcount
    con.commit()
    return new


def _cut(text):
    return text if len(text) <= CELL_MAX else text[:CELL_MAX - 1] + "…"


def latest(con, limit=TAB_ROWS):
    """탭에 적을 줄. 최근 것부터."""
    out = []
    for board_no, draft, channel, kind, before, after, seen_at in con.execute(
            "SELECT board_no,draft,channel,kind,before,after,seen_at FROM sns_edit ORDER BY seen_at DESC, edit_id DESC LIMIT ?", (limit,)):
        when = datetime.strptime(seen_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).astimezone(KST).strftime("%m-%d %H:%M")
        out.append({"본 시각(KST)": when, "번호": board_no, "초안": draft, "채널": channel, "종류": kind, "처음": _cut(before), "고친 뒤": _cut(after)})
    return out


def total(con):
    return con.execute("SELECT COUNT(*) FROM sns_edit").fetchone()[0]
