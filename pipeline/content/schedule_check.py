"""일정 체크: 다가오는 미국 발표·회의·휴장을 한국 시간 한 줄씩으로 만든다. 문장과 숫자는 전부 코드가 만든다.

    python -m pipeline.content.schedule_check              오늘부터 7일
    python -m pipeline.content.schedule_check --tonight    지금부터 18시간 안의 것만 ("오늘 밤 체크")
    python -m pipeline.content.schedule_check --days 14

- 일정은 data/forecast/schedule_*.csv (지표 발표)와 data/calendar/events_*.csv (연준·휴장)에서 읽는다.
- 지표 발표에는 DB에 있는 직전 발표값을 붙인다(없으면 붙이지 않는다). 방향·전망 문장은 만들지 않는다.
- 거래소·노동부 일정과 아직 대조하지 않은 줄에는 "(일정 확인 전)"이 붙는다. 그 줄은 대조한 뒤에 발행한다.
- DB가 있으면 만든 줄을 사실(fact, kind=schedule)로 남긴다. LLM은 이 사실만 보고 문장을 잇는다(D17).
"""
import argparse
import csv
import glob
import json
import os
import sys
from datetime import datetime, timedelta, timezone

from ..collect import catalog as C
from ..collect import store
from ..forecast import targets as T

VERSION = "schedule_check/0.1"
KST = timezone(timedelta(hours=9))
WEEKDAY = "월화수목금토일"


def setup_console():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except Exception:
            pass


def load_events(patterns):
    rows = []
    for pattern in patterns:
        for path in sorted(glob.glob(pattern)):
            with open(path, encoding="utf-8-sig", newline="") as f:
                for r in csv.DictReader(f):
                    r["_file"] = os.path.basename(path)
                    rows.append(r)
    rows.sort(key=lambda r: (r["release_at_utc"], r["event_kind"]))
    return rows


def ref_label(kind, ref):
    freq = T.EVENTS[kind][2] if kind in T.EVENTS else ""
    if freq == "M":
        return "%d월분" % int(ref[5:7])
    if freq == "Q":
        return "%s분기" % ref[-1]
    if freq == "W":
        return "%d/%d까지의 주" % (int(ref[5:7]), int(ref[8:10]))
    return ""


def fmt_value(target, value):
    places, unit = T.TARGETS[target][3], T.TARGETS[target][2]
    text = ("%." + str(places) + "f") % value
    if unit == "%":
        return text + "%"
    sign = "+" if (C.TARGET_SERIES.get(target, ("", ""))[1] == "nc1" and value > 0) else ""
    return "%s%s%s" % (sign, text, unit.replace(" ", ""))


def prev_values(con, kind, ref, cutoff):
    """그 발표의 대상별 직전 발표값. DB에 없으면 빈 목록."""
    out = []
    if con is None or kind not in T.EVENTS or T.EVENTS[kind][2] != "M":
        return out
    for target, v in T.TARGETS.items():
        if v[0] != kind or target not in C.TARGET_SERIES:
            continue
        rows = [(d, val) for d, val in store.asof(con, C.target_series_id(target), cutoff) if d[:7] < ref]
        if rows:
            out.append((target, T.TARGETS[target][1], rows[-1][0][:7], rows[-1][1]))
    return out


def when_text(r):
    kst = r["release_kst"]
    day = datetime.strptime(kst[:10], "%Y-%m-%d")
    head = "%s %d/%d" % (WEEKDAY[day.weekday()], day.month, day.day)
    if len(kst) > 10:
        return "%s %s" % (head, kst[11:16])
    return head + " (미국 날짜)"


def build(events, now, hours=None, days=7, con=None):
    """[{"text", "subject", "release_at_utc", "checked", "refs"}]. 문장은 여기서만 만들어진다."""
    end = now + (timedelta(hours=hours) if hours else timedelta(days=days))
    cutoff = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = []
    for r in events:
        at = datetime.strptime(r["release_at_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if not (now <= at < end):
            continue
        kind, ref = r["event_kind"], r["ref_period"]
        label = ref_label(kind, ref)
        text = "%s %s%s" % (when_text(r), r["title_ko"], " (%s)" % label if label else "")
        prev = prev_values(con, kind, ref, cutoff)
        if prev:
            text += " · 직전: " + ", ".join("%s %s" % (name, fmt_value(t, val)) for t, name, _, val in prev)
        note = (r.get("note") or "").strip()
        if note:
            text += " · " + note
        checked = str(r.get("checked", "1")) == "1"
        if not checked:
            text += " (일정 확인 전)"
        lines.append({"text": text, "subject": "%s:%s" % (kind, ref), "release_at_utc": r["release_at_utc"], "checked": checked,
                      "refs": [{"t": "schedule", "file": r["_file"], "event": kind, "ref": ref}] +
                              [{"t": "series", "id": C.target_series_id(t), "period": p} for t, _, p, _ in prev]})
    return lines


def save_facts(con, lines, as_of):
    """같은 날 같은 문장은 한 번만 남긴다. 확인 전인 일정은 발행 불가로 둔다."""
    added = 0
    for ln in lines:
        got = con.execute("SELECT 1 FROM fact WHERE kind='schedule' AND subject=? AND as_of=? AND text_ko=?", (ln["subject"], as_of, ln["text"])).fetchone()
        if got:
            continue
        con.execute("INSERT INTO fact(kind,subject,as_of,text_ko,refs,publishable,computed_by,created_at) VALUES ('schedule',?,?,?,?,?,?,?)",
                    (ln["subject"], as_of, ln["text"], json.dumps(ln["refs"], ensure_ascii=False), 1 if ln["checked"] else 0, VERSION, store.utc_now()))
        added += 1
    return added


def main(argv=None, now=None):
    setup_console()
    ap = argparse.ArgumentParser(description="일정 체크")
    ap.add_argument("--tonight", action="store_true", help="지금부터 18시간 안의 것만")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--db", default=store.DEFAULT_DB)
    ap.add_argument("--no-db", action="store_true", help="DB를 읽지도 쓰지도 않는다")
    ap.add_argument("--events", action="append", help="일정 파일 패턴 (기본: 발표 일정표와 연준·휴장 일정표)")
    a = ap.parse_args(argv)
    now = now or datetime.now(timezone.utc)
    patterns = a.events or [os.path.join(store.ROOT, "data", "forecast", "schedule_*.csv"),
                            os.path.join(store.ROOT, "data", "calendar", "events_*.csv")]
    con = None
    if not a.no_db and os.path.exists(a.db):
        con = store.connect(a.db)
    lines = build(load_events(patterns), now, hours=18 if a.tonight else None, days=a.days, con=con)
    title = "오늘 밤 체크" if a.tonight else "일정 체크 (%d일)" % a.days
    print("%s — %s 기준" % (title, now.astimezone(KST).strftime("%m/%d %H:%M")))
    if not lines:
        print("   해당하는 일정이 없습니다.")
    for ln in lines:
        print("   " + ln["text"])
    if con is not None:
        added = save_facts(con, lines, now.astimezone(KST).strftime("%Y-%m-%d"))
        con.commit()
        con.close()
        print("사실로 남긴 줄: %d" % added)
    elif not a.no_db:
        print("(DB가 아직 없어 직전 값은 붙이지 않았습니다. 수집을 한 번 돌리면 붙습니다.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
