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
from . import drafts as D
from . import edits as E
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
    check("X 한도: 긴 글이 켜져 있으면 25,000, 아니면 280", (x_api.BASIC_WEIGHT, x_api.LONG_WEIGHT) == (280, 25000)
          and x_api.MAX_WEIGHT == (x_api.LONG_WEIGHT if x_api.LONG_POSTS else x_api.BASIC_WEIGHT), x_api.MAX_WEIGHT)
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
        n6, p6 = W.add_draft(board, B.CH_X, "", "가" * (x_api.MAX_WEIGHT // 2 + 1), banned=banned)   # 한도를 한 글자 넘긴 글
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
        opts = {"db": os.path.join(tmp, "j.db"), "raw_dir": os.path.join(tmp, "raw"), "schedule": sched, "actuals": os.path.join(tmp, "actuals.csv"), "from_file": early,
                "drafts": os.path.join(tmp, "no_drafts", "*.md")}
        t0 = datetime(2099, 1, 14, 13, 32, tzinfo=timezone.utc)   # 발표 2분 뒤
        jlog = []
        only_collect = [j for j in J.JOBS if j.id == "collect_indicators"]
        kw = dict(board_opener=lambda: board, log=jlog.append, jobs=only_collect)

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
        ran = J.tick(now=t1, opts=dict(opts, db=os.path.join(tmp, "j4.db"), collect=broken), board_opener=no_board, log=jlog.append, jobs=only_collect)
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

        # 일정표에 읽을 수 없는 줄·겹친 줄이 있어도 일꾼은 돈다
        messy = os.path.join(tmp, "schedule_messy.csv")
        with open(messy, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["event_kind", "title_ko", "ref_period", "release_et", "release_kst", "release_at_utc", "tier", "targets", "source_url", "checked"])
            w.writerow(["CPI", "소비자물가", "2098-12", "", "", "2099-01-14T13:30:00Z", 1, "CPI_MOM CPI_CORE_MOM CPI_YOY", "u", 1])
            w.writerow(["CPI", "소비자물가", "2098-12", "", "", "2099-01-14T13:30:00Z", 1, "CPI_MOM CPI_CORE_MOM CPI_YOY", "u", 1])
            w.writerow(["GDP_ADV", "GDP 속보치", "2098Q4", "", "", "", 1, "GDP_ADV_QOQ", "u", 1])
            w.writerow(["PPI", "생산자물가", "2098-12", "", "", "2099-01-15T13:30Z", 2, "PPI_FD_MOM", "u", 1])
            w.writerow(["CPI", "소비자물가", "2099-01"])
        o6 = dict(opts, db=os.path.join(tmp, "j6.db"), raw_dir=os.path.join(tmp, "raw6"), schedule=messy, actuals=os.path.join(tmp, "a6.csv"), from_file=full)
        ids = [s.id for s in J.indicator_slots(t0, o6)]
        jlog.clear()
        ran = J.tick(now=t0, opts=o6, **kw)
        row = {r["항목"]: r for r in board.read(B.STATUS)}["지표 수집"]
        check("일정표의 읽을 수 없는 줄은 건너뛰고 알림, 겹친 줄은 예정 하나", ids.count("release:CPI:2098-12") == 1 and not any("PPI" in i for i in ids) and len(ran) == 1 and ran[0][2]["ok"]
              and ran[0][2]["done"] == {"daily:2099-01-14", "release:CPI:2098-12"} and row["메모"].count("읽을 수 없는 줄") == 1 and "PPI 2098-12" in row["메모"] and J.tick(now=t0 + timedelta(minutes=10), opts=o6, **kw) == [], (ids, ran, row))

        def leaky(**k):
            raise RuntimeError("request failed: registrationkey=SECRETKEY0123456789")
        jlog.clear()
        J.tick(now=t1, opts=dict(opts, db=os.path.join(tmp, "j7.db"), collect=leaky, secrets=J.secrets_of({"BLS_API_KEY": "SECRETKEY0123456789", "CONSOLE_SHEET_ID": "sheet-id-0123456789"})), **kw)
        row = {r["항목"]: r for r in board.read(B.STATUS)}["지표 수집"]
        check("오류 문구에 서버의 키가 섞여도 조종판·기록·로그에는 가려서", "도중에 멈춤" in row["결과"] and "(가림)" in row["결과"] and "SECRETKEY" not in str(row) + " ".join(jlog)
              and J.secrets_of({"CONSOLE_SHEET_ID": "sheet-id-0123456789", "X": "short"}) == [], (row, jlog))

    # --- 채우지 않은 칸: 휴대폰에서 고치다 괄호가 한쪽만 남아도 막는다
    bn = W.banned_terms()
    left = ["전월비 [채울 것: CPI 전월비]%", "전월비 [채울 것: CPI 전월비 %", "전월비 채울 것: CPI 전월비]%", "전월비 ［채울 것： CPI］%", "전월비 [채울것: CPI]%",
            "전월비 (채울 것: CPI)%", "전월비 [ 채울 것: CPI ]%", "전월비 [채\u200b울 것: CPI]%"]
    check("채우지 않은 칸의 변형을 모두 막고, 평범한 문장은 막지 않음", all(any("채우지 않은 칸" in x for x in W.check_text(B.CH_THREADS, t, "", bn)) for t in left)
          and any("채우지 않은 칸" in x for x in W.check_text(B.CH_X, "짧은 글", "", bn) + W.check_text(B.CH_THREADS, "글", "구독: [채울 것: 주소", bn))
          and not W.check_text(B.CH_THREADS, "빈칸은 제가 채울 것입니다. 숫자는 그대로 적겠습니다.", "", bn),
          [t for t in left if not W.check_text(B.CH_THREADS, t, "", bn)])

    # --- 초안 싣기: 저장소의 초안 파일 -> 대기열 ('초안'으로만)
    sample = """# 설명은 읽지 않는다
## 이 줄도 아님? 아니다, 이름 규칙에 걸린다
"""
    _, bad = D.parse(sample)
    check("초안 파일: 이름 규칙과 빈 초안을 잡음", any("초안 이름" in b for b in bad) and any("본문이 없음" in b for b in bad), bad)
    _, bad1 = D.parse("## a-1\n### 스레드\n글\n---\n<!-- 검토 메모 -->\n")
    _, bad2 = D.parse("##a-1\n### 스레드\n글\n")
    check("초안 파일: 본문에 섞인 구분선·주석 줄, 초안이 하나도 없는 파일을 잡음", sum("구분선이나 주석" in b for b in bad1) == 2 and any("하나도 없음" in b for b in bad2), (bad1, bad2))
    good = """설명 줄.

## 설명 안의 제목은 초안이 아니다
- 예약: 아무 말

<!-- 초안 시작 -->

## a-1009-0630
- 예약: 2099-01-05 06:30
- 줄기: 소개
- 조건: 없음

### 스레드
첫 글입니다.

둘째 문단.

### 스레드 답글
구독: https://example.com/s

### X
X용 짧은 글

## a-1009-1200
- 줄기: 일정
- 조건: 발표가 나온 뒤

### 스레드
전월비 [채울 것: CPI 전월비]%
"""
    drafts, bad = D.parse(good)
    check("초안 파일 읽기: 예약·줄기·조건, 본문의 빈 줄 보존, 채널별 칸", not bad and len(drafts) == 2 and drafts[0]["threads"] == "첫 글입니다.\n\n둘째 문단."
          and drafts[0]["reply"].startswith("구독") and drafts[0]["x"] == "X용 짧은 글" and drafts[0]["cond"] == "" and drafts[1]["cond"] == "발표가 나온 뒤" and drafts[1]["slot"] == "", (bad, drafts))
    with tempfile.TemporaryDirectory() as tmp:
        terms_file = os.path.join(tmp, "avoid.txt")
        with open(terms_file, "w", encoding="utf-8") as f:
            f.write("# 설명 줄\n봉인\n\n")
        terms = D.avoid_terms(terms_file)
        check("쓰지 않는 말: 목록에 있는 말이 든 글만 걸리고, 목록 파일이 없으면 걸지 않는다",
              terms == ["봉인"] and D.avoid_hits("답은 발표 전에 봉인했습니다.", terms) == ["봉인"] and D.avoid_hits("답은 발표 전에 저장해 두었습니다.", terms) == []
              and D.avoid_terms(os.path.join(tmp, "none.txt")) == [], terms)
    with tempfile.TemporaryDirectory() as tmp:
        board = B.CsvBoard(os.path.join(tmp, "board"))
        for tab in (B.QUEUE, B.CANDIDATES, B.STATUS):
            board.ensure(tab)
        os.makedirs(os.path.join(tmp, "drafts"))
        with open(os.path.join(tmp, "drafts", "first.md"), "w", encoding="utf-8") as f:
            f.write(good)
        with open(os.path.join(tmp, "drafts", "broken.md"), "w", encoding="utf-8") as f:
            f.write("## b-1\n- 예약: 내일 아침\n\n### 스레드\n글\n")
        W.add_draft(board, B.CH_THREADS, "", "이미 있던 줄", banned=W.banned_terms())
        opts = {"db": os.path.join(tmp, "d.db"), "drafts": os.path.join(tmp, "drafts", "*.md"), "schedule": os.path.join(tmp, "none_*.csv")}
        t0 = datetime(2099, 1, 4, 22, 2, tzinfo=timezone.utc)
        jlog = []
        only = [j for j in J.JOBS if j.id == "load_drafts"]
        ran = J.tick(now=t0, opts=opts, jobs=only, board_opener=lambda: board, log=jlog.append)
        q = board.read(B.QUEUE)
        st = {r["항목"]: r for r in board.read(B.STATUS)}.get("초안 싣기", {})
        check("초안 싣기: 채널마다 한 줄, 번호를 이어서, 메모에 이름과 조건", len(ran) == 1 and [(r["번호"], r["채널"], r["예약(KST)"]) for r in q[1:]] ==
              [("2", "스레드", "2099-01-05 06:30"), ("3", "X", "2099-01-05 06:30"), ("4", "스레드", "")] and q[1]["셀프 답글"].startswith("구독")
              and q[1]["메모"] == "a-1009-0630 · 소개" and "조건: 발표가 나온 뒤" in q[3]["메모"] and q[1]["처음 문안"] == q[1]["본문"], q)
        check("실은 초안은 전부 '초안' 상태이고, 채우지 않은 칸은 검사에 적힘", all(r["상태"] == B.ST_DRAFT for r in q) and "채우지 않은 칸" in q[3]["검사"] and q[1]["검사"] == "이상 없음", [(r["상태"], r["검사"]) for r in q])
        check("오늘 현황: 실은 수와 형식이 틀린 파일", st.get("결과", "").startswith("주의 1건 · 초안 3줄") and "예약 시각 형식" in st.get("메모", "") and "4번(a-1009-1200)" in st["메모"], st)
        made = []
        res = W.run_once(board, {}, now=datetime(2099, 2, 1, tzinfo=timezone.utc), posters={B.CH_THREADS: lambda *a, **k: made.append(a) or ("1", "u"), B.CH_X: lambda *a, **k: made.append(a) or ("1", "u")}, log=jlog.append)
        check("승인하지 않은 초안은 예약 시각이 지나도 올라가지 않음", not made and res[0] == 0, (res, made))
        check("다시 돌려도 두 번 싣지 않음", J.tick(now=t0 + timedelta(minutes=5), opts=opts, jobs=only, board_opener=lambda: board, log=jlog.append) == [] and len(board.read(B.QUEUE)) == 4)
        board.update(B.QUEUE, q[3]["_row"], {"상태": B.ST_OK})
        res = W.run_once(board, {}, now=datetime(2099, 2, 1, tzinfo=timezone.utc), posters={B.CH_THREADS: lambda *a, **k: made.append(a) or ("1", "u")}, log=jlog.append)
        check("채우지 않은 칸이 있는 글은 승인해도 막힘", not made and board.read(B.QUEUE)[3]["상태"] == B.ST_BLOCKED and "채우지 않은 칸" in board.read(B.QUEUE)[3]["검사"], board.read(B.QUEUE)[3])
        with open(os.path.join(tmp, "drafts", "second.md"), "w", encoding="utf-8") as f:
            f.write("## c-1\n### 스레드\n새 글\n")

        def no_board():
            raise SystemExit("[중단] 조종판 시트를 열 수 없습니다: 권한")
        t1 = t0 + timedelta(minutes=10)
        J.tick(now=t1, opts=opts, jobs=only, board_opener=no_board, log=jlog.append)
        again = J.tick(now=t1 + timedelta(minutes=5), opts=opts, jobs=only, board_opener=lambda: board, log=jlog.append)
        later = J.tick(now=t1 + timedelta(minutes=30), opts=opts, jobs=only, board_opener=lambda: board, log=jlog.append)
        check("조종판을 못 열면 싣지 않고 30분 뒤 다시 시도", again == [] and len(later) == 1 and board.read(B.QUEUE)[-1]["본문"] == "새 글" and len(board.read(B.QUEUE)) == 5, (again, later))
        fresh_db = dict(opts, db=os.path.join(tmp, "d2.db"))   # DB를 잃어버린 경우: 시트에 이미 있는 줄은 다시 넣지 않는다
        ran = J.tick(now=t1 + timedelta(hours=2), opts=fresh_db, jobs=only, board_opener=lambda: board, log=jlog.append)
        check("실었다는 기록을 잃어도 시트에 있는 초안은 두 번 싣지 않음", len(ran) == 1 and "초안 0줄" in ran[0][2]["result"] and len(board.read(B.QUEUE)) == 5, (ran, len(board.read(B.QUEUE))))
        os.makedirs(os.path.join(tmp, "only_bad"))
        with open(os.path.join(tmp, "only_bad", "x.md"), "w", encoding="utf-8") as f:
            f.write("## b-1\n- 예약: 내일 아침\n\n### 스레드\n글\n")
        ob = {"db": os.path.join(tmp, "d3.db"), "drafts": os.path.join(tmp, "only_bad", "*.md")}
        first = J.tick(now=t1, opts=ob, jobs=only, board_opener=lambda: board, log=jlog.append)
        st = {r["항목"]: r for r in board.read(B.STATUS)}["초안 싣기"]
        check("형식이 틀린 파일만 있어도 한 번은 알리고, 같은 문제를 되풀이해 알리지 않음", len(first) == 1 and st["결과"].startswith("주의 1건") and "예약 시각 형식" in st["메모"]
              and J.tick(now=t1 + timedelta(minutes=40), opts=ob, jobs=only, board_opener=lambda: board, log=jlog.append) == [], (first, st))

    # --- 고친 기록: 승인·게시된 줄에서 고친 문장만 모아 탭에 적는다
    d = E.diff("첫 문장입니다. 둘째 문장입니다.\n\n셋째 줄\n전월비 [채울 것: CPI 전월비]%", "첫 문장입니다. 둘째 문장을 고쳤습니다.\n\n전월비 0.3%\n새로 넣은 줄")
    check("고친 곳만 문장 단위로: 바꿈·지움·채움·더함", d == [(E.KIND_CHANGE, "둘째 문장입니다.", "둘째 문장을 고쳤습니다."), (E.KIND_DELETE, "셋째 줄", ""),
                                             (E.KIND_FILL, "전월비 [채울 것: CPI 전월비]%", "전월비 0.3%"), (E.KIND_ADD, "", "새로 넣은 줄")], d)
    d2 = E.diff("스레드를 시작한 지 일주일이 됐습니다.\n\n[채울 것: 이번 주에 해 본 것 한 가지]\n\n다음 주에 첫 호를 보냅니다.",
                "글을 올린 지 일주일입니다.\n\n서버에서 지표를 받아 보았습니다.\n\n다음 주에 첫 호를 보냅니다.")
    check("통째로 채운 칸도 그 자리의 문장과 짝이 됨", (E.KIND_FILL, "[채울 것: 이번 주에 해 본 것 한 가지]", "서버에서 지표를 받아 보았습니다.") in d2
          and (E.KIND_CHANGE, "스레드를 시작한 지 일주일이 됐습니다.", "글을 올린 지 일주일입니다.") in d2 and len(d2) == 2, d2)
    check("고치지 않은 글은 기록이 없음", E.diff("같은 글.\n둘째 줄", "같은 글.\r\n둘째 줄 ") == [])
    with tempfile.TemporaryDirectory() as tmp:
        board = B.CsvBoard(os.path.join(tmp, "board"))
        for tab in (B.QUEUE, B.CANDIDATES, B.STATUS):
            board.ensure(tab)
        bn = W.banned_terms()
        W.add_drafts(board, [{"channel": B.CH_THREADS, "slot": "", "text": "숫자가 어떻게 나올지는 모릅니다. 나오면 그대로 적겠습니다.", "note": "a-1 · 일정"},
                             {"channel": B.CH_X, "slot": "", "text": "고쳤지만 아직 승인하지 않은 글입니다.", "note": "a-2 · 일정"},
                             {"channel": B.CH_THREADS, "slot": "", "text": "손대지 않고 승인한 글입니다.", "note": "a-3 · 일정"}], bn)
        q = board.read(B.QUEUE)
        board.update(B.QUEUE, q[0]["_row"], {"본문": "숫자는 저도 모릅니다. 나오면 그대로 적겠습니다.", "상태": B.ST_OK})
        board.update(B.QUEUE, q[1]["_row"], {"본문": "고치는 중입니다."})
        board.update(B.QUEUE, q[2]["_row"], {"상태": B.ST_OK})
        only = [j for j in J.JOBS if j.id == "log_edits"]
        opts = {"db": os.path.join(tmp, "e.db")}
        t0 = datetime(2099, 1, 5, 3, 7, tzinfo=timezone.utc)
        jlog = []
        ran = J.tick(now=t0, opts=opts, jobs=only, board_opener=lambda: board, log=jlog.append)
        tab = board.read(B.EDITS)
        st = {r["항목"]: r for r in board.read(B.STATUS)}.get("고친 기록", {})
        check("고친 기록: 승인한 줄의 고친 문장만 탭에", len(ran) == 1 and len(tab) == 1 and tab[0]["종류"] == E.KIND_CHANGE and tab[0]["처음"] == "숫자가 어떻게 나올지는 모릅니다."
              and tab[0]["고친 뒤"] == "숫자는 저도 모릅니다." and tab[0]["초안"] == "a-1" and st.get("결과", "").startswith("새로 고친 문장 1개"), (ran, tab, st))
        n_log = len(jlog)
        again = J.tick(now=t0 + timedelta(minutes=5), opts=opts, jobs=only, board_opener=lambda: board, log=jlog.append)
        nxt = J.tick(now=t0 + timedelta(hours=1), opts=opts, jobs=only, board_opener=lambda: board, log=jlog.append)
        check("같은 시간에는 한 번만, 새로 고친 것이 없으면 조용히 지나감", again == [] and len(nxt) == 1 and nxt[0][2]["quiet"] and len(jlog) == n_log
              and {r["항목"]: r for r in board.read(B.STATUS)}["고친 기록"]["마지막 실행(KST)"] == "2099-01-05 12:07", (again, nxt, jlog[n_log:]))
        board.update(B.QUEUE, q[1]["_row"], {"상태": B.ST_DONE})
        J.tick(now=t0 + timedelta(hours=2), opts=opts, jobs=only, board_opener=lambda: board, log=jlog.append)
        tab = board.read(B.EDITS)
        check("새 고침은 맨 위에, 긴 칸은 잘라서", len(tab) == 2 and tab[0]["초안"] == "a-2" and tab[1]["초안"] == "a-1" and E._cut("가" * 500).endswith("…") and len(E._cut("가" * 500)) == E.CELL_MAX, tab)
        try:
            board.replace(B.QUEUE, [])
            guarded = False
        except ValueError:
            guarded = True
        check("게시 대기열은 통째로 바꿀 수 없음", guarded and len(board.read(B.QUEUE)) == 3)

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
