"""조종판 일꾼이 이 PC·서버에서 제대로 도는지 임시 폴더에서 확인한다. 인터넷, 실제 시트, 실제 계정을 쓰지 않는다.

    python -m pipeline.console.selftest
"""
import os
import sys
import tempfile
from datetime import datetime, timezone

from ..collect import store
from ..publish import threads as threads_api
from ..publish import x as x_api
from . import board as B
from . import worker as W


def main():
    ok = []

    def check(name, cond, detail=""):
        ok.append(bool(cond))
        print("%s %s%s" % ("  통과" if cond else "**실패", name, "" if cond else " — " + str(detail).strip()[-400:]))

    # --- X 서명과 길이
    p = {"status": "Hello Ladies + Gentlemen, a signed OAuth request!", "include_entities": "true",
         "oauth_consumer_key": "xvz1evFS4wEEPTGEFPHBog", "oauth_nonce": "kYjzVBB8Y0ZFabxSWbWovY3uYSQ2pTgmZeNu2VS4cg",
         "oauth_signature_method": "HMAC-SHA1", "oauth_timestamp": "1318622958",
         "oauth_token": "370773112-GmHxMAgYyLbNEtIKZeRNFsMKPR9EyMZeS9weJAEb", "oauth_version": "1.0"}
    sig = x_api.sign("POST", "https://api.twitter.com/1.1/statuses/update.json", p,
                     "kAcSOqF21Fu85e7zjz7ZN2U4ZRhfV3WpwPAoE3Z7kBw", "LswwdoUaIvS8ltyTt5jkRh4J50vUPVVHtR2YPi5kE")
    check("X 서명: 공식 문서의 예제 값과 일치", sig == "hCtSmYh+iHYCEqBWrE7C7hYmtUk=", sig)
    check("X 길이: 한글 140자 = 280, 링크 = 23", x_api.weighted_length("가" * 140) == 280 and x_api.weighted_length("a https://example.com/" + "b" * 60) == 25)
    sent = {}

    def fake_send(body, header):
        sent["body"], sent["header"] = body, header
        return {"data": {"id": "777", "text": body["text"]}}
    env = {"X_API_KEY": "k", "X_API_SECRET": "s", "X_ACCESS_TOKEN": "t", "X_ACCESS_SECRET": "ts",
           "THREADS_USER_ID": "u1", "THREADS_ACCESS_TOKEN": "tok-secret"}
    pid, url = x_api.post("안녕", env, reply_to="55", send=fake_send)
    check("X 요청: 본문·답글 대상·인증 머리글", pid == "777" and sent["body"] == {"text": "안녕", "reply": {"in_reply_to_tweet_id": "55"}}
          and sent["header"].startswith("OAuth ") and "oauth_signature=" in sent["header"] and url.endswith("/777"), sent)

    calls = []

    def fake_call(method, url, data=None, timeout=30):
        calls.append((method, url.split("?")[0], dict(data or {})))
        if url.endswith("/threads"):
            return {"id": "box1"}
        if url.endswith("/threads_publish"):
            return {"id": "post1"}
        return {"permalink": "https://www.threads.net/@checksumlab/post/abc"}
    tid, link = threads_api.post("글", env, reply_to="p0", wait=0, call=fake_call, sleep=lambda s: None)
    check("스레드 요청: 그릇 → 게시 → 링크", tid == "post1" and link.endswith("/abc") and [c[1].rsplit("/", 1)[-1] for c in calls] == ["threads", "threads_publish", "post1"]
          and calls[0][2]["media_type"] == "TEXT" and calls[0][2]["reply_to_id"] == "p0" and calls[1][2]["creation_id"] == "box1", calls)

    # --- 일꾼
    with tempfile.TemporaryDirectory() as tmp:
        board = B.CsvBoard(os.path.join(tmp, "board"))
        for tab in (B.QUEUE, B.CANDIDATES, B.STATUS):
            board.ensure(tab)
        banned = W.banned_terms()
        n1, _ = W.add_draft(board, B.CH_THREADS, "2099-01-05 06:30", "첫 글입니다. 제 가설은 이렇습니다.", "출처 https://example.com/a", banned=banned)
        n2, _ = W.add_draft(board, B.CH_X, "2099-01-05 06:30", "X용 짧은 글", "출처 https://example.com/a", banned=banned)
        n3, _ = W.add_draft(board, B.CH_THREADS, "2099-01-06 06:30", "내일 글", banned=banned)
        n4, p4 = W.add_draft(board, B.CH_THREADS, "", "이건 무조건 오릅니다", banned=banned)
        n5, p5 = W.add_draft(board, B.CH_THREADS, "", "본문에 링크 https://example.com/x", banned=banned)
        n6, p6 = W.add_draft(board, B.CH_X, "", "가" * 141, banned=banned)
        n7, _ = W.add_draft(board, B.CH_THREADS, "", "승인하지 않은 글", banned=banned)
        n8, _ = W.add_draft(board, B.CH_THREADS, "", "서버가 받아 주지 않는 글", banned=banned)
        check("초안을 넣을 때 검사 결과를 미리 적음", (n1, n4) == ("1", "4") and any("금지어" in x for x in p4) and any("링크" in x for x in p5) and any("X 길이" in x for x in p6), (p4, p5, p6))

        rows = board.read(B.QUEUE)
        for r in rows:
            if r["번호"] != n7:
                board.update(B.QUEUE, r["_row"], {"상태": B.ST_OK})
        board.update(B.QUEUE, rows[0]["_row"], {"본문": "첫 글입니다. 제 가설은 조금 다릅니다."})   # Nick이 시트에서 고침

        log, made = [], []

        def fake_threads(text, env, reply_to=None):
            if "받아 주지" in text:
                raise threads_api.PostError("스레드 API 오류 400: bad")
            made.append(("스레드", text, reply_to))
            return "T%d" % len(made), "https://threads.example/%d" % len(made)

        def fake_x(text, env, reply_to=None):
            made.append(("X", text, reply_to))
            return "X%d" % len(made), "https://x.example/%d" % len(made)
        posters = {B.CH_THREADS: fake_threads, B.CH_X: fake_x}
        now = datetime(2099, 1, 4, 22, 0, tzinfo=timezone.utc)   # 한국 시간 1/5 07:00

        res = W.run_once(board, env, now=now, dry_run=True, posters=posters, log=log.append)
        after = {r["번호"]: r["상태"] for r in board.read(B.QUEUE)}
        check("미리 보기는 올리지도, 시트를 바꾸지도 않음", not made and res == (3, 3, 1) and all(v in (B.ST_OK, B.ST_DRAFT) for v in after.values()), (res, made, after))

        con = store.connect(os.path.join(tmp, "t.db"))
        res = W.run_once(board, env, now=now, posters=posters, con=con, log=log.append)
        st = {r["번호"]: r for r in board.read(B.QUEUE)}
        check("승인되고 시각이 지난 글만 올림", res == (2, 4, 1) and st[n1]["상태"] == B.ST_DONE and st[n2]["상태"] == B.ST_DONE and st[n3]["상태"] == B.ST_OK, (res, {k: v["상태"] for k, v in st.items()}))
        check("승인하지 않은 글은 그대로", st[n7]["상태"] == B.ST_DRAFT and not st[n7]["게시 링크"])
        check("금지어·본문 링크·길이 초과는 막힘과 이유", all(st[n]["상태"] == B.ST_BLOCKED for n in (n4, n5, n6)) and "금지어" in st[n4]["검사"] and "링크" in st[n5]["검사"] and "X 길이" in st[n6]["검사"],
              [st[n]["검사"] for n in (n4, n5, n6)])
        check("올리다 난 오류는 막힘으로, 토큰은 드러나지 않음", st[n8]["상태"] == B.ST_BLOCKED and "400" in st[n8]["검사"] and "tok-secret" not in str(st) + " ".join(log), st[n8]["검사"])
        check("스레드는 셀프 답글을 달고, X는 링크 답글을 달지 않음", ("스레드", "출처 https://example.com/a", "T1") in made and not any(c == "X" and r for c, _, r in made)
              and "링크 답글" in st[n2]["메모"], made)
        check("게시 링크와 시각을 다시 적음", st[n1]["게시 링크"].startswith("https://threads.example/") and st[n1]["게시 시각"] == "2099-01-05 07:00", st[n1])
        logrow = con.execute("SELECT channel, text_original, text_final, edited, url FROM sns_post ORDER BY post_id").fetchall()
        check("올린 글 기록: 처음 문안과 고친 문안", len(logrow) == 2 and logrow[0][3] == 1 and "조금 다릅니다" in logrow[0][2] and "이렇습니다" in logrow[0][1] and logrow[1][3] == 0, logrow)

        before = len(made)
        res = W.run_once(board, env, now=now, posters=posters, con=con, log=log.append)
        check("다시 돌려도 두 번 올리지 않음", len(made) == before and res[0] == 0, (res, len(made)))
        board.update(B.QUEUE, st[n3]["_row"], {"상태": B.ST_POSTING})
        log.clear()
        W.run_once(board, env, now=datetime(2099, 1, 6, tzinfo=timezone.utc), posters=posters, con=con, log=log.append)
        check("'게시 중'으로 남은 줄은 다시 올리지 않고 알림", len(made) == before and any("게시 중" in x for x in log), log)
        bad = board.read(B.QUEUE)[6]
        board.update(B.QUEUE, bad["_row"], {"상태": B.ST_OK, "예약(KST)": "내일 아침"})
        W.run_once(board, env, now=now, posters=posters, con=con, log=log.append)
        check("읽을 수 없는 예약 시각은 막힘", board.read(B.QUEUE)[6]["상태"] == B.ST_BLOCKED and len(made) == before)
        W.write_status(board, 2, 4, 1, now)
        W.write_status(board, 0, 0, 1, now)
        srows = board.read(B.STATUS)
        check("오늘 현황에 한 줄로 갱신", len(srows) == 1 and srows[0]["결과"].startswith("올림 0"), srows)
        con.close()

    print("\n시험 %d건 중 %d건 통과" % (len(ok), sum(ok)))
    return 0 if all(ok) else 1


if __name__ == "__main__":
    sys.exit(main())
