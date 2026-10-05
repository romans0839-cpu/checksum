"""일정 체크에 쓰는 발표 외 일정(연준 회의, 휴장, 서머타임)을 표로 만든다. 표준 라이브러리만 사용.

    python scripts/calendar_events.py        data/calendar/events_2026Q4.csv 를 쓴다 (Windows는 pip install tzdata 필요)

날짜는 2026-10-05에 옮겨 적었다. 연준 회의 날짜는 연준 일정표에서 확인했고(성명 발표는 통상 둘째 날 14:00 미 동부),
휴장·조기 폐장은 거래소 일정표와 아직 대조하지 않아 '확인 전'으로 표시했다.
  연준 https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
  거래소 https://www.nyse.com/markets/hours-calendars
"""
import csv
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ET, KST = ZoneInfo("America/New_York"), ZoneInfo("Asia/Seoul")
FED = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
NYSE = "https://www.nyse.com/markets/hours-calendars"

# (event_kind, 이름, 기준, 미 동부 날짜, 시각 또는 "", 출처, 확인 여부, 메모)
ROWS = [
    ("FOMC", "연준 금리 결정(FOMC)", "2026-10", "2026-10-28", "14:00", FED, 1, "성명 발표. 기자회견은 30분 뒤"),
    ("FOMC", "연준 금리 결정(FOMC) + 경제전망", "2026-12", "2026-12-09", "14:00", FED, 1, "경제전망(점도표) 포함. 기자회견은 30분 뒤"),
    ("DST", "미국 서머타임 끝", "2026-11", "2026-11-01", "", NYSE, 1, "이날부터 미국 일정이 한국 시간으로 1시간씩 늦어진다(개장 23:30, 발표 22:30)"),
    ("HOLIDAY", "미국장 휴장(추수감사절)", "2026-11-26", "2026-11-26", "", NYSE, 0, ""),
    ("EARLY_CLOSE", "미국장 조기 폐장(추수감사절 다음 날)", "2026-11-27", "2026-11-27", "13:00", NYSE, 0, "폐장 시각"),
    ("EARLY_CLOSE", "미국장 조기 폐장(성탄절 전날)", "2026-12-24", "2026-12-24", "13:00", NYSE, 0, "폐장 시각"),
    ("HOLIDAY", "미국장 휴장(성탄절)", "2026-12-25", "2026-12-25", "", NYSE, 0, ""),
]
FIELDS = ["event_kind", "title_ko", "ref_period", "release_et", "release_kst", "release_at_utc", "tier", "targets", "source_url", "checked", "note"]


def main():
    out = os.path.join(ROOT, "data", "calendar", "events_2026Q4.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    rows = []
    for kind, title, ref, day, hm, src, checked, note in ROWS:
        if hm:
            local = datetime.strptime(day + " " + hm, "%Y-%m-%d %H:%M").replace(tzinfo=ET)
            et, kst = local.strftime("%Y-%m-%d %H:%M"), local.astimezone(KST).strftime("%Y-%m-%d %H:%M")
            utc = local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        else:   # 하루 전체. 날짜는 미국 날짜다
            et, kst = day, day
            utc = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=ET).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        rows.append({"event_kind": kind, "title_ko": title, "ref_period": ref, "release_et": et, "release_kst": kst, "release_at_utc": utc,
                     "tier": "", "targets": "", "source_url": src, "checked": checked, "note": note})
    rows.sort(key=lambda r: r["release_at_utc"])
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print("일정표: %s (%d줄)" % (out, len(rows)))
    for r in rows:
        print("   %s  %s  %s" % (r["release_kst"], r["title_ko"], "" if str(r["checked"]) == "1" else "(확인 전)"))


if __name__ == "__main__":
    main()
