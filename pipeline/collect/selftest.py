"""수집 → DB → 사실 묶음이 이 PC에서 제대로 도는지 임시 폴더에서 확인한다. 인터넷과 실제 DB를 쓰지 않는다.

    python -m pipeline.collect.selftest

노동통계국 응답과 같은 모양의 가짜 응답(2094-01 ~ 2098-12)을 만들어 쓴다. 실제 API 응답은 첫 수집 때
`python -m pipeline.collect.bls --dry-run` 으로 따로 확인한다.
"""
import contextlib
import csv
import hashlib
import io
import json
import os
import sys
import tempfile
import urllib.error
from datetime import datetime, timezone
from decimal import Decimal

from ..forecast import bundle
from . import bls, store, trends
from . import catalog as C


def fake_response(with_titles=True, bump=None, bad_title=None):
    series = []
    for n, (bls_id, group, name_ko, unit, keywords, derived) in enumerate(C.BLS):
        data = []
        for i in range(60):
            year, month = 2094 + i // 12, i % 12 + 1
            if unit == "지수":
                value = "%.3f" % (200 + n + i * (0.35 + 0.01 * n) + (0.2 if month in (1, 6) else 0.0))
            elif unit == "천 명":
                value = "%d" % (150000 + n * 100 + i * 150 + (40 if month % 3 == 0 else 0))
            elif unit == "%":
                value = "%.1f" % (4.0 + 0.1 * ((i + n) % 4))
            else:
                value = "%.2f" % (30 + n + i * 0.09)
            if bls_id.startswith("CU") and (year, month) == (2097, 10):
                value = "-"   # 조사가 없었던 달
            if bump and bump == (bls_id, year, month):
                value = "%.3f" % (float(value) + 0.5)
            data.append({"year": str(year), "period": "M%02d" % month, "periodName": "x", "value": value, "footnotes": [{}]})
        data.append({"year": "2098", "period": "M13", "periodName": "Annual", "value": "999.000", "footnotes": [{}]})
        data.reverse()   # 실제 응답은 최신 달이 먼저 온다
        item = {"seriesID": bls_id, "data": data}
        if with_titles:
            title = ", ".join(keywords) + " in U.S. city average, seasonally adjusted"
            if bad_title == bls_id:
                title = "Something else entirely"
            item["catalog"] = {"series_title": title.capitalize(), "series_id": bls_id}
        series.append(item)
    return {"status": "REQUEST_SUCCEEDED", "responseTime": 100, "message": [], "Results": {"series": series}}


def run(fn, argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = fn(argv)
    return code, buf.getvalue()


def main():
    ok = []

    def check(name, cond, detail=""):
        ok.append(bool(cond))
        print("%s %s%s" % ("  통과" if cond else "**실패", name, "" if cond else " — " + str(detail).strip()[-400:]))

    # --- 읽기와 계산
    parsed, _ = bls.parse(fake_response())
    cpi = parsed["CUSR0000SA0"]
    check("응답 읽기: 계열 수, 연평균(M13)과 빈 달('-') 제외", len(parsed) == len(C.BLS) and len(cpi["values"]) == 59 and (2097, 10) not in cpi["values"])
    d = bls.derive({(2098, 1): "100.000", (2098, 2): "100.250", (2098, 3): "100.100", (2097, 2): "98.000"}, "pc1")
    check("전월비: 발표 지수로 계산, 소수 1자리 반올림(0.25 → 0.3)", d[(2098, 2)] == Decimal("0.3") and d[(2098, 3)] == Decimal("-0.1") and (2098, 1) not in d, d)
    d12 = bls.derive({(2098, 2): "100.250", (2097, 2): "98.000"}, "pc12")
    check("전년비", d12 == {(2098, 2): Decimal("2.3")}, d12)
    check("빈 달 다음 달은 전월비를 만들지 않음", (2097, 11) not in bls.derive(cpi["values"], "pc1") and (2097, 12) in bls.derive(cpi["values"], "pc1"))
    check("증감(천 명)", bls.derive({(2098, 1): "150000", (2098, 2): "150190"}, "nc1")[(2098, 2)] == Decimal("190"))

    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "t.db")
        con = store.connect(db)
        t1, t2 = "2099-01-14T14:00:00Z", "2099-02-11T14:00:00Z"
        rep = bls.ingest(con, parsed, t1, None)
        check("저장: 새 값이 들어가고 불일치·누락 없음", rep["new"] > 3000 and not rep["mismatch"] and not rep["missing"] and rep["revised"] == 0, rep)
        rep2 = bls.ingest(con, parsed, "2099-01-15T14:00:00Z", None)
        check("같은 응답을 다시 넣으면 한 줄도 늘지 않음", rep2["new"] == 0 and rep2["revised"] == 0 and rep2["same"] == rep["new"], rep2)
        con.commit()

        # --- 사실 묶음
        b1, problems = bundle.build(con, "CPI", "2099-01", "2099-01-20T00:00:00Z", "2099-02-11T13:30:00Z")
        check("묶음 생성", b1 is not None and not problems, problems)
        if b1:
            periods = [h["period"] for t in b1["history"].values() for h in t]
            comp = [v["period"] for blk in b1["components"] for v in blk["values"]]
            check("묶음: 대상 3개, 과거 36개월 이내, 기준 기간 값 없음", len(b1["targets"]) == 3 and max(len(h) for h in b1["history"].values()) == 36
                  and max(periods + comp) == "2098-12", (len(b1["targets"]), max(periods + comp)))
            check("묶음: 기준선이 될 직전 값과 전년비 재료", all(t["prev"]["period"] == "2098-12" for t in b1["targets"])
                  and b1["yoy_ingredients"]["CUUR0000SA0"]["index_same_month_last_year"]["period"] == "2098-01"
                  and b1["yoy_ingredients"]["CUUR0000SA0"]["index_prev_month"]["value"] is not None, b1["targets"])
            check("묶음: 관련 묶음(생산자물가·고용) 포함", len(b1["related"]["PPI"]) == 4 and len(b1["related"]["EMP"]) == 6, {k: len(v) for k, v in b1["related"].items()})
            again, _ = bundle.build(con, "CPI", "2099-01", "2099-01-20T00:00:00Z", "2099-02-11T13:30:00Z")
            check("같은 DB·같은 마감이면 같은 해시", hashlib.sha256(bundle.dumps(b1)).hexdigest() == hashlib.sha256(bundle.dumps(again)).hexdigest())
        _, problems = bundle.build(con, "CPI", "2098-12", "2099-01-20T00:00:00Z")
        check("이미 발표된 기간은 묶음을 만들지 않음", problems and "이미 알려져" in problems[0], problems)
        _, problems = bundle.build(con, "CPI", "2099-01", "2099-01-01T00:00:00Z")
        check("마감 시각 전에 알려진 값이 없으면 만들지 않음", bool(problems), problems)
        _, problems = bundle.build(con, "GDP_ADV", "2098Q4", "2099-01-20T00:00:00Z")
        check("수집기가 없는 발표는 만들지 않음", bool(problems), problems)

        # --- 수정치: 덮어쓰지 않고 쌓인다
        revised, _ = bls.parse(fake_response(bump=("CUSR0000SA0", 2098, 12)))
        rep3 = bls.ingest(con, revised, t2, None)
        con.commit()
        sid = C.series_id("CUSR0000SA0")
        before = dict(store.asof(con, sid, "2099-01-20T00:00:00Z"))["2098-12-31"]
        after = dict(store.asof(con, sid, "2099-03-01T00:00:00Z"))["2098-12-31"]
        check("수정치는 새 줄로 쌓이고 시점별로 다르게 보임", rep3["revised"] >= 2 and abs(after - before - 0.5) < 1e-6, (rep3["revised"], before, after))
        b2, _ = bundle.build(con, "CPI", "2099-01", "2099-01-20T00:00:00Z", "2099-02-11T13:30:00Z")
        check("수정 전 시각으로 만든 묶음은 수정 뒤에도 그대로", b1 and b2 and bundle.dumps(b1) == bundle.dumps(b2))
        b3, _ = bundle.build(con, "CPI", "2099-01", "2099-03-01T00:00:00Z", "2099-02-11T13:30:00Z")
        check("마감 시각을 수정 뒤로 잡으면 묶음이 달라짐", b3 and bundle.dumps(b3) != bundle.dumps(b1))

        # --- 처음 발표값 기록
        sched = os.path.join(tmp, "schedule_test.csv")
        with open(sched, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["event_kind", "title_ko", "ref_period", "release_et", "release_kst", "release_at_utc", "tier", "targets", "source_url", "checked"])
            w.writerow(["CPI", "x", "2098-12", "", "", "2099-01-14T13:30:00Z", 1, "CPI_MOM CPI_CORE_MOM CPI_YOY", "u", 1])
            w.writerow(["CPI", "x", "2098-11", "", "", "2098-12-10T13:30:00Z", 1, "CPI_MOM", "u", 1])
            w.writerow(["CPI", "x", "2099-01", "", "", "2099-02-11T13:30:00Z", 1, "CPI_MOM", "u", 1])
            w.writerow(["GDP_ADV", "x", "2098Q4", "", "", "2099-01-10T13:30:00Z", 1, "GDP_ADV_QOQ", "u", 1])
        actuals = os.path.join(tmp, "actuals.csv")
        now = datetime(2099, 2, 1, tzinfo=timezone.utc)
        added, notes = bls.record_actuals(con, sched, actuals, now)
        first = dict(store.asof(con, C.series_id("CUSR0000SA0", "pc1"), "2099-01-20T00:00:00Z"))["2098-12-31"]
        row = {r["target"]: r for r in added}
        check("처음 발표값 3개 기록(수정 전 값, 발표 자릿수)", len(added) == 3 and row["CPI_MOM"]["actual"] == "%.1f" % first
              and row["CPI_MOM"]["known_at_utc"] == t1, added)
        check("늦게 받은 값은 넣지 않고 알림", any("2098-11" in n and "넣지 않았습니다" in n for n in notes), notes)
        added2, _ = bls.record_actuals(con, sched, actuals, now)
        check("다시 돌려도 중복 없음", not added2 and sum(1 for _ in open(actuals, encoding="utf-8")) == 4)

        # --- 제목 대조
        con2 = store.connect(os.path.join(tmp, "t2.db"))
        bad, _ = bls.parse(fake_response(bad_title="CUSR0000SETA02"))
        repb = bls.ingest(con2, bad, t1, None)
        bb, _ = bundle.build(con2, "CPI", "2099-01", "2099-01-20T00:00:00Z")
        check("제목이 다른 계열은 표시되고 묶음에서 빠짐", len(repb["mismatch"]) == 1 and bb and any("CUSR0000SETA02" in s for s in bb["coverage"]["series_skipped"])
              and not any(blk["series"] == "CUSR0000SETA02" for blk in bb["components"]), repb["mismatch"])
        con3 = store.connect(os.path.join(tmp, "t3.db"))
        plain, _ = bls.parse(fake_response(with_titles=False))
        bls.ingest(con3, plain, t1, None)
        _, problems = bundle.build(con3, "CPI", "2099-01", "2099-01-20T00:00:00Z")
        bu, _ = bundle.build(con3, "CPI", "2099-01", "2099-01-20T00:00:00Z", allow_unverified=True)
        check("제목을 대조하지 못하면 기본은 거부, 허용 옵션은 기록에 남음", bool(problems) and bu and bu["coverage"]["allow_unverified"] is True, problems)
        for c in (con, con2, con3):
            c.close()

        # --- 명령으로 끝까지
        fixture = os.path.join(tmp, "resp.json")
        with open(fixture, "w", encoding="utf-8") as f:
            json.dump(fake_response(), f)
        db4 = os.path.join(tmp, "t4.db")
        args = ["--from-file", fixture, "--db", db4, "--raw-dir", os.path.join(tmp, "raw"), "--schedule", sched, "--actuals", os.path.join(tmp, "a4.csv")]
        c, out = run(bls.main, args + ["--dry-run"])
        check("명령: --dry-run 은 DB를 만들지 않음", c == 0 and not os.path.exists(db4), out)
        c, out = run(bls.main, args)
        check("명령: 수집", c == 0 and "새 값" in out and "가장 최근 달: 2098-12" in out and len(os.listdir(os.path.join(tmp, "raw"))) == 1, out)
        c, out = run(bundle.main, ["--event", "CPI", "--ref", "2099-01", "--db", db4, "--schedule", sched, "--out-dir", os.path.join(tmp, "bundles")])
        check("명령: 묶음", c == 0 and "sha256" in out and len(os.listdir(os.path.join(tmp, "bundles"))) == 1, out)

        # --- collect(): 서버의 예약 작업이 부르는 길. 요약을 돌려주고, 키는 어디에도 남기지 않는다
        said = []
        d5 = os.path.join(tmp, "t5.db")
        base = dict(db=d5, raw_dir=os.path.join(tmp, "raw5"), schedule=sched, actuals=os.path.join(tmp, "a5.csv"), say=said.append)
        when = datetime(2099, 1, 14, 13, 32, tzinfo=timezone.utc)
        code, rep = bls.collect(from_file=fixture, now=when, **base)
        check("collect(): 요약(새 값, 최근 달, 처음 발표값, 알림)", code == 0 and rep["ok"] and rep["new"] > 3000 and rep["newest"] == (2098, 12)
              and sorted(r["target"] for r in rep["added"]) == ["CPI_CORE_MOM", "CPI_MOM", "CPI_YOY"] and len(rep["notes"]) == 1 and not rep["mismatch"], rep)
        secret = "0123456789abcdef0123456789abcdef"

        def bad_key(ids, y0, y1, key):
            body = {"status": "REQUEST_NOT_PROCESSED", "message": ["The key:%s provided by the User is invalid." % key], "Results": {}}
            return 200, json.dumps(body).encode("utf-8"), "u"

        def down(ids, y0, y1, key):
            raise urllib.error.URLError("timed out")

        def with_note(ids, y0, y1, key):
            doc = fake_response()
            doc["message"] = ["request by %s accepted" % key]
            return 200, json.dumps(doc).encode("utf-8"), "u"
        base["db"], base["raw_dir"] = os.path.join(tmp, "t6.db"), os.path.join(tmp, "raw6")
        said.clear()
        c1, r1 = bls.collect(key=secret, fetcher=bad_key, now=when, **base)
        c2, r2 = bls.collect(key=secret, fetcher=down, now=when, **base)
        c3, r3 = bls.collect(key="", fetcher=down, now=when, **base)
        check("collect(): 잘못된 키·접속 실패·키 없음은 이유와 함께 실패, 아무것도 쓰지 않음", (c1, r1["error_kind"]) == (1, "api") and (c2, r2["error_kind"]) == (1, "network")
              and (c3, r3["error_kind"]) == (2, "no_key") and not os.path.exists(base["db"]) and not os.path.exists(base["raw_dir"]), (c1, r1["error"], c2, r2["error"], c3))
        c4, r4 = bls.collect(key=secret, fetcher=with_note, now=when, **base)
        saved = open(r4["raw_path"], "rb").read().decode("utf-8") if r4["raw_path"] else ""
        check("collect(): 키는 화면·요약·원문 어디에도 남지 않음", c4 == 0 and "accepted" in saved and secret not in saved + " ".join(said) + json.dumps([r1, r2, r3, r4], default=str, ensure_ascii=False),
              [x for x in said if secret in x])

    # --- 뜨는 검색어
    feed = ("""<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:atom="http://www.w3.org/2005/Atom" xmlns:ht="https://trends.google.com/trending/rss" version="2.0"><channel>
<title>Daily Search Trends</title>
<item><title>스테이블코인</title><ht:approx_traffic>1000+</ht:approx_traffic><pubDate>Mon, 5 Oct 2026 01:40:00 -0700</pubDate>
 <ht:picture>https://example.com/p.jpg</ht:picture>
 <ht:news_item><ht:news_item_title>기업이 쓰기 시작했다</ht:news_item_title><ht:news_item_url>https://example.com/a1</ht:news_item_url><ht:news_item_source>가나신문</ht:news_item_source></ht:news_item>
 <ht:news_item><ht:news_item_title>카드 결제액 성장</ht:news_item_title><ht:news_item_url>https://example.com/a2</ht:news_item_url><ht:news_item_source>다라일보</ht:news_item_source></ht:news_item></item>
<item><title>실종자</title><ht:approx_traffic>500+</ht:approx_traffic><pubDate>Mon, 5 Oct 2026 01:20:00 -0700</pubDate>
 <ht:news_item><ht:news_item_title>어선 전복 2명 실종</ht:news_item_title><ht:news_item_url>https://example.com/b1</ht:news_item_url><ht:news_item_source>마바뉴스</ht:news_item_source></ht:news_item></item>
<item><title>ken paxton</title><ht:approx_traffic>2,000+</ht:approx_traffic><pubDate>bad date</pubDate>
 <ht:news_item><ht:news_item_title>Senate campaign ad</ht:news_item_title><ht:news_item_url>https://example.com/c1</ht:news_item_url><ht:news_item_source>News</ht:news_item_source></ht:news_item></item>
</channel></rss>""").encode("utf-8")
    recs = trends.parse(feed)
    check("뜨는 검색어 읽기: 검색어·어림 검색량·시각·기사 링크", len(recs) == 3 and recs[0]["term"] == "스테이블코인" and recs[0]["approx_traffic"] == 1000
          and recs[0]["pub_at"] == "2026-10-05T08:40:00Z" and len(recs[0]["news"]) == 2 and recs[2]["approx_traffic"] == 2000 and recs[2]["pub_at"] is None, recs)
    check("제외 표시: 재난·정치는 표시하고 나머지는 비움", [trends.flag_of(r) for r in recs] == ["", "disaster", "politics"], [trends.flag_of(r) for r in recs])
    loan = {"term": "student loan", "news": [{"title": "Deadline to reduce your student loan interest rate extended", "source": "x", "url": "https://example.com/d"}]}
    died = {"term": "someone death", "news": [{"title": "Whistleblower dies", "source": "x", "url": "https://example.com/e"}]}
    check("영어는 낱말 단위로만 표시(deadline 은 재난이 아님)", trends.flag_of(loan) == "" and trends.flag_of(died) == "disaster", (trends.flag_of(loan), trends.flag_of(died)))
    with tempfile.TemporaryDirectory() as tmp:
        con = store.connect(os.path.join(tmp, "tr.db"))
        r1 = trends.ingest(con, "KR", recs, "2026-10-05T12:00:00Z")
        r2 = trends.ingest(con, "KR", recs, "2026-10-05T15:00:00Z")
        con.commit()
        n_doc = con.execute("SELECT COUNT(*) FROM document").fetchone()[0]
        n_body = con.execute("SELECT COUNT(*) FROM document WHERE summary_own NOT IN ('가나신문','다라일보','마바뉴스','News')").fetchone()[0]
        seen = con.execute("SELECT first_seen_at, last_seen_at FROM trend WHERE term='스테이블코인'").fetchone()
        check("뜨는 검색어 저장: 다시 받아도 중복 없이 마지막으로 본 시각만 바뀜", r1 == (3, 0, 4) and r2 == (0, 3, 0) and n_doc == 4
              and seen == ("2026-10-05T12:00:00Z", "2026-10-05T15:00:00Z"), (r1, r2, n_doc, seen))
        check("기사는 제목·출처·링크만 저장", n_body == 0 and con.execute("SELECT COUNT(*) FROM doc_link WHERE ref_id LIKE 'trend:%'").fetchone()[0] == 4)
        con.close()
        fpath = os.path.join(tmp, "feed.xml")
        with open(fpath, "wb") as f:
            f.write(feed)
        c, out = run(trends.main, ["--from-file", fpath, "--geo", "KR", "--db", os.path.join(tmp, "tr2.db")])
        check("명령: 뜨는 검색어 수집", c == 0 and "새 검색어 3" in out and "(disaster)" in out, out)

    print("\n시험 %d건 중 %d건 통과" % (len(ok), sum(ok)))
    return 0 if all(ok) else 1


if __name__ == "__main__":
    sys.exit(main())
