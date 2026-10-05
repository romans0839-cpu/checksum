"""조종판 일꾼이 이 PC·서버에서 제대로 도는지 임시 폴더에서 확인한다. 인터넷, 실제 시트, 실제 계정을 쓰지 않는다.

    python -m pipeline.console.selftest
"""
import csv
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

from ..collect import store
from ..collect.selftest import fake_response
from ..publish import threads as threads_api
from ..publish import x as x_api
from . import board as B
from . import jobs as J
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
        W.set_status(board, "코드 반영", "반영 aaaaaaa → bbbbbbb", "", now)
        W.set_status(board, "코드 반영", "실패: console 자체 시험", "되돌림", now)
        srows = board.read(B.STATUS)
        check("오늘 현황: 다른 항목은 다른 줄, 같은 항목은 갱신", len(srows) == 2 and srows[1]["항목"] == "코드 반영" and srows[1]["결과"].startswith("실패") and srows[0]["항목"] == "게시 일꾼", srows)
        con.close()

    # --- 예약 작업 일꾼: 지표 수집을 서버에서 돌리는 길
    with tempfile.TemporaryDirectory() as tmp:
        board = B.CsvBoard(os.path.join(tmp, "board"))
        for tab in (B.QUEUE, B.CANDIDATES, B.STATUS):
            board.ensure(tab)
        sched = os.path.join(tmp, "schedule_t.csv")
        with open(sched, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["event_kind", "title_ko", "ref_period", "release_et", "release_kst", "release_at_utc", "tier", "targets", "source_url", "checked"])
            w.writerow(["CPI", "소비자물가", "2098-12", "", "", "2099-01-14T13:30:00Z", 1, "CPI_MOM CPI_CORE_MOM CPI_YOY", "u", 1])
            w.writerow(["CLAIMS", "주간 신규 실업수당 청구", "2099-01-10", "", "", "2099-01-15T13:30:00Z", 2, "CLAIMS_INIT", "u", 0])
            w.writerow(["GDP_ADV", "GDP 속보치", "2098Q4", "", "", "2099-01-16T13:30:00Z", 1, "GDP_ADV_QOQ", "u", 1])
        full, early = os.path.join(tmp, "full.json"), os.path.join(tmp, "early.json")
        doc = fake_response()
        with open(full, "w", encoding="utf-8") as f:
            json.dump(doc, f)
        for srs in doc["Results"]["series"]:   # 발표 직후 아직 새 달이 올라오지 않은 응답
            srs["data"] = [d for d in srs["data"] if not (d["year"] == "2098" and d["period"] == "M12")]
        with open(early, "w", encoding="utf-8") as f:
            json.dump(doc, f)
        opts = {"db": os.path.join(tmp, "j.db"), "raw_dir": os.path.join(tmp, "raw"), "schedule": sched, "actuals": os.path.join(tmp, "actuals.csv"), "from_file": early}
        t0 = datetime(2099, 1, 14, 13, 32, tzinfo=timezone.utc)   # 발표 2분 뒤
        jlog = []
        kw = dict(board_opener=lambda: board, log=jlog.append)

        ids = [s.id for s in J.indicator_slots(t0, opts)]
        check("예정: 매일 아침 + 수집기가 있는 발표 직후만", "release:CPI:2098-12" in ids and not any("CLAIMS" in i or "GDP" in i for i in ids)
              and sum(i.startswith("daily:") for i in ids) == J.PLAN_DAYS + 2 and "daily:2099-01-14" in ids, ids)
        ran = J.tick(now=t0, opts=opts, dry_run=True, **kw)
        check("미리 보기는 돌리지도 기록하지도 않음", [r[1] for r in ran] == [["daily:2099-01-14", "release:CPI:2098-12"]] and ran[0][2] is None
              and not os.path.exists(opts["actuals"]) and not board.read(B.STATUS), ran)
        ran = J.tick(now=t0, opts=opts, **kw)
        row = {r["항목"]: r for r in board.read(B.STATUS)}.get("지표 수집", {})
        check("첫 바퀴: 수집하고 오늘 현황에 한 줄", len(ran) == 1 and ran[0][2]["ok"] and ran[0][2]["done"] == {"daily:2099-01-14"} and row.get("결과", "").startswith("정상 · 새 값")
              and "최근 달 2098-11" in row["결과"] and row["마지막 실행(KST)"] == "2099-01-14 22:32", (ran, row))
        check("발표값이 아직 없으면 메모에 적고 다시 받을 예정", "발표값이 아직 오지 않음(CPI 전월비" in row.get("메모", "") and "다음: " in row.get("메모", ""), row)
        check("간격 안에는 다시 돌리지 않음", J.tick(now=t0 + timedelta(minutes=5), opts=opts, **kw) == [])
        opts["from_file"] = full
        ran = J.tick(now=t0 + timedelta(minutes=10), opts=opts, **kw)
        row = {r["항목"]: r for r in board.read(B.STATUS)}["지표 수집"]
        check("10분 뒤 다시 받아 처음 발표값을 기록하고 끝냄", len(ran) == 1 and ran[0][1] == ["release:CPI:2098-12"] and ran[0][2]["done"] == {"release:CPI:2098-12"}
              and "처음 발표값 기록: CPI 전월비(계절조정) 2098-12 = " in row["메모"] and sum(1 for _ in open(opts["actuals"], encoding="utf-8")) == 4, (ran, row))
        check("끝난 예정은 다시 돌리지 않음", J.tick(now=t0 + timedelta(minutes=20), opts=opts, **kw) == [] and J.tick(now=t0 + timedelta(hours=2), opts=opts, **kw) == [])
        con = store.connect(opts["db"])
        runs = con.execute("SELECT status, detail FROM job_run WHERE job_id='collect_indicators' AND detail LIKE 'slot=%' ORDER BY run_id").fetchall()
        con.close()
        check("실행 기록: 예정마다 한 줄씩", [(st_, d.split()[0]) for st_, d in runs] == [("ok", "slot=daily:2099-01-14"), ("skipped", "slot=release:CPI:2098-12"),
                                                                              ("ok", "slot=release:CPI:2098-12")], runs)

        # 실패와 다시 시도
        calls = []
        blank = {"ok": False, "error": "", "error_kind": "", "received": 0, "listed": 27, "new": 0, "revised": 0, "same": 0, "newest": None, "unknown": 0,
                 "mismatch": [], "missing": [], "calc_diff": [], "added": [], "notes": [], "raw_path": ""}

        def failing(**k):
            calls.append(k["now"])
            return 1, dict(blank, error="노동통계국 API에 닿지 못했습니다: timed out", error_kind="network")
        o2 = dict(opts, db=os.path.join(tmp, "j2.db"), collect=failing)
        t1 = datetime(2099, 2, 1, 0, 0, tzinfo=timezone.utc)
        J.tick(now=t1, opts=o2, **kw)
        row = {r["항목"]: r for r in board.read(B.STATUS)}["지표 수집"]
        check("실패하면 이유와 다시 시도 시각을 적음", len(calls) == 1 and row["결과"].startswith("실패: 노동통계국 API에 닿지 못했습니다") and "60분 뒤 다시 시도 (1/24)" in row["메모"], row)
        J.tick(now=t1 + timedelta(minutes=30), opts=o2, **kw)
        J.tick(now=t1 + timedelta(minutes=60), opts=o2, **kw)
        check("실패한 예정은 정해진 간격으로만 다시 시도", calls == [t1, t1 + timedelta(minutes=60)], calls)
        con = store.connect(o2["db"])
        soon = t1 + timedelta(minutes=65)
        check("사람이 직접 돌릴 때는 간격을 따지지 않고 끝나지 않은 예정을 함께 처리", [s.id for s in J.due_slots(con, J.JOBS[0], soon, o2)] == []
              and [s.id for s in J.due_slots(con, J.JOBS[0], soon, o2, ignore_gap=True)] == ["daily:2099-02-01"])
        con.close()
        o3 = dict(opts, db=os.path.join(tmp, "j3.db"), collect=lambda **k: (2, dict(blank, error="키 없음", error_kind="no_key")))
        J.tick(now=t1, opts=o3, **kw)
        row = {r["항목"]: r for r in board.read(B.STATUS)}["지표 수집"]
        check("키가 없으면 무엇을 넣어야 하는지 적음", "BLS_API_KEY" in row["결과"] and ".env" in row["메모"], row)

        def broken(**k):
            raise RuntimeError("boom")

        def no_board():
            raise SystemExit("[중단] 조종판 시트를 열 수 없습니다: 권한")
        jlog.clear()
        ran = J.tick(now=t1, opts=dict(opts, db=os.path.join(tmp, "j4.db"), collect=broken), board_opener=no_board, log=jlog.append)
        check("작업이 멈추거나 조종판을 못 열어도 일꾼은 끝까지 돌고 기록을 남김", len(ran) == 1 and not ran[0][2]["ok"] and "도중에 멈춤" in ran[0][2]["result"]
              and any("조종판에 적지 못함" in x for x in jlog), (ran, jlog))
        tue = datetime(2099, 1, 1, 14, 30, tzinfo=timezone.utc)   # 한국 시간 23:30
        while tue.astimezone(J.KST).weekday() != 1:
            tue += timedelta(days=1)
        n_before = len(calls)
        check("화요일 봇 집행 시간에는 돌리지 않음", J.is_quiet(tue) and not J.is_quiet(tue + timedelta(minutes=30)) and J.tick(now=tue, opts=dict(o2, db=os.path.join(tmp, "j5.db")), **kw) == []
              and len(calls) == n_before)
        res, memo = J.indicator_summary(dict(blank, ok=True, new=5, newest=(2098, 12), mismatch=["CUSR0000SETG01 (항공료): Airline fares in U.S. city average"], missing=["WPSFD41"], unknown=2))
        check("요약: 고칠 때 필요한 내용(제목 불일치, 오지 않은 계열)을 그대로", res.startswith("주의 2건 · 새 값 5") and any("Airline fares" in m for m in memo) and any("WPSFD41" in m for m in memo)
              and any("대조하지 못한 계열 2개" in m for m in memo), (res, memo))

    class FakeApi(Exception):
        pass
    try:
        try:
            raise FakeApi("APIError: [403]: Google Sheets API has not been used in project 1 before or it is disabled.")
        except FakeApi as inner:
            raise PermissionError from inner
    except PermissionError as e:
        m1 = B.explain_sheet_error(e)
    m2 = B.explain_sheet_error(PermissionError())
    m3 = B.explain_sheet_error(FileNotFoundError(2, "No such file", "/x/sa.json"))
    m4 = B.explain_sheet_error(FakeApi("APIError: [404]: Requested entity was not found."))
    check("시트 오류를 원인 한 줄로", "Sheets API" in m1 and "공유" in m2 and "키 파일" in m3 and "CONSOLE_SHEET_ID" in m4, (m1, m2, m3, m4))
    try:
        B.open_board({"GOOGLE_SERVICE_ACCOUNT_FILE": "/nonexistent/sa.json", "CONSOLE_SHEET_ID": "x"})
        stopped = ""
    except SystemExit as e:
        stopped = str(e)
    check("시트를 못 열면 긴 오류 대신 [중단] 한 줄", stopped.startswith("[중단] 조종판 시트를 열 수 없습니다"), stopped)

    print("\n시험 %d건 중 %d건 통과" % (len(ok), sum(ok)))
    return 0 if all(ok) else 1


if __name__ == "__main__":
    sys.exit(main())
