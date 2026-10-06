"""SNS 초안 파일: 저장소에 올린 초안(data/sns/drafts/*.md)을 조종판 게시 대기열에 '초안'으로 싣는다 (docs/15 §5-3).

    python -m pipeline.console.drafts check data/sns/drafts/<파일>.md    올리기 전 검사: 길이·금지어·본문 링크·채우지 않은 칸·쓰지 않는 말
    python -m pipeline.console.drafts pending                            아직 싣지 않은 초안 (서버)

- 세션(또는 예약 작업)이 초안 파일을 저장소에 올리면, 서버의 예약 작업 일꾼이 5분 안에 대기열에 '초안'으로 적는다.
  싣는 상태는 언제나 '초안'이다. 승인은 사람만 한다. 승인하지 않은 글은 올라가지 않는다.
- 한 번 실은 초안은 다시 싣지 않는다(파일 이름 + 초안 이름 + 채널로 기억한다). 실은 뒤에는 시트가 기준이다.
  이미 실은 초안을 고쳐서 다시 싣고 싶으면 초안 이름을 바꾼다(예: 끝에 -v2).
- 파일 형식 (마크다운). `<!-- 초안 시작 -->` 줄이 있으면 그 위는 설명이며 읽지 않는다(편성표·검토 메모를 적는 자리).
  그 줄이 없으면 첫 '## ' 앞까지가 설명이다.

    ## w1-1009-0630
    - 예약: 2026-10-09 06:30        (한국 시간. 비우면 승인 즉시 올라간다)
    - 줄기: 소개
    - 조건: 없음                    (있으면 대기열의 메모 칸에 적힌다)
    - 메모: ...

    ### 스레드
    본문

    ### 스레드 답글
    셀프 답글 (링크는 여기에만)

    ### X
    X용 글. 유료 구독 중이라 스레드 본문을 그대로 써도 된다(D30). 피드에는 앞부분만 보이고 접히므로 첫 문장이 중요한 것은 같다

- 나중에 채워야 하는 값은 [채울 것: 무엇] 으로 적는다. 채우지 않고 승인하면 게시 일꾼이 막는다.
- 독자가 알아듣지 못하는 우리끼리의 말(templates/avoid_terms.txt, 예: 봉인)이 본문에 있으면 check 가 걸러 낸다(D27).
  이 검사는 초안을 쓰는 쪽을 위한 것이라 check 명령에서만 한다. 서버는 이것으로 글을 막지 않는다 — 고쳐 쓰는 것은 사람의 몫이다.
"""
import argparse
import glob
import os
import re
import sys

from ..collect import store
from ..publish import x as x_api
from . import board as B
from . import worker as W

DRAFT_GLOB = os.path.join(store.ROOT, "data", "sns", "drafts", "*.md")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SECTIONS = {"스레드": "threads", "스레드 답글": "reply", "X": "x"}
META = {"예약": "slot", "줄기": "stem", "조건": "cond", "메모": "memo"}
START = "<!-- 초안 시작 -->"
AVOID_FILE = os.path.join(store.ROOT, "templates", "avoid_terms.txt")


def avoid_terms(path=None):
    """발행 문장에 쓰지 않는 말의 목록. 파일이 없으면 빈 목록."""
    try:
        with open(path or AVOID_FILE, encoding="utf-8-sig") as f:
            return [ln.strip() for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
    except OSError:
        return []


def avoid_hits(text, terms):
    """글에 들어 있는 '쓰지 않는 말'."""
    return [t for t in terms if t in (text or "")]


def parse(text):
    """초안 파일 -> ([{"id", "slot", "stem", "cond", "memo", "threads", "reply", "x"}], 문제 목록)."""
    drafts, problems, cur, part = [], [], None, None
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == START:
            lines = lines[i + 1:]
            break
    for line in lines:
        if line.startswith("## "):
            cur = {"id": line[3:].strip(), "slot": "", "stem": "", "cond": "", "memo": "", "threads": [], "reply": [], "x": []}
            drafts.append(cur)
            part = None
            continue
        if cur is None:
            continue   # 첫 초안 앞의 설명
        if line.startswith("### "):
            name = line[4:].strip()
            part = SECTIONS.get(name)
            if part is None:
                problems.append("%s: 모르는 칸 '%s' (스레드 / 스레드 답글 / X)" % (cur["id"], name))
            continue
        if part is None:
            m = re.match(r"^-\s*([^:：]+)[:：]\s*(.*)$", line)
            if m and m.group(1).strip() in META:
                cur[META[m.group(1).strip()]] = m.group(2).strip()
            elif line.strip():
                problems.append("%s: 읽을 수 없는 줄 '%s'" % (cur["id"], line.strip()[:40]))
            continue
        if re.match(r"^\s*(-{3,}|<!--.*-->)\s*$", line):
            problems.append("%s: 본문 안에 구분선이나 주석 줄이 있음 '%s' (그대로 올라가므로 지운다)" % (cur["id"], line.strip()[:30]))
        cur[part].append(line)
    if not drafts:
        problems.append("초안이 하나도 없음 ('## 초안이름' 줄을 찾지 못했다)")
    seen = set()
    for d in drafts:
        for part in SECTIONS.values():
            d[part] = "\n".join(d[part]).strip()
        if d["cond"] in ("없음", "-"):
            d["cond"] = ""
        if not ID_RE.match(d["id"]):
            problems.append("%s: 초안 이름은 영문 소문자·숫자·붙임표만" % d["id"])
        if d["id"] in seen:
            problems.append("%s: 같은 이름의 초안이 두 번 있음" % d["id"])
        seen.add(d["id"])
        if d["slot"] and W.parse_slot(d["slot"]) == "bad":
            problems.append("%s: 예약 시각 형식은 2026-10-09 06:30" % d["id"])
        if not d["threads"] and not d["x"]:
            problems.append("%s: 본문이 없음" % d["id"])
        if d["reply"] and not d["threads"]:
            problems.append("%s: 스레드 본문 없이 답글만 있음" % d["id"])
    return drafts, problems


def rows_of(stem, draft):
    """초안 하나 -> 대기열에 실을 줄(채널마다 하나). key 는 다시 싣지 않기 위한 이름."""
    note = " · ".join(x for x in (draft["id"], draft["stem"], "조건: " + draft["cond"] if draft["cond"] else "", draft["memo"]) if x)
    out = []
    if draft["threads"]:
        out.append({"key": "%s#%s#%s" % (stem, draft["id"], B.CH_THREADS), "channel": B.CH_THREADS, "slot": draft["slot"], "text": draft["threads"], "reply": draft["reply"], "note": note})
    if draft["x"]:
        out.append({"key": "%s#%s#%s" % (stem, draft["id"], B.CH_X), "channel": B.CH_X, "slot": draft["slot"], "text": draft["x"], "reply": "", "note": note})
    return out


def read_all(pattern=None):
    """초안 파일 전부 -> (실을 줄 목록, 문제 목록). 문제가 있는 파일은 통째로 건너뛴다(반쯤 실리는 것을 막는다)."""
    items, problems = [], []
    for path in sorted(glob.glob(pattern or DRAFT_GLOB)):
        stem = os.path.splitext(os.path.basename(path))[0]
        with open(path, encoding="utf-8-sig") as f:
            drafts, bad = parse(f.read())
        if bad:
            problems.extend("%s — %s" % (stem, b) for b in bad)
            continue
        for d in drafts:
            items.extend(rows_of(stem, d))
    return items, problems


def pending(con, pattern=None):
    """아직 싣지 않은 줄. (줄 목록, 문제 목록)."""
    items, problems = read_all(pattern)
    done = {r[0][len("draft:"):] for r in con.execute("SELECT key FROM meta WHERE key LIKE 'draft:%'")}
    return [it for it in items if it["key"] not in done], problems


def load(board, con, items, now_text):
    """대기열에 '초안'으로 싣고 실었다고 적는다. (실은 수, 검사에 걸린 줄의 설명 목록)."""
    if not items:
        return 0, []
    have = {((r.get("채널") or "").strip(), (r.get("처음 문안") or "").strip()) for r in board.read(B.QUEUE)}
    fresh = [it for it in items if (it["channel"], it["text"].strip()) not in have]   # 이미 시트에 있는 줄은 다시 넣지 않는다
    results = W.add_drafts(board, fresh) if fresh else []
    for it in items:
        store.set_meta(con, "draft:" + it["key"], now_text)
    con.commit()
    flagged = ["%s번(%s): %s" % (no, it["note"].split(" · ")[0], "; ".join(p)) for it, (no, p) in zip(fresh, results) if p]
    return len(fresh), flagged


def setup_console():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except Exception:
            pass


def main(argv=None):
    setup_console()
    ap = argparse.ArgumentParser(description="SNS 초안 파일")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="올리기 전 검사 (아무것도 쓰지 않는다)")
    c.add_argument("files", nargs="+")
    sub.add_parser("pending", help="아직 싣지 않은 초안")
    a = ap.parse_args(argv)
    if a.cmd == "pending":
        con = store.connect(store.DEFAULT_DB)
        items, problems = pending(con)
        con.close()
        for it in items:
            print("   %s  [%s] %s" % (it["slot"] or "(예약 없음)", it["channel"], it["note"][:60]))
        for p in problems:
            print("[주의] " + p)
        print("아직 싣지 않은 줄 %d개" % len(items))
        return 0
    banned, bad = W.banned_terms(), 0
    avoid = avoid_terms()
    for path in a.files:
        with open(path, encoding="utf-8-sig") as f:
            drafts, problems = parse(f.read())
        print("%s — 초안 %d개" % (os.path.basename(path), len(drafts)))
        for p in problems:
            bad += 1
            print("**형식 " + p)
        for d in drafts:
            for it in rows_of("x", d):
                found = W.check_text(it["channel"], it["text"], it["reply"], banned)
                todo = [p for p in found if p.startswith("채우지 않은 칸")]
                real = [p for p in found if p not in todo]
                hits = avoid_hits(it["text"] + "\n" + it["reply"], avoid)
                if hits:
                    real.append("쓰지 않는 말: " + ", ".join(hits) + " (풀어서 쓴다)")
                size = "%d자" % len(it["text"]) if it["channel"] == B.CH_THREADS else "가중 %d/%d" % (x_api.weighted_length(it["text"]), x_api.MAX_WEIGHT)
                print("%s %-18s %-4s %-12s %s%s" % ("**걸림" if real else "  통과", d["id"], it["channel"], size, d["slot"] or "(예약 없음)",
                                                 (" — " + "; ".join(real)) if real else (" — 채울 칸 있음" if todo else "")))
                bad += bool(real)
    print("걸린 곳 %d개" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
