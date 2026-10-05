"""일정 체크가 이 PC에서 제대로 도는지 임시 폴더에서 확인한다. 인터넷과 실제 DB를 쓰지 않는다.

    python -m pipeline.content.selftest
"""
import csv
import os
import sys
import tempfile
from datetime import datetime, timezone

from ..collect import bls, store
from ..collect.selftest import fake_response
from . import schedule_check as sc

FIELDS = ["event_kind", "title_ko", "ref_period", "release_et", "release_kst", "release_at_utc", "tier", "targets", "source_url", "checked", "note"]


def main():
    ok = []

    def check(name, cond, detail=""):
        ok.append(bool(cond))
        print("%s %s%s" % ("  통과" if cond else "**실패", name, "" if cond else " — " + str(detail).strip()[-400:]))

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "schedule_test.csv")
        rows = [
            ["CPI", "소비자물가", "2099-01", "", "2099-02-11 22:30", "2099-02-11T13:30:00Z", 1, "CPI_MOM CPI_CORE_MOM CPI_YOY", "u", 1, ""],
            ["EMP", "고용보고서", "2099-01", "", "2099-02-06 22:30", "2099-02-06T13:30:00Z", 1, "NFP_CHG UNRATE", "u", 1, ""],
            ["CLAIMS", "주간 신규 실업수당 청구", "2099-01-31", "", "2099-02-05 22:30", "2099-02-05T13:30:00Z", 2, "CLAIMS_INIT", "u", 0, ""],
            ["FOMC", "연준 금리 결정(FOMC)", "2099-01", "", "2099-02-05 04:00", "2099-02-04T19:00:00Z", "", "", "u", 1, "성명 발표"],
            ["HOLIDAY", "미국장 휴장", "2099-02-16", "", "2099-02-16", "2099-02-16T05:00:00Z", "", "", "u", 0, ""],
            ["GDP_ADV", "GDP 속보치", "2098Q4", "", "2099-03-30 21:30", "2099-03-30T12:30:00Z", 1, "GDP_ADV_QOQ", "u", 1, ""],
        ]
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(FIELDS)
            w.writerows(rows)
        events = sc.load_events([path])
        now = datetime(2099, 2, 4, 3, 0, tzinfo=timezone.utc)   # 한국 시간 2/4 정오

        lines = sc.build(events, now, days=7)
        texts = [ln["text"] for ln in lines]
        check("7일 안의 일정만, 시간순", len(lines) == 3 and texts[0].startswith("목 2/5 04:00 연준") and "고용보고서 (1월분)" in texts[2], texts)
        check("확인 전인 일정에 표시", texts[1].endswith("(일정 확인 전)") and "1/31까지의 주" in texts[1] and lines[1]["checked"] is False, texts[1])
        check("DB가 없으면 직전 값을 붙이지 않음", "직전" not in " ".join(texts))
        tonight = sc.build(events, now, hours=18)
        check("오늘 밤 체크: 18시간 안의 것만", [ln["subject"] for ln in tonight] == ["FOMC:2099-01"], tonight)
        far = sc.build(events, now, days=60)
        check("하루 전체 일정과 분기 표기", any("(미국 날짜) 미국장 휴장" in ln["text"] for ln in far) and any("GDP 속보치 (4분기)" in ln["text"] for ln in far), [ln["text"] for ln in far])

        con = store.connect(os.path.join(tmp, "t.db"))
        parsed, _ = bls.parse(fake_response())
        bls.ingest(con, parsed, "2099-01-14T14:00:00Z", None)
        con.commit()
        lines = sc.build(events, now, days=10, con=con)
        cpi = [ln for ln in lines if ln["subject"] == "CPI:2099-01"][0]
        emp = [ln for ln in lines if ln["subject"] == "EMP:2099-01"][0]
        want = dict(store.asof(con, "BLS.CUSR0000SA0.pc1", "2099-02-04T03:00:00Z"))["2098-12-31"]
        check("직전 발표값을 DB에서 붙임(발표 자릿수)", ("직전: CPI 전월비(계절조정) %.1f%%" % want) in cpi["text"] and cpi["text"].count("%") == 3, cpi["text"])
        check("증감은 부호와 단위", "비농업 취업자 증감 +" in emp["text"] and "천명" in emp["text"] and "실업률" in emp["text"], emp["text"])
        check("직전 값은 기준 기간보다 앞선 달", all(r["period"] == "2098-12" for r in cpi["refs"] if r["t"] == "series"), cpi["refs"])
        n1 = sc.save_facts(con, lines, "2099-02-04")
        n2 = sc.save_facts(con, lines, "2099-02-04")
        pub = dict(con.execute("SELECT subject, publishable FROM fact WHERE kind='schedule'").fetchall())
        check("사실로 남김: 중복 없음, 확인 전 일정은 발행 불가", n1 == len(lines) and n2 == 0 and pub["CPI:2099-01"] == 1 and pub["CLAIMS:2099-01-31"] == 0, (n1, n2, pub))
        con.close()

    print("\n시험 %d건 중 %d건 통과" % (len(ok), sum(ok)))
    return 0 if all(ok) else 1


if __name__ == "__main__":
    sys.exit(main())
