"""엔진 예측 대상 발표 일정표를 만든다 (docs/12). 표준 라이브러리만 사용.

    python scripts/forecast_schedule.py            data/forecast/schedule_2026Q4.csv 를 쓰고 건수를 센다

날짜·시각(미 동부)은 각 기관 일정표에서 2026-10-05에 옮겨 적었다. 일정은 바뀔 수 있으므로
수집기(collect_calendar)가 생기면 그쪽이 기준이 되고 이 파일은 초기값으로만 쓴다.
  BLS https://www.bls.gov/schedule/news_release/current_year.asp
  BEA https://www.bea.gov/news/schedule/full
주간 실업수당 청구(노동부, 매주 목 08:30)는 요일 규칙으로 만든 값이라 '대조 전'으로 표시한다(휴일 주간은 앞당겨질 수 있다).
"""
import csv
import os
import sys
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from pipeline.forecast import targets as T  # noqa: E402

ET, KST = ZoneInfo("America/New_York"), ZoneInfo("Asia/Seoul")
BLS = "https://www.bls.gov/schedule/news_release/current_year.asp"
BEA = "https://www.bea.gov/news/schedule/full"
DOL = "https://www.dol.gov/ui/data.pdf"

# (event_kind, ref_period, 발표일(미 동부), 시각, 출처, 대조 여부)
ROWS = [
    ("CPI", "2026-09", "2026-10-14", "08:30", BLS, 1),
    ("CPI", "2026-10", "2026-11-10", "08:30", BLS, 1),
    ("CPI", "2026-11", "2026-12-10", "08:30", BLS, 1),
    ("EMP", "2026-10", "2026-11-06", "08:30", BLS, 1),
    ("EMP", "2026-11", "2026-12-04", "08:30", BLS, 1),
    ("PPI", "2026-09", "2026-10-15", "08:30", BLS, 1),
    ("PPI", "2026-10", "2026-11-13", "08:30", BLS, 1),
    ("PPI", "2026-11", "2026-12-15", "08:30", BLS, 1),
    ("PCE", "2026-09", "2026-10-29", "08:30", BEA, 1),
    ("PCE", "2026-10", "2026-11-25", "08:30", BEA, 1),
    ("PCE", "2026-11", "2026-12-23", "08:30", BEA, 1),
    ("GDP_ADV", "2026Q3", "2026-10-29", "08:30", BEA, 1),
]
# 주간 청구: 목요일 발표, 기준 주는 직전 토요일에 끝난다
d = date(2026, 10, 15)
while d <= date(2026, 12, 31):
    ROWS.append(("CLAIMS", (d - timedelta(days=5)).isoformat(), d.isoformat(), "08:30", DOL, 0))
    d += timedelta(days=7)

FIRST_SEAL = date(2026, 10, 13)   # 첫 봉인 목표일(한국 날짜)


def main():
    out = os.path.join(ROOT, "data", "forecast", "schedule_2026Q4.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    rows = []
    for kind, ref, day, hm, src, checked in ROWS:
        assert T.ref_period_ok(kind, ref), (kind, ref)
        local = datetime.strptime(day + " " + hm, "%Y-%m-%d %H:%M").replace(tzinfo=ET)
        targets = [t for t, v in T.TARGETS.items() if v[0] == kind]
        rows.append({"event_kind": kind, "title_ko": T.EVENTS[kind][0], "ref_period": ref,
                     "release_et": local.strftime("%Y-%m-%d %H:%M"),
                     "release_kst": local.astimezone(KST).strftime("%Y-%m-%d %H:%M"),
                     "release_at_utc": local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                     "tier": min(T.TARGETS[t][4] for t in targets), "targets": " ".join(targets),
                     "source_url": src, "checked": checked})
    rows.sort(key=lambda r: (r["release_at_utc"], r["event_kind"]))
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    live = [r for r in rows if r["release_kst"][:10] > FIRST_SEAL.isoformat()]
    span_days = (date(2026, 12, 31) - FIRST_SEAL).days
    print("일정표: %s (%d줄)" % (out, len(rows)))
    print("첫 봉인 %s 이후 ~ 12/31 (%d일)" % (FIRST_SEAL, span_days))
    for label, pick in (("핵심(묶음 1)", lambda r: r["tier"] == 1), ("보조(묶음 2)", lambda r: r["tier"] == 2), ("전체", lambda r: True)):
        ev = [r for r in live if pick(r)]
        vals = sum(len(r["targets"].split()) for r in ev)
        per_month = len(ev) / span_days * 30.4
        print("  %-12s 발표 %2d회, 값 %2d개 → 월 %.1f회, 발표 %d회까지 약 %.0f개월"
              % (label, len(ev), vals, per_month, T.MIN_SCORED_EVENTS, T.MIN_SCORED_EVENTS / per_month))
    by = {}
    for r in live:
        by[r["event_kind"]] = by.get(r["event_kind"], 0) + 1
    print("  종류별: " + ", ".join("%s %d" % kv for kv in sorted(by.items())))
    nxt = live[0]
    print("  첫 대상: %s %s — 한국 시간 %s 발표" % (nxt["title_ko"], nxt["ref_period"], nxt["release_kst"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
