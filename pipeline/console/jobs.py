"""예약 작업 일꾼: 때가 된 서버 작업을 돌리고 결과를 조종판 '오늘 현황'에 적는다 (docs/15 §5).

    python -m pipeline.console.jobs tick              때가 된 작업을 돌린다 (서버 cron 5분마다)
    python -m pipeline.console.jobs tick --dry-run    돌리지 않고 무엇을 돌릴지만 보여 준다
    python -m pipeline.console.jobs plan              앞으로 8일의 예정 (한국 시간)
    python -m pipeline.console.jobs run collect_indicators    시각과 무관하게 지금 한 번

규칙
- 예정은 cron 이 아니라 이 파일과 일정표(data/forecast/schedule_*.csv)가 정한다. 서버의 cron 은 5분마다 tick 만 부른다.
  작업을 더하거나 시각을 바꿀 때 서버에 들어갈 필요가 없다(저장소에 올리면 반영된다, D24).
- 예정 하나(slot)는 끝날 때까지 정해진 간격으로 다시 시도하고, 유효 시간이 지나면 그만둔다. 실행 기록은 DB의 job_run 에 남는다.
- 결과는 '오늘 현황'에 작업마다 한 줄로 적는다. 세션은 서버의 로그를 볼 수 없으므로, 고칠 때 필요한 내용
  (제목 불일치, 오지 않은 계열)은 메모 칸에 그대로 적는다. 키 값은 적지 않는다.
- 조종판을 열지 못해도 작업은 돈다. 한 작업이 실패해도 다른 작업과 게시 일꾼에는 영향을 주지 않는다.
- 화요일 23:20~23:50(한국 시간)에는 돌리지 않는다. 같은 서버에서 봇이 주문을 내는 시간이다.

지금 있는 작업
- collect_indicators (지표 수집): 매일 07:10 + 노동통계국 발표 2분 뒤. 발표 직후에는 발표값이 올 때까지 10분마다 다시 받는다.
- load_drafts (초안 싣기): 저장소에 새 SNS 초안(data/sns/drafts/*.md)이 올라오면 조종판 게시 대기열에 '초안'으로 싣는다. 승인은 사람만 한다.
"""
import argparse
import csv
import glob
import hashlib
import os
import sys
from collections import namedtuple
from datetime import datetime, timedelta, timezone

from ..collect import bls
from ..collect import catalog as C
from ..collect import env as envmod
from ..collect import store
from ..forecast import targets as T
from . import board as B
from . import drafts as D
from . import worker as W

KST = timezone(timedelta(hours=9))
UTC_FMT = "%Y-%m-%dT%H:%M:%SZ"
WEEKDAY = "월화수목금토일"
PLAN_DAYS = 8
QUIET = (1, (23, 20), (23, 50))   # (요일: 화=1, 시작, 끝) 한국 시간. 봇 집행 시각이 바뀌면 여기를 고친다
MEMO_MAX = 3000

# id: 예정의 이름(기록의 열쇠) / at: 이때부터 / until: 이때까지 유효 / gap: 다시 시도 간격(분) / tries: 최대 시도 / ctx: 작업이 쓰는 값
Slot = namedtuple("Slot", "id at until gap tries label ctx")
# id: DB job 표의 job_id / item: '오늘 현황'의 항목 이름 / slots(now, opts) -> [Slot] / run(now, due, opts) -> 결과
Job = namedtuple("Job", "id item slots run")


def setup_console():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except Exception:
            pass


def parse_utc(text):
    return datetime.strptime(text, UTC_FMT).replace(tzinfo=timezone.utc)


def kst_text(at):
    k = at.astimezone(KST)
    return "%s %d/%d %02d:%02d" % (WEEKDAY[k.weekday()], k.month, k.day, k.hour, k.minute)


def is_quiet(now):
    k = now.astimezone(KST)
    return k.weekday() == QUIET[0] and QUIET[1] <= (k.hour, k.minute) < QUIET[2]


# --- 지표 수집 (노동통계국)

def schedule_rows(pattern):
    rows = []
    for path in sorted(glob.glob(pattern)):
        with open(path, encoding="utf-8-sig", newline="") as f:
            rows.extend(csv.DictReader(f))
    return rows


def indicator_slots(now, opts):
    """매일 아침 한 번(밤사이 발표와 수정치) + 수집기가 있는 발표의 2분 뒤."""
    out = []
    today = now.astimezone(KST).date()
    for i in range(-1, PLAN_DAYS + 1):
        d = today + timedelta(days=i)
        at = datetime(d.year, d.month, d.day, 7, 10, tzinfo=KST).astimezone(timezone.utc)
        out.append(Slot("daily:%s" % d.isoformat(), at, at + timedelta(hours=24), 60, 24, "아침 수집", None))
    for r in schedule_rows(opts.get("schedule") or bls.DEFAULT_SCHEDULE):
        targets = [t for t in (r.get("targets") or "").split() if t in C.TARGET_SERIES]
        if not targets:
            continue   # 수집기가 아직 없는 발표(경제분석국·노동부)
        try:
            released = parse_utc(r["release_at_utc"])
        except (TypeError, ValueError, KeyError):
            continue   # 읽을 수 없는 줄 하나가 모든 예정을 멈추지 않게. 수집 결과의 [주의]에 그 줄이 적힌다
        if not (r.get("event_kind") and r.get("ref_period")):
            continue
        out.append(Slot("release:%s:%s" % (r["event_kind"], r["ref_period"]), released + timedelta(minutes=2), released + timedelta(hours=3), 10, 18,
                        "%s 발표 직후" % (r.get("title_ko") or r["event_kind"]), {"ref": r["ref_period"], "targets": targets}))
    out.sort(key=lambda s: (s.at, s.id))
    seen = set()
    return [s for s in out if not (s.id in seen or seen.add(s.id))]   # 같은 발표가 두 일정표에 있어도 예정은 하나


def actuals_have(path):
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {(r["target"], r["ref_period"]) for r in csv.DictReader(f)}


def indicator_summary(rep):
    """수집 요약 -> ('오늘 현황'의 결과 한 줄, 메모 줄 목록)."""
    memo = []
    if not rep["ok"]:
        if rep["error_kind"] == "no_key":
            return "실패: 서버 .env 에 BLS_API_KEY 가 없음", ["서버의 ~/checksum/.env 에 BLS_API_KEY= 줄을 넣으면 다음 시도부터 됩니다(PC .env 의 같은 줄)"]
        return "실패: " + rep["error"][:200], memo
    for r in rep["added"]:
        memo.append("처음 발표값 기록: %s %s = %s" % (T.TARGETS[r["target"]][1], r["ref_period"], r["actual"]))
    warn = 0
    if rep["mismatch"]:
        warn += len(rep["mismatch"])
        memo.append("[주의] 제목 불일치 %d개(사실 묶음에서 빠짐): %s" % (len(rep["mismatch"]), " | ".join(rep["mismatch"])))
    if rep["missing"]:
        warn += len(rep["missing"])
        memo.append("[주의] 값이 오지 않은 계열 %d개: %s" % (len(rep["missing"]), ", ".join(rep["missing"])))
    if rep["calc_diff"]:
        warn += 1
        memo.append("[주의] 계산값이 API 계산과 다른 곳 %d건: %s" % (len(rep["calc_diff"]), " | ".join(rep["calc_diff"][:3])))
    for n in rep["notes"]:
        warn += 1
        memo.append("[주의] " + n)
    if rep["unknown"]:
        memo.append("[알림] 제목을 대조하지 못한 계열 %d개" % rep["unknown"])
    newest = "%04d-%02d" % rep["newest"] if rep["newest"] else "없음"
    head = "정상" if not warn else "주의 %d건" % warn
    return "%s · 새 값 %d / 수정 %d / 그대로 %d · 최근 달 %s" % (head, rep["new"], rep["revised"], rep["same"], newest), memo


def run_indicators(now, due, opts):
    lines = []
    code, rep = (opts.get("collect") or bls.collect)(db=opts.get("db"), raw_dir=opts.get("raw_dir"), schedule=opts.get("schedule"), actuals=opts.get("actuals"),
                                                     from_file=opts.get("from_file"), now=now, say=lines.append)
    result, memo = indicator_summary(rep)
    done = set()
    if rep["ok"]:
        have = actuals_have(opts.get("actuals") or bls.DEFAULT_ACTUALS)
        for s in due:
            lack = [t for t in s.ctx["targets"] if (t, s.ctx["ref"]) not in have] if s.ctx else []
            if lack:
                memo.append("%s: 발표값이 아직 오지 않음(%s). %d분 뒤 다시 받음" % (s.label, ", ".join(T.TARGETS[t][1] for t in lack), s.gap))
            else:
                done.add(s.id)
    return {"ok": rep["ok"], "result": result, "memo": memo, "done": done, "lines": lines}


# --- 초안 싣기: 저장소의 SNS 초안 -> 조종판 게시 대기열 ('초안'으로만)

def draft_slots(now, opts):
    """싣지 않은 초안이 있을 때만 예정이 생긴다. 예정의 이름은 남은 초안 묶음에서 나오므로, 실패하면 30분 간격으로 네 번까지만 다시 한다."""
    con = store.connect(opts.get("db") or store.DEFAULT_DB)
    items, problems = D.pending(con, opts.get("drafts"))
    told = store.get_meta(con, "drafts_problems") or ""
    con.close()
    pdig = hashlib.sha256("\n".join(problems).encode("utf-8")).hexdigest()[:12] if problems else ""
    if not items and pdig == told:
        return []
    digest = hashlib.sha256("\n".join(sorted(it["key"] for it in items) + [pdig]).encode("utf-8")).hexdigest()[:12]
    return [Slot("drafts:" + digest, now - timedelta(seconds=1), now + timedelta(hours=1), 30, 4, "새 초안 싣기", None)]


def run_drafts(now, due, opts):
    con = store.connect(opts.get("db") or store.DEFAULT_DB)
    try:
        items, problems = D.pending(con, opts.get("drafts"))
        count, flagged = D.load(opts["board_opener"](), con, items, now.strftime(UTC_FMT))
        store.set_meta(con, "drafts_problems", hashlib.sha256("\n".join(problems).encode("utf-8")).hexdigest()[:12] if problems else "")
        con.commit()
    finally:
        con.close()
    memo = ["게시 대기열 끝에 '초안'으로 들어갔습니다. 고친 뒤 상태를 '승인'으로 바꾼 줄만 올라갑니다"] if count else []
    if flagged:
        memo.append("검사에 걸린 줄 %d개(채울 칸 포함): %s" % (len(flagged), " | ".join(flagged)[:1500]))
    memo.extend("[주의] 초안 파일 형식: " + p for p in problems[:5])
    head = "주의 %d건 · " % len(problems) if problems else ""
    return {"ok": True, "result": "%s초안 %d줄을 대기열에 실음" % (head, count), "memo": memo, "done": {s.id for s in due}, "lines": []}


JOBS = [Job("collect_indicators", "지표 수집", indicator_slots, run_indicators),
        Job("load_drafts", "초안 싣기", draft_slots, run_drafts)]


# --- 일꾼

def slot_state(con, job_id, slot_id, now):
    """그 예정의 (끝났는가, 시도 횟수, 마지막 시도 시각). 예정의 유효 시간은 하루 이내라 최근 3일 기록만 본다."""
    since = (now - timedelta(days=3)).strftime(UTC_FMT)
    done, tries, last = False, 0, None
    for status, started_at, detail in con.execute("SELECT status, started_at, detail FROM job_run WHERE job_id=? AND started_at>=? ORDER BY run_id", (job_id, since)):
        detail = detail or ""
        if not (detail == "slot=" + slot_id or detail.startswith("slot=%s " % slot_id)):
            continue
        tries += 1
        last = parse_utc(started_at)
        done = done or status == "ok"
    return done, tries, last


def due_slots(con, job, now, opts, ignore_gap=False):
    """지금 돌려야 하는 예정. ignore_gap 은 사람이 직접 돌릴 때: 간격과 횟수를 따지지 않고 아직 끝나지 않은 예정을 모두 넣는다."""
    out = []
    for s in job.slots(now, opts):
        if not (s.at <= now < s.until):
            continue
        done, tries, last = slot_state(con, job.id, s.id, now)
        if done:
            continue
        if not ignore_gap:
            if tries >= s.tries:
                continue
            if last is not None and now - last < timedelta(minutes=s.gap) - timedelta(seconds=150):   # cron 줄이 잠금을 100초까지 기다린다. 그만큼 늦게 도는 것은 봐준다
                continue
        out.append(s)
    return out


def next_text(job, now, opts, done_ids):
    """메모 끝에 붙이는 '다음 예정' 한 줄."""
    for s in job.slots(now, opts):
        if s.at > now and s.id not in done_ids:
            return "다음: %s %s" % (kst_text(s.at), s.label)
    return ""


def secrets_of(env):
    """.env 의 값 가운데 키·토큰으로 보이는 것(12자 이상). 결과 문구에 섞이면 가리기 위해서만 쓴다."""
    return sorted({v for k, v in (env or {}).items() if len(v) >= 12 and not k.endswith(("_FILE", "_DIR", "_ID"))}, key=len, reverse=True)


def scrub(text, secrets):
    for v in secrets:
        text = text.replace(v, "(가림)")
    return text


def note(board_opener, item, result, memo, now, log):
    """'오늘 현황'에 한 줄. 조종판을 열지 못해도 작업 결과에는 영향을 주지 않는다."""
    try:
        W.set_status(board_opener(), item, result[:300], memo[:MEMO_MAX], now)
    except (Exception, SystemExit) as e:
        log("[알림] 조종판에 적지 못함(%s): %s" % (item, str(e)[:200]))


def run_job(job, due, now, opts, db_path, board_opener, log):
    """작업을 한 번 돌리고, 기록하고, 조종판에 적는다. 돌려주는 값: 작업의 결과."""
    secrets = opts.get("secrets") or []
    started = now.strftime(UTC_FMT)   # 예정의 간격과 횟수는 이 시각으로 센다
    try:
        res = job.run(now, due, dict(opts, board_opener=board_opener))
    except (Exception, SystemExit) as e:   # 작업 하나가 멈춰도 일꾼은 계속 돈다
        res = {"ok": False, "result": "실패: 작업이 도중에 멈춤 (%s: %s)" % (type(e).__name__, str(e)[:160]), "memo": [], "done": set(), "lines": []}
    res["result"] = scrub(res["result"], secrets)   # 어떤 오류 문구에도 서버의 키가 남지 않게 한 번 더 가린다
    res["memo"] = [scrub(m, secrets) for m in res["memo"]]
    res["lines"] = [scrub(x, secrets) for x in res.get("lines") or []]
    memo = list(res["memo"])
    try:   # 기록이 실패해도 결과는 조종판에 남긴다
        con = store.connect(db_path)
        try:
            for s in due:
                status = "ok" if s.id in res["done"] else ("skipped" if res["ok"] else "fail")
                con.execute("INSERT INTO job_run(job_id,started_at,finished_at,status,detail) VALUES (?,?,?,?,?)",
                            (job.id, started, store.utc_now(), status, "slot=%s %s" % (s.id, res["result"][:200])))
            con.commit()
            for s in due:
                if s.id in res["done"] or s.id.startswith("manual:"):
                    continue
                _, tries, _ = slot_state(con, job.id, s.id, now + timedelta(seconds=1))
                if not res["ok"]:
                    memo.append("%s: %d분 뒤 다시 시도 (%d/%d)" % (s.label, s.gap, tries, s.tries) if tries < s.tries and now + timedelta(minutes=s.gap) < s.until
                                else "%s: 다시 시도하지 않음 (%d번 시도)" % (s.label, tries))
        finally:
            con.close()
        nxt = next_text(job, now, opts, res["done"])
        if nxt:
            memo.append(nxt)
    except Exception as e:
        memo.append("[주의] 실행 기록을 남기지 못함 (%s: %s). 다음 바퀴에 다시 돌 수 있음" % (type(e).__name__, str(e)[:120]))
    for line in res.get("lines") or []:
        log("   " + line)
    log("%s %s: %s%s" % (now.astimezone(KST).strftime("%Y-%m-%d %H:%M"), job.item, res["result"], " | " + " / ".join(memo) if memo else ""))
    note(board_opener, job.item, res["result"], " / ".join(memo), now, log)
    return res


def tick(now=None, env=None, db_path=None, jobs=None, opts=None, dry_run=False, board_opener=None, log=print):
    """한 바퀴. 돌린(돌릴) 작업의 [(job_id, [slot id], 결과 또는 None)]을 돌려준다."""
    now = now or datetime.now(timezone.utc)
    opts = dict(opts or {})
    db_path = db_path or opts.get("db") or store.DEFAULT_DB
    opts["db"] = db_path
    jobs = JOBS if jobs is None else jobs
    if env is None:
        env = envmod.load()
    opts.setdefault("secrets", secrets_of(env))
    if board_opener is None:
        board_opener = lambda: B.open_board(env)
    if is_quiet(now):
        if dry_run:
            log("지금은 돌리지 않는 시간입니다 (화 23:20~23:50).")
        return []
    out = []
    for job in jobs:   # 작업 하나가(예정을 읽는 단계 포함) 멈춰도 다른 작업은 돈다
        try:
            con = store.connect(db_path)
            try:
                due = due_slots(con, job, now, opts)
            finally:
                con.close()
            if not due:
                continue
            if dry_run:
                log("돌릴 것: %s — %s" % (job.item, ", ".join(s.label for s in due)))
                out.append((job.id, [s.id for s in due], None))
                continue
            out.append((job.id, [s.id for s in due], run_job(job, due, now, opts, db_path, board_opener, log)))
        except Exception as e:
            log("[주의] %s: 예정을 읽거나 기록하다 멈춤 (%s: %s)" % (job.item, type(e).__name__, str(e)[:160]))
            if not dry_run:
                note(board_opener, job.item, "실패: 예정을 읽지 못함 (%s: %s)" % (type(e).__name__, str(e)[:160]), "", now, log)
    return out


def main(argv=None):
    setup_console()
    ap = argparse.ArgumentParser(description="예약 작업 일꾼")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("tick")
    t.add_argument("--dry-run", action="store_true")
    sub.add_parser("plan")
    r = sub.add_parser("run")
    r.add_argument("job", choices=[j.id for j in JOBS])
    a = ap.parse_args(argv)
    now = datetime.now(timezone.utc)
    if a.cmd == "plan":
        for job in JOBS:
            print("%s (%s)" % (job.item, job.id))
            for s in job.slots(now, {}):
                if now <= s.at < now + timedelta(days=PLAN_DAYS):
                    print("   %s  %s" % (kst_text(s.at), s.label))
        return 0
    if a.cmd == "run":
        job = [j for j in JOBS if j.id == a.job][0]
        con = store.connect(store.DEFAULT_DB)
        due = due_slots(con, job, now, {}, ignore_gap=True)
        con.close()
        manual = Slot("manual:%s" % now.strftime(UTC_FMT), now, now, 0, 1, "직접 실행", None)
        if job.id == "load_drafts" and not due:
            print("지금 실을 초안이 없습니다.")
            return 0
        env = envmod.load()
        res = run_job(job, due + [manual], now, {"db": store.DEFAULT_DB, "secrets": secrets_of(env)}, store.DEFAULT_DB, lambda: B.open_board(env), print)
        return 0 if res["ok"] else 1
    ran = tick(now=now, dry_run=a.dry_run)
    if a.dry_run and not ran:
        print("지금 돌릴 작업이 없습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
