"""조종판 일꾼이 이 PC·서버에서 제대로 도는지 임시 폴더에서 확인한다. 인터넷, 실제 시트, 실제 계정을 쓰지 않는다.

    python -m pipeline.console.selftest
"""
import csv
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

from ..collect import bls, store
from ..collect.selftest import fake_response
from ..forecast import runner as R
from ..forecast import selftest_runner as SR
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

    # --- 스레드 점검: 글을 올리지 않는 확인과 막힌 줄
    seen = []

    def ok_call(method, url, data=None, timeout=30):
        seen.append((method, url.split("?")[0].rsplit("/", 1)[-1], data))
        if url.split("?")[0].endswith("/me"):
            return {"id": "u1", "username": "checksumlab"}
        return {"data": [{"quota_usage": 3, "config": {"quota_total": 250, "quota_duration": 86400}}]}

    def blocked_call(method, url, data=None, timeout=30):
        if url.split("?")[0].endswith("/me"):
            return {"id": "u1", "username": "checksumlab"}
        raise threads_api.PostError("스레드 API 오류 400: API access blocked.")
    got = threads_api.check(env, call=ok_call)
    try:
        threads_api.check(env, call=blocked_call)
        where = ""
    except threads_api.PostError as e:
        where = str(e)
    check("스레드 점검: 읽기 요청 두 번, 글은 만들지 않음", got == ("checksumlab", "u1", 3, 250) and [c[:2] for c in seen] == [("GET", "me"), ("GET", "threads_publishing_limit")]
          and all(c[2] is None for c in seen) and where.startswith("게시 권한 확인에서 멈춤(@checksumlab)") and "API access blocked" in where and "tok-secret" not in where, (got, seen, where))
    with tempfile.TemporaryDirectory() as tmp:
        board = B.CsvBoard(os.path.join(tmp, "board"))
        for tab in (B.QUEUE, B.CANDIDATES, B.STATUS):
            board.ensure(tab)
        W.add_drafts(board, [{"channel": B.CH_THREADS, "slot": "", "text": "막혔던 글입니다.", "note": "s-roe · 예비"},
                             {"channel": B.CH_X, "slot": "2099-01-06 06:30", "text": "기다리는 글입니다.", "note": "b-1 · 일정"}], W.banned_terms())
        q = board.read(B.QUEUE)
        board.update(B.QUEUE, q[0]["_row"], {"상태": B.ST_BLOCKED, "검사": "스레드 API 오류 400: API access blocked."})
        board.update(B.QUEUE, q[1]["_row"], {"상태": B.ST_OK})
        only = [j for j in J.JOBS if j.id == "check_channels"]
        t0 = datetime(2099, 1, 5, 21, 0, tzinfo=timezone.utc)   # 한국 시간 1/6 06:00
        jlog = []
        ids = [s.id for s in J.channel_slots(t0, {})]
        o1 = {"db": os.path.join(tmp, "c.db"), "env": env, "threads_check": lambda e: threads_api.check(e, call=ok_call)}
        ran = J.tick(now=t0, opts=o1, jobs=only, board_opener=lambda: board, log=jlog.append)
        st = {r["항목"]: r for r in board.read(B.STATUS)}.get("스레드 점검", {})
        check("스레드 점검 작업: 하루 두 번, 정상이면 한도와 막힌 줄을 적음", "check:2099-01-06:0600" in ids and "check:2099-01-06:2030" in ids and len(ids) == 2 * (J.PLAN_DAYS + 2)
              and len(ran) == 1 and ran[0][2]["ok"] and st.get("결과") == "정상 · @checksumlab · 최근 24시간 게시 3/250 · 막힌 줄 1"
              and "s-roe(스레드): 스레드 API 오류 400: API access blocked." in st.get("메모", "") and "b-1" not in st.get("메모", "")
              and J.tick(now=t0 + timedelta(minutes=5), opts=o1, jobs=only, board_opener=lambda: board, log=jlog.append) == [], (ids[:4], ran, st))
        o2 = {"db": os.path.join(tmp, "c2.db"), "env": env, "threads_check": lambda e: threads_api.check(e, call=blocked_call), "secrets": J.secrets_of(env)}
        ran = J.tick(now=t0, opts=o2, jobs=only, board_opener=lambda: board, log=jlog.append)
        st = {r["항목"]: r for r in board.read(B.STATUS)}["스레드 점검"]
        soon = J.tick(now=t0 + timedelta(minutes=5), opts=o2, jobs=only, board_opener=lambda: board, log=jlog.append)
        again = J.tick(now=t0 + timedelta(minutes=30), opts=o2, jobs=only, board_opener=lambda: board, log=jlog.append)
        third = J.tick(now=t0 + timedelta(minutes=60), opts=o2, jobs=only, board_opener=lambda: board, log=jlog.append)
        check("스레드 점검 작업: 막혀 있으면 실패로 적고 30분 뒤 한 번만 더 본다", len(ran) == 1 and not ran[0][2]["ok"] and st["결과"].startswith("실패: 스레드 게시 권한 확인에서 멈춤(@checksumlab)")
              and "API access blocked" in st["결과"] and st["결과"].endswith("막힌 줄 1") and "X 줄은 따로" in st["메모"] and "30분 뒤 다시 시도 (1/2)" in st["메모"]
              and soon == [] and len(again) == 1 and third == [] and "tok-secret" not in json.dumps(board.read(B.STATUS), ensure_ascii=False), (ran, st, soon, again, third))
        ran = J.tick(now=t0, opts=dict(o1, db=os.path.join(tmp, "c3.db")), jobs=only, board_opener=no_board, log=jlog.append)
        check("스레드 점검 작업: 조종판을 못 열어도 토큰 확인은 한다", len(ran) == 1 and ran[0][2]["ok"] and "게시 대기열을 읽지 못함" in " ".join(ran[0][2]["memo"]), ran)

    # --- 스레드 API를 쉬는 동안: 스레드 줄은 부르지 않고 '보류', X 줄은 그대로
    with tempfile.TemporaryDirectory() as tmp:
        board = B.CsvBoard(os.path.join(tmp, "board"))
        for tab in (B.QUEUE, B.CANDIDATES, B.STATUS):
            board.ensure(tab)
        W.add_drafts(board, [{"channel": B.CH_THREADS, "slot": "2099-01-05 06:30", "text": "쉬는 동안의 스레드 글입니다.", "note": "p-1"},
                             {"channel": B.CH_X, "slot": "2099-01-05 06:30", "text": "쉬는 동안의 X 글입니다.", "note": "p-1"},
                             {"channel": B.CH_THREADS, "slot": "2099-01-09 06:30", "text": "아직 때가 안 된 스레드 글입니다.", "note": "p-2"}], W.banned_terms())
        for r in board.read(B.QUEUE):
            board.update(B.QUEUE, r["_row"], {"상태": B.ST_OK})
        called = []
        fake = {B.CH_THREADS: lambda t, e, reply_to=None: called.append("스레드") or ("t1", "https://threads.example/t1"),
                B.CH_X: lambda t, e, reply_to=None: called.append("X") or ("x1", "https://x.example/x1")}
        t0 = datetime(2099, 1, 5, 0, 0, tzinfo=timezone.utc)   # 한국 시간 1/5 09:00
        res = W.run_once(board, {}, now=t0, posters=fake, log=lambda x: None, paused=lambda now: "2099-01-07 06:20")
        q = board.read(B.QUEUE)
        again = W.run_once(board, {}, now=t0 + timedelta(days=5), posters=fake, log=lambda x: None, paused=lambda now: "")
        q2 = board.read(B.QUEUE)
        check("쉬는 동안: 스레드는 부르지 않고 보류, X는 올리고, 기한 뒤에도 보류한 줄은 올라가지 않음", res == (1, 0, 1) and called[:1] == ["X"] and q[0]["상태"] == B.ST_HOLD
              and "스레드 API를 쉬는 중(2099-01-07 06:20까지)" in q[0]["검사"] and q[1]["상태"] == B.ST_DONE and q[2]["상태"] == B.ST_OK
              and again == (1, 0, 0) and called == ["X", "스레드"] and q2[0]["상태"] == B.ST_HOLD and q2[2]["상태"] == B.ST_DONE, (res, called, [(r["상태"], r["검사"]) for r in q2]))
        kst = timezone(timedelta(hours=9))
        check("쉬는 기한 읽기: 기한 전에는 기한을, 지나면 빈 글을", threads_api.paused(datetime(2026, 10, 12, 6, 19, tzinfo=kst), "2026-10-12 06:20") == "2026-10-12 06:20"
              and threads_api.paused(datetime(2026, 10, 12, 6, 20, tzinfo=kst), "2026-10-12 06:20") == "" and threads_api.paused(t0, "") == "" and threads_api.paused(t0, "엉뚱한 값") == "")
        only = [j for j in J.JOBS if j.id == "check_channels"]
        hit = []
        ran = J.tick(now=datetime(2099, 1, 5, 21, 0, tzinfo=timezone.utc), opts={"db": os.path.join(tmp, "p.db"), "env": {}, "threads_paused": lambda now: "2099-01-07 06:20",
                                                                              "threads_check": lambda e: hit.append(1)}, jobs=only, board_opener=lambda: board, log=lambda x: None)
        st = {r["항목"]: r for r in board.read(B.STATUS)}.get("스레드 점검", {})
        check("쉬는 동안: 스레드 점검도 API를 부르지 않는다", len(ran) == 1 and ran[0][2]["ok"] and not hit and st.get("결과", "").startswith("쉬는 중 — 2099-01-07 06:20까지"), (ran, st))

    # --- 장부 봉인: 화요일에 그 주 신호만 봉인하고, 종목 이름은 조종판에 적지 않는다
    with tempfile.TemporaryDirectory() as tmp:
        board = B.CsvBoard(os.path.join(tmp, "board"))
        for tab in (B.QUEUE, B.CANDIDATES, B.STATUS):
            board.ensure(tab)
        bot, led, prv, sig_csv = (os.path.join(tmp, x) for x in ("bot", "ledger", "private", os.path.join("priv_tr", "signals.csv")))
        os.makedirs(os.path.join(bot, "signals"))

        def signal_file(day, asof, symbol):
            with open(os.path.join(bot, "signals", "target_%s.json" % day.replace("-", "")), "w", encoding="utf-8") as f:
                json.dump({"generator": "live_signal_a_selftest", "engine": "A", "params": {}, "asof_week": asof, "generated_at": day,
                           "orders": {"exit": [], "entry": [{"symbol": symbol, "group": "G"}]}, "model_positions": [{"symbol": "HOLDSYM"}], "context": {}}, f)
        tue = datetime(2099, 1, 5, 0, 45, tzinfo=timezone.utc)
        while tue.astimezone(J.KST).weekday() != 1:
            tue += timedelta(days=1)                      # 화요일 09:45 (한국 시간)
        day = tue.astimezone(J.KST).date()
        only = [j for j in J.JOBS if j.id == "pull_bot_signal"]
        pulls = []
        lo = {"db": os.path.join(tmp, "l.db"), "env": {}, "bot_dir": bot, "ledger_dir": led, "private_dir": prv, "signals_csv": sig_csv, "no_ots": True,
              "git_pull": lambda path: (pulls.append(path) or True, "")}
        kw = dict(opts=lo, jobs=only, board_opener=lambda: board, log=lambda x: None)
        status = lambda: {r["항목"]: r for r in board.read(B.STATUS)}.get("장부 봉인", {})
        ids = [x.id for x in J.ledger_slots(tue, {})]
        signal_file((day - timedelta(days=7)).isoformat(), (day - timedelta(days=8)).isoformat(), "OLDSYM")
        ran = J.tick(now=tue, **kw)
        check("장부 봉인: 빈 장부에는 서버가 아무것도 쓰지 않음", "seal:%s" % day.isoformat() in ids and "ledger:%s" % (day - timedelta(days=1)).isoformat() in ids
              and len(ran) == 1 and status().get("결과", "").startswith("장부 없음") and not os.path.exists(os.path.join(led, "ledger.jsonl")) and not pulls, (ids[:4], ran, status()))
        code, _ = J.quiet_call(J.ledger_commit.main, ["--bot", bot, "--ledger-dir", led, "--private-dir", prv, "--signals-csv", os.path.join(tmp, "pc_signals.csv"), "--no-ots"])
        read = lambda: J.ledger_core.read_ledger(os.path.join(led, "ledger.jsonl"))
        lo2 = dict(lo, db=os.path.join(tmp, "l2.db"))
        kw2 = dict(kw, opts=lo2)
        ran = J.tick(now=tue, **kw2)
        st = status()
        with open(os.path.join(tmp, "pc_signals.csv"), encoding="utf-8") as f1, open(sig_csv, encoding="utf-8") as f2:
            same_csv = f1.read() == f2.read()
        check("장부 봉인: 지난주 파일뿐이면 기다리고, signals.csv 는 장부 원문에서 다시 만든다", code == 0 and len(read()) == 2 and len(ran) == 1 and ran[0][2]["ok"] and not ran[0][2]["done"]
              and st["결과"].startswith("기다리는 중") and "장부 이상 없음" in st["결과"] and "봉인됨)" in st["메모"] and same_csv and pulls == [bot]
              and J.tick(now=tue + timedelta(minutes=5), **kw2) == [], (code, ran, st, same_csv))
        signal_file(day.isoformat(), (day - timedelta(days=1)).isoformat(), "NEWSYM")
        ran = J.tick(now=tue + timedelta(minutes=30), **kw2)
        st, entries = status(), read()
        with open(sig_csv, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        everything = json.dumps(board.read(B.STATUS), ensure_ascii=False)
        check("장부 봉인: 이번 주 파일이 오면 봉인하고 건수와 해시만 적는다", len(ran) == 1 and ran[0][2]["done"] == {"seal:%s" % day.isoformat()} and len(entries) == 3
              and entries[-1]["kind"] == "weekly" and entries[-1]["week_asof"] == (day - timedelta(days=1)).isoformat()
              and st["결과"].startswith("봉인됨 · 기록 #3 (기준 주 %s: 청산 0 / 진입 후보 1 / 보유 1)" % (day - timedelta(days=1)).isoformat()) and entries[-1]["entry_hash"][:16] in st["결과"]
              and [r["symbol"] for r in rows] == ["OLDSYM", "NEWSYM"] and not any(x in everything for x in ("OLDSYM", "NEWSYM", "HOLDSYM"))
              and os.path.exists(os.path.join(prv, "000003_weekly_%s.json" % (day - timedelta(days=1)).isoformat()))
              and J.tick(now=tue + timedelta(minutes=60), **kw2) == [], (ran, st, entries[-1], rows))
        wed = tue + timedelta(days=1)
        ran = J.tick(now=wed, **kw2)
        st = status()
        good = len(ran) == 1 and ran[0][2]["ok"] and st["결과"].startswith("장부 이상 없음 · 기록 3건") and len(read()) == 3
        with open(os.path.join(led, "ledger.jsonl"), encoding="utf-8") as f:
            text = f.read()
        with open(os.path.join(led, "ledger.jsonl"), "w", encoding="utf-8", newline="\n") as f:
            f.write(text.replace('"n_holdings":1', '"n_holdings":2', 1))
        ran = J.tick(now=wed, opts=dict(lo, db=os.path.join(tmp, "l3.db")), jobs=only, board_opener=lambda: board, log=lambda x: None)
        st = status()
        check("장부 봉인: 다른 날은 점검만, 고친 흔적이 있으면 실패로 적는다", good and len(ran) == 1 and not ran[0][2]["ok"] and st["결과"].startswith("실패: 장부 점검에서 문제")
              and "entry_hash 불일치" in st["메모"], (good, ran, st))
        check("날짜 읽기: 줄표가 있든 없든, 파일 이름에서도", [str(J.as_date(x)) for x in ("2026-10-05", "20261005", "target_20261006.json", "주차 41")] == ["2026-10-05", "2026-10-05", "2026-10-06", "None"])

    # --- 엔진 봉인: 발표 전날 낮부터 실행기를 부르고, 조종판에는 엔진별 상태만 적는다
    with tempfile.TemporaryDirectory() as tmp:
        board = B.CsvBoard(os.path.join(tmp, "board"))
        for tab in (B.QUEUE, B.CANDIDATES, B.STATUS):
            board.ensure(tab)
        sched = os.path.join(tmp, "schedule_e.csv")
        with open(sched, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["event_kind", "title_ko", "ref_period", "release_at_utc", "targets"])
            w.writerow(["CPI", "소비자물가", "2099-01", "2099-02-11T13:30:00Z", "CPI_MOM CPI_CORE_MOM CPI_YOY"])   # 수요일 22:30 (한국 시간)
            w.writerow(["PPI", "생산자물가", "2099-01", "2099-02-12T13:30:00Z", "PPI_FD_MOM"])
            w.writerow(["EMP", "고용보고서", "2099-01", "2099-02-06T13:30:00Z", "NFP_CHG UNRATE"])
            w.writerow(["CLAIMS", "주간 신규 실업수당 청구", "2099-02-07", "2099-02-12T13:30:00Z", "CLAIMS_INIT"])
            w.writerow(["GDP_ADV", "GDP 속보치", "2098Q4", "2099-02-12T13:30:00Z", "GDP_ADV_QOQ"])
            w.writerow(["CPI", "소비자물가", "2099-01", "2099-03-01T13:30:00Z", "CPI_MOM"])   # 겹친 줄
            w.writerow(["CPI", "소비자물가", "2099-02", "읽을 수 없음", "CPI_MOM"])
        cpi_at, ppi_at = datetime(2099, 2, 10, 5, 30, tzinfo=timezone.utc), datetime(2099, 2, 11, 14, 0, tzinfo=timezone.utc)
        slots = {x.id: x for x in J.engine_slots(cpi_at, {"schedule": sched})}
        check("엔진 봉인 예정: 묶음을 만들 수 있는 발표만, 발표 32시간 전부터 발표 때까지, 겹친 줄은 하나",
              sorted(slots) == ["engine:CPI:2099-01", "engine:EMP:2099-01", "engine:PPI:2099-01"] and slots["engine:CPI:2099-01"].at == cpi_at
              and slots["engine:EMP:2099-01"].at == datetime(2099, 2, 5, 5, 30, tzinfo=timezone.utc) and slots["engine:CPI:2099-01"].tries >= 96
              and slots["engine:CPI:2099-01"].until == datetime(2099, 2, 11, 13, 30, tzinfo=timezone.utc) and slots["engine:CPI:2099-01"].gap == 20
              and not slots["engine:CPI:2099-01"].ctx["wait"], [(x.id, x.at) for x in slots.values()])
        check("엔진 봉인 예정: 묶음에 들어갈 다른 발표가 그 사이에 있으면 그 발표 30분 뒤부터",
              slots["engine:PPI:2099-01"].at == ppi_at and [(x["title"], x["ref"]) for x in slots["engine:PPI:2099-01"].ctx["wait"]] == [("소비자물가", "2099-01")], slots["engine:PPI:2099-01"])
        check("엔진 봉인은 작업표의 맨 뒤(남은 시간을 재서 쓴다)", J.JOBS[-1].id == "seal_forecasts" and J.JOBS[-1].item == "엔진 봉인")

        only_engine = [j for j in J.JOBS if j.id == "seal_forecasts"]
        clk, calls, answers, elog = SR.Clock(), [], [], []
        status = lambda: {r["항목"]: r for r in board.read(B.STATUS)}.get("엔진 봉인", {})

        def fake_run(kind, ref, o, env=None):
            calls.append((kind, ref, dict(o)))
            return answers.pop(0)

        def world(name, **more):
            # 서버에는 진짜 레시피 폴더·장부·발표값 파일이 있다. 시험이 그것을 읽지 않게 자리를 모두 임시 폴더로 준다
            return dict({"db": os.path.join(tmp, name + ".db"), "schedule": sched, "actuals": os.path.join(tmp, name + "_actuals.csv"), "no_ots": True,
                         "engines_dir": os.path.join(tmp, "no_engines"), "ledger_dir": os.path.join(tmp, "no_ledger"), "private_dir": os.path.join(tmp, "no_private"),
                         "runs_dir": os.path.join(tmp, "no_runs"), "clock": clk, "run_event": fake_run, "env": {}}, **more)
        kw = dict(jobs=only_engine, board_opener=lambda: board, log=elog.append)
        part = {"state": "pending", "ok": True, "result": "봉인함 · alpha@1 · CPI 2099-01 · 진행 중: beta@1 · 다시 돌리면 남은 것만 합니다", "memo": ["alpha@1: 맞는 답 5/5 · 받은 답 5"],
                "calls": 7, "stamped": None, "engines": {"alpha@1": "sealed", "beta@1": "pending"}}
        both = {"alpha@1": "sealed", "beta@1": "sealed"}
        eo = world("e1")
        check("때가 되기 전에는 부르지 않음", J.tick(now=cpi_at - timedelta(minutes=3), opts=eo, **kw) == [] and not calls)
        answers[:] = [part]
        ran = J.tick(now=cpi_at + timedelta(minutes=2), opts=eo, **kw)
        st = status()
        check("엔진 봉인: 한 엔진만 끝났으면 진행 중으로 적고 20분 뒤 이어서", len(ran) == 1 and ran[0][2]["done"] == set() and ran[0][2]["ok"]
              and st.get("결과") == "진행 중 · 소비자물가 2099-01 · 봉인된 엔진 1/2: alpha@1 · 나머지: beta@1(진행 중)" and "20분 뒤 이어서" in st.get("메모", "")
              and "맞는 답 5/5" in st["메모"] and "부른 횟수 7" in st["메모"], (ran, st))
        o1 = calls[0][2]
        check("엔진 봉인: 실행기에 쓸 시간 400초·엔진마다 5번 동시·폴더를 넘긴다", calls[0][:2] == ("CPI", "2099-01") and o1["budget_sec"] == 400 and o1["parallel"] == 5
              and o1["db"] == eo["db"] and o1["schedule"] == sched and o1["no_ots"] is True, o1)
        with open(os.path.join(store.ROOT, "scripts", "server_cron.sh"), encoding="utf-8") as f:
            cron_line = [x for x in f.read().splitlines() if "pipeline.console.jobs tick >>" in x and x.lstrip()[:1].isdigit()]
        check("엔진 봉인: 한 바퀴의 제한(600초)이 서버 예약 줄의 timeout 과 같다", len(cron_line) == 1 and " timeout %d " % J.TICK_LIMIT_SEC in cron_line[0]
              and J.ENGINE_BUDGET_SEC + J.ENGINE_RESERVE_SEC < J.TICK_LIMIT_SEC, cron_line)
        check("엔진 봉인: 간격(20분) 안에는 다시 부르지 않음", J.tick(now=cpi_at + timedelta(minutes=7), opts=eo, **kw) == [] and len(calls) == 1)
        answers[:] = [{"state": "sealed", "ok": True, "result": "봉인함 · CPI 2099-01 · beta@1 · 묶음 abc…", "memo": [], "calls": 5, "stamped": False, "engines": both}]
        ran = J.tick(now=cpi_at + timedelta(minutes=22), opts=eo, **kw)
        st = status()
        check("엔진 봉인: 봉인은 됐는데 외부 타임스탬프가 없으면 끝내지 않고 다시 받는다", ran[0][2]["done"] == set()
              and st["결과"] == "봉인됨 · 소비자물가 2099-01 · 봉인된 엔진 2/2: alpha@1, beta@1 · 외부 타임스탬프는 아직", (ran, st))
        answers[:] = [{"state": "already", "ok": True, "result": "이미 봉인됨 · CPI 2099-01 · alpha@1, beta@1", "memo": ["봉인: 타임스탬프 받음"], "calls": 0, "stamped": True, "engines": both}]
        ran = J.tick(now=cpi_at + timedelta(minutes=42), opts=eo, **kw)
        st = status()
        check("엔진 봉인: 두 엔진이 봉인되고 타임스탬프까지 받으면 끝", ran[0][2]["done"] == {"engine:CPI:2099-01"}
              and st["결과"] == "봉인됨 · 소비자물가 2099-01 · 봉인된 엔진 2/2: alpha@1, beta@1" and "다음: 수 2/11 23:00 생산자물가 2099-01 엔진 봉인" in st["메모"], (ran, st))
        check("엔진 봉인: 끝난 발표는 다시 부르지 않음", J.tick(now=cpi_at + timedelta(minutes=62), opts=eo, **kw) == [] and J.tick(now=cpi_at + timedelta(hours=20), opts=eo, **kw) == []
              and len(calls) == 3)

        # 한 바퀴(600초)와 봇 집행 시간 앞에서 쓸 시간을 줄인다
        calls.clear()
        answers[:] = [part]
        J.tick(now=cpi_at + timedelta(minutes=2), opts=world("e2", tick_started=clk() - 200), **kw)
        ran = J.tick(now=cpi_at + timedelta(minutes=2), opts=world("e3", tick_started=clk() - 480), **kw)
        st = status()
        check("엔진 봉인: 같은 바퀴의 다른 작업이 쓴 시간만큼 줄이고, 모자라면 부르지 않고 미룬다", len(calls) == 1 and calls[0][2]["budget_sec"] == 290
              and st["결과"] == "미룸 · 소비자물가 2099-01 — 이번 바퀴에 남은 시간이 모자람" and ran[0][2]["done"] == set() and ran[0][2]["ok"], (calls, st))
        calls.clear()
        answers[:] = [part, part]
        tue = datetime(2099, 2, 10, 14, 12, tzinfo=timezone.utc)   # 화요일 23:12 (한국 시간). 23:20부터 봇 집행 시간
        J.tick(now=tue, opts=world("e4"), **kw)
        J.tick(now=tue + timedelta(minutes=5), opts=world("e5"), **kw)
        J.tick(now=tue + timedelta(minutes=7), opts=world("e6"), **kw)
        check("엔진 봉인: 봇 집행 시간 전에 봉인까지 끝나도록 쓸 시간을 줄이고, 바로 앞에서는 부르지 않는다", tue.astimezone(J.KST).weekday() == 1
              and [c[2]["budget_sec"] for c in calls] == [370, 70] and status()["결과"].startswith("미룸"), (calls, status()))

        calls.clear()
        answers[:] = [part]
        need = world("e7", call_seconds=lambda folder: 360)
        J.tick(now=tue, opts=need, **kw)
        J.tick(now=tue + timedelta(minutes=5), opts=dict(need, db=os.path.join(tmp, "e8.db")), **kw)
        st = status()
        check("엔진 봉인: 남은 시간이 레시피의 한 번 부르는 시간보다 짧으면 부르지 않고 미룬다(실패로 적지 않는다)", [c[2]["budget_sec"] for c in calls] == [370]
              and st["결과"] == "미룸 · 소비자물가 2099-01 — 이번 바퀴에 남은 시간(70초)이 한 번 부르는 시간(360초)보다 짧음", (calls, st))
        ran = J.tick(now=cpi_at + timedelta(minutes=2), opts=world("e9", call_seconds=lambda folder: 500), **kw)
        st = status()
        check("엔진 봉인: 레시피의 한 번 부르는 시간이 한 바퀴보다 길면 부르지 않고 사람에게 알린다", len(calls) == 1 and not ran[0][2]["ok"] and ran[0][2]["done"] == set()
              and st["결과"].startswith("멈춤 · 소비자물가 2099-01 — 레시피의 한 번 부르는 시간(500초)"), st)
        calls.clear()
        J.tick(now=tue + timedelta(minutes=6, seconds=40), opts=world("e10", tick_started=clk() - 130), **kw)   # 23:18:40에 시작해 앞 작업이 130초를 썼다
        check("엔진 봉인: 앞 작업이 길어져 봇 집행 시간 안으로 들어갔으면 부르지 않는다", not calls and status()["결과"].startswith("미룸") and J.seconds_to_quiet(tue + timedelta(minutes=9)) == -60
              and J.seconds_to_quiet(tue + timedelta(minutes=40)) is None and J.seconds_to_quiet(tue - timedelta(days=1)) is None, (calls, status()))

        def slow_job(now, due, o):   # 엔진 봉인보다 먼저 도는 작업이 200초를 썼다
            clk.t += 200
            return {"ok": True, "result": "끝", "memo": [], "done": {x.id for x in due}, "lines": []}
        answers[:] = [part]
        first_job = J.Job("log_edits", "고친 기록", lambda now, o: [J.Slot("edits:x", now - timedelta(seconds=1), now + timedelta(hours=1), 20, 2, "앞 작업", None)], slow_job)
        J.tick(now=cpi_at + timedelta(minutes=2), opts=world("e11"), jobs=[first_job] + only_engine, board_opener=lambda: board, log=elog.append)
        check("엔진 봉인: 같은 바퀴의 앞 작업이 쓴 시간을 일꾼이 재서 넘긴다", [c[2]["budget_sec"] for c in calls] == [290], calls)

        # 끝날 때까지 20분마다 이어서 부른다
        calls.clear()
        lo = world("e12")
        lo.pop("no_ots")
        answers[:] = [dict(part, ok=False)] * 6 + [{"state": "already", "ok": True, "result": "이미 봉인됨", "memo": [], "calls": 0, "stamped": False, "engines": both}]
        for i in range(7):
            ran = J.tick(now=cpi_at + timedelta(minutes=2 + 20 * i), opts=lo, **kw)
        st = status()
        check("엔진 봉인: 끝날 때까지 20분마다 이어서 부르고, 오류가 있으면 결과 줄에 드러낸다", len(calls) == 7 and calls[0][2]["no_ots"] is False
              and J.engine_line("소비자물가 2099-01", dict(part, ok=False)).startswith("진행 중(오류 있음) · 소비자물가 2099-01 · 봉인된 엔진 1/2"), (len(calls), st))
        check("엔진 봉인: 앞서 봉인된 발표도 외부 타임스탬프가 없으면 끝내지 않는다", ran[0][2]["done"] == set() and st["결과"].endswith("외부 타임스탬프는 아직"), (ran, st))
        check("엔진 봉인: 엔진 하나로만 봉인되면 결과 줄에 알린다", J.engine_line("소비자물가 2099-01", {"state": "sealed", "ok": True, "engines": {"alpha@1": "sealed"}})
              == "봉인됨 · 소비자물가 2099-01 · 봉인된 엔진 1/1: alpha@1 · [주의] 이 발표에 쓰인 엔진이 1개뿐")

        # 두 발표가 겹치면 바퀴마다 차례를 바꾼다
        sched2 = os.path.join(tmp, "schedule_two.csv")
        with open(sched2, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["event_kind", "title_ko", "ref_period", "release_at_utc", "targets"])
            w.writerow(["CPI", "소비자물가", "2099-01", "2099-02-11T13:30:00Z", "CPI_MOM CPI_CORE_MOM CPI_YOY"])
            w.writerow(["EMP", "고용보고서", "2099-01", "2099-02-11T13:30:00Z", "NFP_CHG UNRATE"])
        calls.clear()
        two = world("e13", schedule=sched2)

        def busy_run(kind, ref, o, env=None):   # 먼저 돈 발표가 300초를 쓴다
            calls.append((kind, ref, dict(o)))
            clk.t += 300
            return part
        two["run_event"] = busy_run
        for i in range(2):
            J.tick(now=cpi_at + timedelta(minutes=2 + 20 * i), opts=two, **kw)
        check("엔진 봉인: 두 발표가 겹치면 차례를 바꿔 가며 하고, 뒤의 발표는 남은 시간만 쓴다", [c[0] for c in calls] in (["CPI", "EMP", "EMP", "CPI"], ["EMP", "CPI", "CPI", "EMP"])
              and [c[2]["budget_sec"] for c in calls] == [400, 190, 400, 190], [(c[0], c[2]["budget_sec"]) for c in calls])

        # 묶음에 들어갈 발표값(PPI 전날의 CPI)이 수집될 때까지 기다린다
        calls.clear()
        po = world("p1")

        def actuals(path, targets):
            with open(path, "w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                w.writerow(["event_kind", "ref_period", "target", "actual"])
                for t in targets:
                    w.writerow(["CPI", "2099-01", t, "0.3"])
        with open(po["actuals"], "wb") as f:   # 읽을 수 없는 파일도 "아직 수집되지 않음"으로 본다
            f.write(b"\xff\xfe\x00garbage")
        garbled = J.tick(now=ppi_at - timedelta(minutes=30), opts=po, **kw) == [] and J.run_engines(ppi_at + timedelta(minutes=1), [J.engine_slots(ppi_at, po)[-1]], po)["result"].startswith("기다리는 중")
        actuals(po["actuals"], ["CPI_MOM", "CPI_YOY"])
        ran = J.tick(now=ppi_at + timedelta(minutes=2), opts=po, **kw)
        st = status()
        check("엔진 봉인: 묶음에 들어갈 발표값이 아직 없으면 부르지 않고 기다린다", garbled and not calls and ran[0][2]["done"] == set() and ran[0][2]["ok"]
              and st["결과"] == "기다리는 중 · 생산자물가 2099-01 — 소비자물가 2099-01 발표값이 아직 수집되지 않음", (calls, st))
        actuals(po["actuals"], ["CPI_MOM", "CPI_CORE_MOM", "CPI_YOY"])
        answers[:] = [dict(part, result="진행 중 · PPI 2099-01", engines={"alpha@1": "pending", "beta@1": "pending"})]
        J.tick(now=ppi_at + timedelta(minutes=22), opts=po, **kw)
        check("엔진 봉인: 발표값이 수집되면 부른다", [c[:2] for c in calls] == [("PPI", "2099-01")] and status()["결과"].startswith("진행 중 · 생산자물가 2099-01 · 봉인된 엔진 0/2 · 나머지"), (calls, status()))
        calls.clear()
        answers[:] = [dict(part, engines={"alpha@1": "pending", "beta@1": "pending"})]
        late = datetime(2099, 2, 11, 22, 30, tzinfo=timezone.utc)   # PPI 봉인 마감 3시간 전
        J.tick(now=late, opts=world("p2"), **kw)
        check("엔진 봉인: 마감이 가까우면 더 기다리지 않고 있는 자료로 부른다", len(calls) == 1 and "소비자물가 2099-01 발표값 없이 부릅니다" in status()["메모"], (calls, status()))
        answers[:] = [{"state": "missed", "ok": False, "result": "미제출 · PPI 2099-01 · 봉인 마감이 지남", "memo": [], "calls": 0, "stamped": None, "engines": {}}]
        ran = J.tick(now=datetime(2099, 2, 12, 2, 0, tzinfo=timezone.utc), opts=world("p3"), **kw)   # PPI 봉인 마감 30분 뒤
        check("엔진 봉인: 마감 뒤에는 기다리지 않고 실행기에 넘겨 닫는다", len(calls) == 2 and ran[0][2]["done"] == {"engine:PPI:2099-01"} and status()["결과"].startswith("미제출 · 생산자물가 2099-01 — 미제출")
              and "발표값 없이" not in status()["메모"], (calls, status()))

        # 미제출·멈춤
        calls.clear()
        answers[:] = [{"state": "missed", "ok": False, "result": "미제출 — 형식이 맞는 답이 모자람 · CPI 2099-01 · 미제출: alpha@1, beta@1", "memo": [], "calls": 0, "stamped": None,
                       "engines": {"alpha@1": "missed", "beta@1": "missed"}}]
        mo = world("m1")
        final = datetime(2099, 2, 11, 1, 0, tzinfo=timezone.utc)
        ran = J.tick(now=final, opts=mo, **kw)
        st = status()
        check("엔진 봉인: 미제출은 그대로 적고 다시 부르지 않는다", ran[0][2]["done"] == {"engine:CPI:2099-01"} and not ran[0][2]["ok"]
              and st["결과"] == "미제출 · 소비자물가 2099-01 · 봉인된 엔진 0/2 · 나머지: alpha@1(미제출), beta@1(미제출)" and "뒤늦게 채우지 않습니다" in st["메모"]
              and J.tick(now=final + timedelta(minutes=25), opts=mo, **kw) == [], (ran, st))
        answers[:] = [{"state": "blocked", "ok": False, "result": "등록된 엔진이 없습니다. 레시피를 만든 뒤: register", "memo": [], "calls": 0, "stamped": None, "engines": {}}]
        ran = J.tick(now=cpi_at + timedelta(minutes=2), opts=world("m2"), **kw)
        st = status()
        check("엔진 봉인: 하지 못한 이유를 그대로 적고 20분 뒤 다시 본다", ran[0][2]["done"] == set() and st["결과"].startswith("멈춤 · 소비자물가 2099-01 — 등록된 엔진이 없습니다")
              and "20분 뒤 다시 시도 (1/" in st["메모"], (ran, st))
        check("엔진 봉인: 한 엔진만 봉인되고 닫힌 발표는 '일부만'으로", J.engine_line("소비자물가 2099-01", {"state": "already", "engines": {"alpha@1": "sealed", "beta@1": "missed"}})
              == "일부만 봉인됨 · 소비자물가 2099-01 · 봉인된 엔진 1/2: alpha@1 · 나머지: beta@1(미제출)")

        # 실제 실행기와 가짜 API로 끝까지: 장부에 봉인되고, 조종판·로그에는 값이 없다
        db = os.path.join(tmp, "facts.db")
        con = store.connect(db)
        parsed, _ = bls.parse(fake_response())
        bls.ingest(con, parsed, "2020-01-01T00:00:00Z", None)
        con.commit()
        con.close()
        wd = SR.World(tmp, "engine_job", db, sched)
        wd.api.plan = {"anthropic": SR.good("anthropic", SR.CPI, SR.A_VALS), "openai": SR.good("openai", SR.CPI, SR.O_VALS)}
        when = cpi_at + timedelta(minutes=2)
        real = lambda kind, ref, o, env=None: R.run_event(kind, ref, o, now=when, env=wd.env, send=wd.api.send, sleep=lambda x: None, build=wd.build)
        n0 = len(wd.ledger())
        elog.clear()
        real_opts = dict(wd.opts, run_event=real, actuals=os.path.join(tmp, "facts_actuals.csv"), env=wd.env)
        ran = J.tick(now=when, opts=dict(real_opts, secrets=J.secrets_of(wd.env)), **kw)
        st = status()
        con = store.connect(db)
        shown = json.dumps(st, ensure_ascii=False) + "\n".join(elog) + "\n".join(r[0] or "" for r in con.execute("SELECT detail FROM job_run"))
        con.close()
        entries = wd.ledger()
        check("엔진 봉인(실제 실행기): 두 엔진을 5번씩 부르고 장부에 봉인한다", len(ran) == 1 and ran[0][2]["done"] == {"engine:CPI:2099-01"} and wd.api.calls == {"anthropic": 5, "openai": 5}
              and len(entries) == n0 + 1 and entries[-1]["kind"] == "forecast" and st["결과"] == "봉인됨 · 소비자물가 2099-01 · 봉인된 엔진 2/2: alpha@1, beta@1", (ran, wd.api.calls, st))
        _, vals = wd.sealed_values(entries[-1])
        check("엔진 봉인(실제 실행기): 조종판과 로그에 엔진이 낸 값·키가 없다", vals[("alpha", "CPI_MOM")]["p50"] == 0.37 and vals[("beta", "CPI_MOM")]["p50"] == 0.57
              and not any(x in shown for x in ["%.2f" % (v + d) for v in SR.A_VALS + SR.O_VALS for d in (-0.1, 0, 0.1)] + ["KEY-A", "KEY-O"])
              and "기록 #" in shown and "slot=engine:CPI:2099-01" in shown, shown)
        check("엔진 봉인(실제 실행기): 다시 돌아도 부르지 않는다", J.tick(now=when + timedelta(minutes=25), opts=real_opts, **kw) == [] and wd.api.calls == {"anthropic": 5, "openai": 5})

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
