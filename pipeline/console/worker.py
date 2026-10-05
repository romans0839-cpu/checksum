"""조종판 일꾼: 시트에서 '승인'된 글을 검사하고 SNS에 올린 뒤 결과를 시트에 다시 적는다.

    python -m pipeline.console.worker init                    탭과 머리글 만들기 (처음 한 번)
    python -m pipeline.console.worker run                     한 바퀴 돈다 (서버에서 5분마다)
    python -m pipeline.console.worker run --dry-run           올리지 않고 무엇을 할지만 보여 준다
    python -m pipeline.console.worker add --channel 스레드 --at "2026-10-09 06:30" --text "..." [--reply "..."]

규칙
- 상태가 '승인'이고 예약 시각이 지난 줄만 올린다. '초안'·'보류'는 건드리지 않는다. 사람이 승인하지 않은 글은 올라가지 않는다.
- 올리기 전에 검사한다: 금지어(templates/banned_terms.txt), 본문 안의 링크(링크는 셀프 답글에만), 길이(스레드 500자 / X 가중 280).
  걸리면 올리지 않고 '막힘'으로 바꾸고 이유를 적는다.
- 올리기 직전에 '게시 중'으로 바꾼다. 도중에 멈춘 줄('게시 중'으로 남은 줄)은 다시 올리지 않는다 — 두 번 올라가는 것을 막기 위해서다.
- X에는 링크가 든 셀프 답글을 달지 않는다(요금). .env 의 X_ALLOW_LINK_REPLY=1 로 풀 수 있다.
- 올라간 글은 DB(sns_post)에 처음 문안과 올린 문안을 함께 남긴다. 고친 흔적이 말투의 기준이 된다.
"""
import argparse
import re
import sys
from datetime import datetime, timedelta, timezone

from ..collect import env as envmod
from ..collect import store
from ..publish import threads as threads_api
from ..publish import x as x_api
from . import board as B

KST = timezone(timedelta(hours=9))
URL_RE = re.compile(r"https?://\S+")


def setup_console():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except Exception:
            pass


def banned_terms():
    from ..publish import lint
    return list(lint.BANNED)


def check_text(channel, text, reply, banned):
    """문제 목록. 비어 있으면 올려도 된다."""
    problems = []
    body = (text or "").strip()
    if not body:
        problems.append("본문이 비어 있음")
    if channel not in B.CHANNELS:
        problems.append("채널은 %s 중 하나" % "/".join(B.CHANNELS))
    for term in banned:
        if re.search(term, body) or re.search(term, reply or ""):
            problems.append("금지어: %s" % term)
    if URL_RE.search(body):
        problems.append("본문에 링크가 있음(링크는 셀프 답글에)")
    if channel == B.CH_THREADS:
        for name, t in (("본문", body), ("셀프 답글", (reply or "").strip())):
            if len(t) > threads_api.MAX_CHARS:
                problems.append("%s %d자 (스레드는 %d자까지)" % (name, len(t), threads_api.MAX_CHARS))
    if channel == B.CH_X and x_api.weighted_length(body) > x_api.MAX_WEIGHT:
        problems.append("X 길이 %d (한도 %d, 한글은 한 글자가 2)" % (x_api.weighted_length(body), x_api.MAX_WEIGHT))
    return problems


def parse_slot(text):
    text = (text or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y. %m. %d %H:%M"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=KST)
        except ValueError:
            continue
    return "bad"


def add_draft(board, channel, slot, text, reply="", note="", banned=None):
    """초안 한 줄을 넣는다. 넣을 때 검사해 결과를 '검사' 칸에 적어 둔다."""
    rows = board.read(B.QUEUE)
    numbers = [int(r["번호"]) for r in rows if str(r.get("번호", "")).isdigit()]
    no = str(max(numbers) + 1 if numbers else 1)
    problems = check_text(channel, text, reply, banned if banned is not None else banned_terms())
    board.append(B.QUEUE, [{"번호": no, "예약(KST)": slot or "", "채널": channel, "본문": text, "셀프 답글": reply or "", "상태": B.ST_DRAFT,
                            "검사": "이상 없음" if not problems else " / ".join(problems), "처음 문안": text, "메모": note}])
    return no, problems


def run_once(board, env, now=None, dry_run=False, posters=None, con=None, log=print):
    """한 바퀴. (올린 수, 막힌 수, 기다리는 수)를 돌려준다."""
    now = now or datetime.now(timezone.utc)
    posters = posters or {B.CH_THREADS: threads_api.post, B.CH_X: x_api.post}
    banned = banned_terms()
    posted = blocked = waiting = 0
    for r in board.read(B.QUEUE):
        row, state = r["_row"], (r.get("상태") or "").strip()
        if state == B.ST_POSTING:
            log("[주의] %s번 줄이 '게시 중'으로 남아 있습니다. 실제로 올라갔는지 확인한 뒤 상태를 직접 고치세요." % r.get("번호"))
            continue
        if state != B.ST_OK or (r.get("게시 링크") or "").strip():
            continue
        slot = parse_slot(r.get("예약(KST)"))
        if slot == "bad":
            if not dry_run:
                board.update(B.QUEUE, row, {"상태": B.ST_BLOCKED, "검사": "예약 시각 형식: 2026-10-09 06:30"})
            blocked += 1
            log("막힘 %s번: 예약 시각을 읽을 수 없음" % r.get("번호"))
            continue
        if slot is not None and slot > now:
            waiting += 1
            continue
        channel, text, reply = (r.get("채널") or "").strip(), (r.get("본문") or "").strip(), (r.get("셀프 답글") or "").strip()
        problems = check_text(channel, text, reply, banned)
        if problems:
            if not dry_run:
                board.update(B.QUEUE, row, {"상태": B.ST_BLOCKED, "검사": " / ".join(problems)})
            blocked += 1
            log("막힘 %s번: %s" % (r.get("번호"), "; ".join(problems)))
            continue
        if dry_run:
            log("올릴 것 %s번 [%s] %s" % (r.get("번호"), channel, text[:40].replace("\n", " ")))
            posted += 1
            continue
        board.update(B.QUEUE, row, {"상태": B.ST_POSTING})
        note, reply_id = (r.get("메모") or "").strip(), ""
        try:
            remote_id, url = posters[channel](text, env)
        except Exception as e:   # 올리지 못했다. 다시 승인하면 다시 시도한다
            board.update(B.QUEUE, row, {"상태": B.ST_BLOCKED, "검사": str(e)[:300]})
            blocked += 1
            log("막힘 %s번: %s" % (r.get("번호"), e))
            continue
        if reply:
            if channel == B.CH_X and URL_RE.search(reply) and env.get("X_ALLOW_LINK_REPLY") != "1":
                note = (note + " " if note else "") + "X에는 링크 답글을 달지 않음"
            else:
                try:
                    reply_id, _ = posters[channel](reply, env, reply_to=remote_id)
                except Exception as e:
                    note = (note + " " if note else "") + "셀프 답글 실패: %s" % str(e)[:120]
        stamp = now.astimezone(KST).strftime("%Y-%m-%d %H:%M")
        board.update(B.QUEUE, row, {"상태": B.ST_DONE, "검사": "이상 없음", "게시 링크": url or remote_id, "게시 시각": stamp, "메모": note})
        if con is not None:
            original = r.get("처음 문안") or ""
            con.execute("INSERT INTO sns_post(board_no,channel,slot_kst,text_original,text_final,edited,remote_id,url,reply_id,posted_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (r.get("번호"), channel, r.get("예약(KST)"), original, text, int(bool(original) and original.strip() != text), remote_id, url, reply_id,
                         now.strftime("%Y-%m-%dT%H:%M:%SZ")))
            con.commit()
        posted += 1
        log("게시 %s번 [%s] %s" % (r.get("번호"), channel, url or remote_id))
    return posted, blocked, waiting


def write_status(board, posted, blocked, waiting, now):
    stamp = now.astimezone(KST).strftime("%Y-%m-%d %H:%M")
    rows = board.read(B.STATUS)
    line = {"항목": "게시 일꾼", "마지막 실행(KST)": stamp, "결과": "올림 %d / 막힘 %d / 예약 대기 %d" % (posted, blocked, waiting), "메모": ""}
    hit = [r for r in rows if r.get("항목") == "게시 일꾼"]
    if hit:
        board.update(B.STATUS, hit[0]["_row"], line)
    else:
        board.append(B.STATUS, [line])


def main(argv=None):
    setup_console()
    ap = argparse.ArgumentParser(description="조종판 일꾼")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    r = sub.add_parser("run")
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--db", default=store.DEFAULT_DB)
    a = sub.add_parser("add")
    a.add_argument("--channel", required=True, choices=B.CHANNELS)
    a.add_argument("--at", default="", help='예약 시각(한국 시간) "2026-10-09 06:30". 비우면 승인 즉시')
    a.add_argument("--text", required=True)
    a.add_argument("--reply", default="")
    a.add_argument("--note", default="")
    args = ap.parse_args(argv)
    env = envmod.load()
    board = B.open_board(env)
    if args.cmd == "init":
        for tab in (B.QUEUE, B.CANDIDATES, B.STATUS):
            board.ensure(tab)
        print("조종판 준비 완료: %s" % ", ".join((B.QUEUE, B.CANDIDATES, B.STATUS)))
        return 0
    if args.cmd == "add":
        no, problems = add_draft(board, args.channel, args.at, args.text, args.reply, args.note)
        print("초안 %s번을 넣었습니다. 검사: %s" % (no, "이상 없음" if not problems else "; ".join(problems)))
        return 0
    now = datetime.now(timezone.utc)
    con = None if args.dry_run else store.connect(args.db)
    posted, blocked, waiting = run_once(board, env, now=now, dry_run=args.dry_run, con=con)
    if con is not None:
        con.execute("INSERT INTO job_run(job_id,started_at,finished_at,status,detail) VALUES ('console_worker',?,?,?,?)",
                    (now.strftime("%Y-%m-%dT%H:%M:%SZ"), store.utc_now(), "ok", "posted=%d blocked=%d waiting=%d" % (posted, blocked, waiting)))
        con.commit()
        con.close()
        write_status(board, posted, blocked, waiting, now)
    print("%s올림 %d / 막힘 %d / 예약 대기 %d" % ("(미리 보기) " if args.dry_run else "", posted, blocked, waiting))
    return 0


if __name__ == "__main__":
    sys.exit(main())
