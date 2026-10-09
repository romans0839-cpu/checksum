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
- log_edits (고친 기록): 한 시간에 한 번, 승인·게시된 줄에서 Nick이 고친 문장을 모아 '고친 기록' 탭에 적는다. 새로 고친 것이 없으면 아무것도 적지 않는다.
- pull_bot_signal (장부 봉인): 화요일 09:40부터 23:15까지, 그 주 봇 신호 파일이 봇 저장소 사본에 올라올 때까지 30분마다 보고
  올라오면 장부에 봉인한다(봇 집행 23:31 전). 다른 날에는 하루 한 번 장부가 그대로인지만 본다. 빈 장부에는 아무것도 쓰지 않는다.
  종목 이름은 조종판과 로그에 적지 않는다(건수와 해시만).
- check_channels (스레드 점검): 매일 06:00(아침 글 30분 전)과 20:30. 글을 올리지 않고 스레드 토큰과 게시 권한을 확인하고,
  게시 대기열에 '막힘'으로 남아 있는 줄을 함께 적는다. 게시 일꾼의 "막힘 N"은 그 바퀴에 새로 막힌 수라서, 남아 있는 막힌 줄은 여기서 본다.
- seal_forecasts (엔진 봉인): 엔진이 맡는 발표(CPI·PPI·고용)마다 발표 32시간 전(한국 시간 전날 13:30쯤)부터 20분마다 엔진 실행기를 불러
  두 엔진의 답을 모으고 장부에 봉인한다(docs/12 §7-1). 받은 답은 다시 받지 않고, 봉인 마감(발표 12시간 전) 뒤에는 부르지 않는다.
  묶음에 들어갈 다른 발표가 그 사이에 있으면(예: PPI 전날의 CPI) 그 발표값이 수집된 뒤에 시작한다.
  엔진이 낸 값은 조종판과 로그에 적지 않는다(엔진별 상태·횟수·토큰만).
"""
import argparse
import contextlib
import csv
import glob
import hashlib
import io
import os
import re
import subprocess
import sys
import time
from collections import namedtuple
from datetime import datetime, timedelta, timezone

from ..collect import bls
from ..collect import catalog as C
from ..collect import env as envmod
from ..collect import store
from ..forecast import runner as R
from ..forecast import targets as T
from ..ledger import commit as ledger_commit
from ..ledger import core as ledger_core
from ..ledger import verify as ledger_verify
from ..publish import threads as threads_api
from . import board as B
from . import drafts as D
from . import edits as E
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


# --- 고친 기록: 조종판에서 고친 문장 -> '고친 기록' 탭 (말투의 기준)

def edit_slots(now, opts):
    """한 시간에 한 번(매시 7분). 놓치면 그 시간 안에만 다시 한다."""
    hour = now.replace(minute=0, second=0, microsecond=0)
    out = []
    for i in (-1, 0, 1):
        at = hour + timedelta(hours=i, minutes=7)
        out.append(Slot("edits:" + at.strftime("%Y-%m-%dT%H"), at, at + timedelta(minutes=50), 20, 2, "고친 문장 모으기", None))
    return out


def run_edits(now, due, opts):
    con = store.connect(opts.get("db") or store.DEFAULT_DB)
    try:
        board = opts["board_opener"]()
        new = E.record(con, board.read(B.QUEUE), now)
        first = store.get_meta(con, "edits_tab") is None
        if new or first:   # 탭은 새 고침이 있을 때와 맨 처음에만 다시 쓴다
            board.replace(B.EDITS, E.latest(con))
            store.set_meta(con, "edits_tab", now.strftime(UTC_FMT))
            con.commit()
        count = E.total(con)
    finally:
        con.close()
    result = "새로 고친 문장 %d개 (모두 %d개)" % (new, count) if new else "'고친 기록' 탭을 만들었습니다 (고친 문장 %d개)" % count
    return {"ok": True, "result": result, "memo": ["승인·게시된 줄에서 고친 문장만 모읍니다. 최근 것부터 '고친 기록' 탭에 있습니다"], "done": {s.id for s in due}, "lines": [],
            "quiet": not (new or first)}


# --- 스레드 점검: 글을 올리지 않고 토큰·게시 권한을 확인하고, 대기열에 남은 막힌 줄을 적는다

CHECK_TIMES = ((6, 0, "아침 글 전 점검"), (20, 30, "밤 점검"))   # 한국 시간. 아침 글은 06:30, 밤 승인은 21시쯤


def channel_slots(now, opts):
    """하루 두 번. 놓치면 3시간 안에만 돌리고, 실패하면 30분 뒤 한 번 더 본다."""
    out = []
    today = now.astimezone(KST).date()
    for i in range(-1, PLAN_DAYS + 1):
        d = today + timedelta(days=i)
        for hh, mm, label in CHECK_TIMES:
            at = datetime(d.year, d.month, d.day, hh, mm, tzinfo=KST).astimezone(timezone.utc)
            out.append(Slot("check:%s:%02d%02d" % (d.isoformat(), hh, mm), at, at + timedelta(hours=3), 30, 2, label, None))
    return out


def blocked_rows(board):
    """게시 대기열에 '막힘'으로 남아 있는 줄을 한 줄씩: 번호, 초안 이름, 채널, 이유."""
    out = []
    for r in board.read(B.QUEUE):
        if (r.get("상태") or "").strip() == B.ST_BLOCKED:
            name = (r.get("메모") or "").split(" · ")[0].strip()[:30]
            out.append("%s번 %s(%s): %s" % (r.get("번호"), name or "이름 없음", (r.get("채널") or "").strip(), (r.get("검사") or "").strip()[:120]))
    return out


def run_channels(now, due, opts):
    env = opts.get("env")
    if env is None:
        env = envmod.load()
    memo, blocked = [], []
    try:
        blocked = blocked_rows(opts["board_opener"]())
    except (Exception, SystemExit) as e:
        memo.append("[알림] 게시 대기열을 읽지 못함: %s" % str(e)[:120])
    if blocked:
        memo.append("막힌 줄 %d개(고친 뒤 상태를 다시 '승인'으로 바꿔야 올라갑니다): %s" % (len(blocked), " | ".join(blocked)[:1500]))
    tail = " · 막힌 줄 %d" % len(blocked) if blocked else ""
    rest = (opts.get("threads_paused") or threads_api.paused)(now)
    if rest:   # 쉬는 동안에는 점검도 API를 부르지 않는다
        memo.insert(0, "때가 된 스레드 줄은 게시 일꾼이 '보류'로 바꿉니다. 스레드 앱에서 직접 올립니다. X 줄은 그대로 올라갑니다")
        return {"ok": True, "result": "쉬는 중 — %s까지 스레드 API를 부르지 않음%s" % (rest, tail), "memo": memo, "done": {s.id for s in due}, "lines": []}
    try:
        name, uid, used, total = (opts.get("threads_check") or threads_api.check)(env)
    except threads_api.PostError as e:
        memo.insert(0, "이 상태에서는 스레드 글이 올라가지 않고 그 줄이 '막힘'이 됩니다. X 줄은 따로 올라갑니다")
        return {"ok": False, "result": "실패: 스레드 %s%s" % (str(e)[:200], tail), "memo": memo, "done": set(), "lines": []}
    if env.get("THREADS_USER_ID") and env.get("THREADS_USER_ID") != uid:
        memo.insert(0, "[주의] .env 의 THREADS_USER_ID 가 토큰의 계정과 다릅니다. 서버에서 whoami 를 한 번 돌리면 맞춰집니다")
    quota = "최근 24시간 게시 %s/%s" % (used, total) if used is not None and total is not None else "게시 한도 값 없음"
    return {"ok": True, "result": "정상 · @%s · %s%s" % (name, quota, tail), "memo": memo, "done": {s.id for s in due}, "lines": []}


# --- 장부 봉인: 화요일에 그 주 봇 신호를 받아 봉인하고, 다른 날에는 장부가 그대로인지 본다 (docs/15 §5-5)

SEAL_FROM, SEAL_UNTIL = (9, 40), (23, 15)   # 한국 시간. 봇 신호는 화요일 아침에 올라오고, 봇은 23:31에 주문을 낸다
SEAL_LOOKBACK_DAYS = 4                      # 화요일에서 이만큼 안쪽의 기준 주만 "이번 주 신호"로 친다(지난주 파일을 다시 봉인하지 않게)


def ledger_slots(now, opts):
    out = []
    today = now.astimezone(KST).date()
    for i in range(-1, PLAN_DAYS + 1):
        d = today + timedelta(days=i)
        at = datetime(d.year, d.month, d.day, SEAL_FROM[0], SEAL_FROM[1], tzinfo=KST).astimezone(timezone.utc)
        if d.weekday() == 1:
            until = datetime(d.year, d.month, d.day, SEAL_UNTIL[0], SEAL_UNTIL[1], tzinfo=KST).astimezone(timezone.utc)
            out.append(Slot("seal:%s" % d.isoformat(), at, until, 30, 28, "이번 주 신호 봉인", {"day": d.isoformat()}))
        else:
            out.append(Slot("ledger:%s" % d.isoformat(), at, at + timedelta(hours=24), 120, 3, "장부 점검", None))
    return out


def ledger_paths(opts):
    """장부가 놓인 자리. signals.csv 는 서버에서 저장소 밖(data/private)에 둔다 — 추적 중인 파일을 서버가 고치면 코드 반영이 그것을 지울 수 있다."""
    root = ledger_commit.ROOT
    return {"ledger": opts.get("ledger_dir") or os.path.join(root, "data", "ledger", "public"),
            "private": opts.get("private_dir") or os.path.join(root, "data", "private", "ledger"),
            "signals": opts.get("signals_csv") or os.path.join(root, "data", "private", "track_record", "signals.csv")}


def bot_dir(opts, env):
    """봇 저장소 사본의 자리: 지정한 곳 > CHECKSUM_BOT_DIR > 코드 폴더 옆의 bot_readonly(서버) > us_swing_bot(PC)."""
    given = opts.get("bot_dir") or env.get("CHECKSUM_BOT_DIR") or os.environ.get("CHECKSUM_BOT_DIR")
    if given:
        return given
    beside = os.path.dirname(ledger_commit.ROOT)
    for name in ("bot_readonly", "us_swing_bot"):
        if os.path.isdir(os.path.join(beside, name)):
            return os.path.join(beside, name)
    return os.path.join(beside, "bot_readonly")


def bot_pull(path, timeout=90):
    """봇 저장소 사본을 새로 받는다(읽기 전용 키). (받았는가, 못 받은 이유)"""
    if not os.path.isdir(os.path.join(path, ".git")):
        return False, "git 저장소가 아님: %s" % path
    try:
        r = subprocess.run(["git", "-C", path, "pull", "--ff-only", "-q"], capture_output=True, text=True, timeout=timeout,
                           env=dict(os.environ, GIT_TERMINAL_PROMPT="0"))
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, type(e).__name__
    if r.returncode != 0:
        tail = [x for x in (r.stderr or r.stdout or "").strip().splitlines() if x.strip()]
        return False, (tail[-1] if tail else "git pull 실패")[:160]
    return True, ""


def quiet_call(fn, argv):
    """화면에 찍는 명령을 조용히 돌린다. 출력에는 종목 이름이 섞일 수 있어 통째로 밖에 내지 않는다. (종료 코드, 출력)"""
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            code = fn(argv)
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
        if not isinstance(e.code, int) and e.code:
            buf.write(str(e.code))
    return code or 0, buf.getvalue()


def as_date(text):
    """'2026-10-05', '20261005', 'target_20261006.json' 같은 글에서 날짜를 읽는다. 읽지 못하면 None."""
    m = re.search(r"(20\d\d)-?(\d\d)-?(\d\d)", str(text or ""))
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date()
    except ValueError:
        return None


def rebuild_signals_csv(entries, private_dir, csv_path):
    """signals.csv 가 없을 때 장부의 주간 기록 원문에서 다시 만든다(같은 순서로 되풀이하면 같은 파일이 나온다)."""
    n = 0
    for e in entries:
        if e.get("kind") != "weekly":
            continue
        priv = ledger_commit.read_private(private_dir, e)
        if priv:
            n += len(ledger_commit.append_signals_csv(csv_path, priv["payload"], e["seq"]))
    return n


def run_ledger(now, due, opts):
    env = opts.get("env")
    if env is None:
        env = envmod.load()
    paths, bot, memo = ledger_paths(opts), bot_dir(opts, env), []
    ledger_file = os.path.join(paths["ledger"], "ledger.jsonl")
    entries = ledger_core.read_ledger(ledger_file)
    if not entries:   # 빈 장부에 서버가 기점 기록을 만들지 않는다. 장부는 옮겨 온 것만 잇는다
        return {"ok": True, "result": "장부 없음 — 이 서버로 옮기기 전입니다(docs/15 §5-5). 아무것도 쓰지 않았습니다", "memo": [], "done": {s.id for s in due}, "lines": []}

    pulled, why = (opts.get("git_pull") or bot_pull)(bot)
    if not pulled:
        memo.append("[주의] 봇 저장소 사본을 새로 받지 못함(%s). 서버에 있는 사본으로 봅니다" % why)
    src, newest = ledger_commit.find_source(bot, None, False), None
    if src:
        try:
            newest = (os.path.basename(src), str(ledger_commit.load_json(src).get("asof_week") or ""))
        except (ValueError, OSError):
            memo.append("[주의] 가장 최근 신호 파일을 읽지 못함: %s" % os.path.basename(src))
    if not os.path.exists(paths["signals"]):
        made = rebuild_signals_csv(entries, paths["private"], paths["signals"])
        memo.append("signals.csv 를 장부 원문에서 다시 만듦(%d줄)" % made)

    def this_week(day, since):
        """이번 주 것으로 치는 주간 기록: 기준 주가 화요일에서 며칠 안쪽이거나, 그 화요일(한국 시간)에 봉인한 것."""
        out = []
        for e in entries:
            if e.get("kind") != "weekly":
                continue
            asof = as_date(e.get("week_asof"))
            try:
                sealed_on = parse_utc(e.get("committed_at")).astimezone(KST).date()
            except (TypeError, ValueError):
                sealed_on = None
            if (asof is not None and since <= asof <= day) or sealed_on == day:
                out.append(e)
        return out

    done, head = set(), ""
    seal_slots = [s for s in due if s.ctx]
    for s in seal_slots:
        day = as_date(s.ctx["day"])
        since = day - timedelta(days=SEAL_LOOKBACK_DAYS)
        got = this_week(day, since)
        fresh = False
        if newest:   # 지난주 파일을 이번 주 것으로 다시 봉인하지 않는다: 기준 주(없으면 파일 이름의 날짜)가 며칠 안쪽이어야 한다
            when = as_date(newest[1]) or as_date(newest[0])
            unsealed = not any(e.get("kind") == "weekly" and e.get("week_asof") == newest[1] for e in entries)
            fresh = unsealed and when is not None and since <= when <= day
        if not got and fresh:
            argv = ["--bot", bot, "--ledger-dir", paths["ledger"], "--private-dir", paths["private"], "--signals-csv", paths["signals"]]
            code, out = quiet_call(ledger_commit.main, argv + (["--no-ots"] if opts.get("no_ots") else []))
            entries = ledger_core.read_ledger(ledger_file)
            got = this_week(day, since)
            memo.extend(x.strip() for x in out.splitlines() if x.strip().startswith("봉인:"))
            if code != 0:
                memo.append("[주의] 봉인 명령이 멈춤(코드 %s): %s" % (code, " / ".join(x.strip() for x in out.splitlines() if x.strip().startswith(("[중단]", "- ")))[:300]))
        if got:
            e = got[-1]
            done.add(s.id)
            head = "봉인됨 · 기록 #%d (기준 주 %s: 청산 %s / 진입 후보 %s / 보유 %s)" % (e["seq"], e["week_asof"], e.get("n_exits", "?"), e.get("n_entry_candidates", "?"), e.get("n_holdings", "?"))
        else:
            head = "기다리는 중 — 이번 주 신호 파일이 아직 봇 저장소에 없음"
            memo.append("%s까지 %d분마다 다시 봅니다. 봇 집행(23:31) 전에 올라와야 봉인됩니다" % ("%02d:%02d" % SEAL_UNTIL, s.gap))

    code, out = quiet_call(ledger_verify.main, ["--ledger-dir", paths["ledger"], "--private-dir", paths["private"]])
    vlines = [x.strip() for x in out.splitlines() if x.strip()]
    counts = next((x for x in vlines if x.startswith("기록 ")), "기록 %d건" % len(entries))
    if newest:
        sealed = any(e.get("kind") == "weekly" and e.get("week_asof") == newest[1] for e in entries)
        memo.append("봇 신호 최신: %s (기준 주 %s, %s)" % (newest[0], newest[1], "봉인됨" if sealed else "아직 봉인 전"))
    else:
        memo.append("[주의] 봇 저장소 사본에서 라이브 신호 파일을 찾지 못함: %s" % os.path.join(bot, "signals"))
    if code != 0:
        memo = [x for x in vlines if x.startswith(("[문제", "- "))][:6] + memo
        return {"ok": False, "result": "실패: 장부 점검에서 문제가 나옴 · %s%s" % (counts, " · " + head if head else ""), "memo": memo, "done": set(), "lines": []}
    done |= {s.id for s in due if not s.ctx}
    tail = "장부 이상 없음 · %s · 마지막 해시 %s…" % (counts, entries[-1]["entry_hash"][:16])
    return {"ok": True, "result": "%s · %s" % (head, tail) if head else tail, "memo": memo, "done": done, "lines": []}


# --- 엔진 봉인: 발표 전날 낮부터 두 엔진을 불러 답을 모으고 장부에 봉인한다 (docs/12 §7-1). 값은 어디에도 적지 않는다

ENGINE_EVENTS = ("CPI", "PPI", "EMP")   # 엔진이 맡는 발표. 사실 묶음을 만들 수 있는 것(수집기가 있는 것)만 실제로 예정이 생긴다
ENGINE_LEAD_H = 32.0             # 발표 몇 시간 전부터 부르나: 한국 시간 전날 13:30(미국 여름 시간) · 14:30(겨울 시간). 전날 밤 글(21시) 전에 끝나고 낮 글(12시)과 겹치지 않는다
ENGINE_GAP_MIN = 20              # 끝날 때까지 이 간격으로 다시 부른다(받은 답은 다시 받지 않는다)
ENGINE_AFTER_RELATED_MIN = 30    # 묶음에 들어갈 다른 발표가 그 사이에 있으면 그 발표의 이만큼 뒤부터 시작한다
ENGINE_RELATED_BEFORE_H = 3.0    # 시작 시각보다 이만큼 앞선 발표까지 "그 사이"로 친다(수집이 늦을 수 있다)
ENGINE_WAIT_STOP_H = 4.0         # 봉인 마감이 이만큼 남으면 그 발표값을 더 기다리지 않고 있는 자료로 부른다
ENGINE_BUDGET_SEC = 400          # 한 바퀴에 엔진 호출에 쓰는 시간
ENGINE_RESERVE_SEC = 110         # 호출 뒤 봉인과 외부 타임스탬프(최대 75초쯤)에 남겨 두는 시간
ENGINE_MIN_BUDGET_SEC = 30       # 남은 시간이 이보다 짧으면 그 바퀴에는 실행기를 부르지 않는다(봉인·타임스탬프만 남은 때에도)
ENGINE_START_SEC = 5             # 한 번 부르는 시간(레시피의 timeout_sec)에 이만큼을 더한 시간이 남아 있어야 부른다
ENGINE_COUNT = 2                 # 엔진의 수(아들러·플레처). 이보다 적은 엔진으로 봉인되면 결과 줄에 알린다
ENGINE_PARALLEL = 5              # 엔진마다 한꺼번에 부르는 수
TICK_LIMIT_SEC = 600             # scripts/server_cron.sh 가 일꾼에 거는 timeout 600 과 같아야 한다
ENGINE_STATE = {"sealed": "봉인됨", "ready": "봉인 전", "pending": "진행 중", "blocked": "쓸 수 없음", "missed": "미제출"}
ENGINE_HEAD = {"sealed": "봉인됨", "already": "봉인됨", "pending": "진행 중", "missed": "미제출", "blocked": "멈춤"}


def engine_slots(now, opts):
    """엔진이 맡는 발표마다 예정 하나: 발표 32시간 전부터 발표 때까지 20분마다. 봉인과 외부 타임스탬프가 끝나면 그만둔다.

    봉인 마감(발표 12시간 전) 뒤의 바퀴에서는 실행기가 엔진을 부르지도 봉인하지도 않는다 — 빠진 타임스탬프만 다시 받는다.
    """
    rows = []
    for r in schedule_rows(opts.get("schedule") or bls.DEFAULT_SCHEDULE):
        try:
            rows.append((r["event_kind"], r["ref_period"], parse_utc(r["release_at_utc"]), r))
        except (TypeError, ValueError, KeyError):
            continue   # 읽을 수 없는 줄은 건너뛴다. 지표 수집의 [주의]에 그 줄이 적힌다
    out, seen = [], set()
    for kind, ref, released, r in rows:
        if kind not in ENGINE_EVENTS or kind not in C.RELATED or kind not in T.EVENTS or not T.ref_period_ok(kind, ref) or (kind, ref) in seen:
            continue
        seen.add((kind, ref))   # 같은 발표가 두 일정표에 있어도 예정은 하나(실행기도 먼저 나온 줄의 시각을 쓴다)
        deadline = released - timedelta(hours=R.MIN_LEAD_H)
        at, wait = released - timedelta(hours=ENGINE_LEAD_H), []
        first = at - timedelta(hours=ENGINE_RELATED_BEFORE_H)
        for k2, ref2, rel2, r2 in rows:   # 이 발표의 묶음에 들어가는 다른 발표가 시작 무렵부터 마감 몇 시간 전 사이에 나오면 그 뒤로 미룬다
            targets = [t for t in (r2.get("targets") or "").split() if t in C.TARGET_SERIES]
            if k2 in C.RELATED[kind] and targets and first <= rel2 <= deadline - timedelta(hours=ENGINE_WAIT_STOP_H):
                at = max(at, rel2 + timedelta(minutes=ENGINE_AFTER_RELATED_MIN))
                wait.append({"title": r2.get("title_ko") or k2, "ref": ref2, "targets": targets})
        title = r.get("title_ko") or T.EVENTS[kind][0]
        tries = int((released - at).total_seconds() // (ENGINE_GAP_MIN * 60)) + 6
        out.append(Slot("engine:%s:%s" % (kind, ref), at, released, ENGINE_GAP_MIN, tries, "%s %s 엔진 봉인" % (title, ref),
                        {"kind": kind, "ref": ref, "title": title, "release": released, "wait": wait}))
    out.sort(key=lambda s: (s.at, s.id))
    return out


def seconds_to_quiet(at):
    """오늘 '돌리지 않는 시간'이 시작될 때까지 남은 초(그 시간 안이면 0 이하). 오늘이 그 요일이 아니거나 그 시간이 끝났으면 None."""
    k = at.astimezone(KST)
    start = k.replace(hour=QUIET[1][0], minute=QUIET[1][1], second=0, microsecond=0)
    end = k.replace(hour=QUIET[2][0], minute=QUIET[2][1], second=0, microsecond=0)
    return (start - k).total_seconds() if k.weekday() == QUIET[0] and k < end else None


def engine_line(name, res):
    """실행기의 결과 -> '오늘 현황'의 한 줄. 엔진별 상태만 적는다(값은 실행기의 결과에도 없다)."""
    state, eng = res.get("state"), res.get("engines") or {}
    head = ENGINE_HEAD.get(state, "멈춤")
    if not eng:   # 엔진을 살피기 전에 끝난 경우(마감 뒤, 등록된 엔진 없음, 장부 문제). 실행기의 한 줄을 그대로 쓴다
        return "%s · %s — %s" % (head, name, str(res.get("result") or "")[:200])
    sealed = sorted(t for t, v in eng.items() if v == "sealed")
    others = ["%s(%s)" % (t, ENGINE_STATE.get(v, v)) for t, v in sorted(eng.items()) if v != "sealed"]
    if state in ("sealed", "already") and others:
        head = "일부만 봉인됨"
    elif state == "pending" and not res.get("ok"):
        head = "진행 중(오류 있음)"
    line = "%s · %s · 봉인된 엔진 %d/%d%s" % (head, name, len(sealed), len(eng), ": " + ", ".join(sealed) if sealed else "")
    line += " · 나머지: " + ", ".join(others) if others else ""
    return line + (" · [주의] 이 발표에 쓰인 엔진이 %d개뿐" % len(eng) if len(eng) < ENGINE_COUNT else "")


def run_engines(now, due, opts):
    """때가 된 발표마다 엔진 실행기를 한 번 부른다. 한 바퀴(일꾼의 제한 600초) 안에 끝나도록 쓸 시간을 정해서 넘긴다.

    두 발표가 겹치면 바퀴마다 먼저 할 발표를 바꿔 가며 하고, 남은 시간이 모자란 발표는 다음 차례(20분 뒤)로 미룬다.
    """
    clock = opts.get("clock") or time.monotonic
    t0 = opts.get("tick_started")
    t0 = clock() if t0 is None else t0
    run_event = opts.get("run_event") or R.run_event
    dirs = {k: opts[k] for k in ("ledger_dir", "private_dir", "engines_dir", "runs_dir", "schedule", "db") if opts.get(k)}
    heads, memo, done, ok, have, need = [], [], {s.id for s in due if not s.ctx}, True, None, None
    events = sorted((x for x in due if x.ctx), key=lambda x: (x.until, x.id))
    if len(events) > 1:   # 겹친 발표는 같은 간격으로 함께 돌아온다. 늘 같은 발표가 먼저 시간을 다 쓰지 않게 차례를 돌린다
        k = int(now.timestamp() // (ENGINE_GAP_MIN * 60)) % len(events)
        events = events[k:] + events[:k]
    for s in events:
        c = s.ctx
        name = "%s %s" % (c["title"], c["ref"])
        elapsed = clock() - t0
        at = now + timedelta(seconds=elapsed)
        lead_h = (c["release"] - at).total_seconds() / 3600.0

        # 묶음에 들어갈 다른 발표값이 아직 수집되지 않았으면 기다린다. 첫 답을 받는 순간 묶음이 굳어 뒤에 온 값은 쓰이지 않는다
        if c["wait"] and lead_h >= R.MIN_LEAD_H:
            if have is None:
                try:
                    have = actuals_have(opts.get("actuals") or bls.DEFAULT_ACTUALS)
                except Exception:
                    have = set()
            lack = ["%s %s" % (w["title"], w["ref"]) for w in c["wait"] if any((t, w["ref"]) not in have for t in w["targets"])]
            if lack and lead_h > R.MIN_LEAD_H + ENGINE_WAIT_STOP_H:
                heads.append("기다리는 중 · %s — %s 발표값이 아직 수집되지 않음" % (name, ", ".join(lack)))
                memo.append("%s: 봉인 마감 %g시간 전까지 기다리고, 그때도 없으면 있는 자료로 부릅니다. '지표 수집' 줄을 함께 보세요" % (name, ENGINE_WAIT_STOP_H))
                continue
            if lack:
                memo.append("[알림] %s: %s 발표값 없이 부릅니다(더 기다리지 않음)" % (name, ", ".join(lack)))

        budget = min(ENGINE_BUDGET_SEC, TICK_LIMIT_SEC - ENGINE_RESERVE_SEC - elapsed)
        q = seconds_to_quiet(at)
        if q is not None:   # 봇 집행 시간 전에 봉인까지 끝나게 한다
            budget = min(budget, q - ENGINE_RESERVE_SEC)
        if budget < ENGINE_MIN_BUDGET_SEC:
            heads.append("미룸 · %s — 이번 바퀴에 남은 시간이 모자람" % name)
            continue
        if lead_h >= R.MIN_LEAD_H + R.FINAL_MARGIN_H:   # 아직 엔진을 부르는 때다(마지막 한 시간에는 부르지 않고 받은 답으로 마무리만 한다)
            if need is None:
                need = (opts.get("call_seconds") or R.longest_call)(opts.get("engines_dir") or R.default_paths({})["engines"])
            if need and need + ENGINE_START_SEC > ENGINE_BUDGET_SEC:   # 이대로는 몇 번을 돌아도 부르지 못한다. 사람이 봐야 한다
                heads.append("멈춤 · %s — 레시피의 한 번 부르는 시간(%d초)이 한 바퀴에 쓸 수 있는 시간(%d초)보다 깁니다" % (name, need, ENGINE_BUDGET_SEC))
                memo.append("%s: 엔진을 부르지 못했습니다. 이 줄을 그대로 Claude에게 알려 주세요" % name)
                ok = False
                continue
            if need and budget < need + ENGINE_START_SEC:
                heads.append("미룸 · %s — 이번 바퀴에 남은 시간(%d초)이 한 번 부르는 시간(%d초)보다 짧음" % (name, budget, need))
                continue

        res = run_event(c["kind"], c["ref"], dict(dirs, budget_sec=budget, parallel=ENGINE_PARALLEL, no_ots=bool(opts.get("no_ots"))), env=opts.get("env"))
        state, head = res.get("state"), engine_line(name, res)
        if state in ("sealed", "already") and res.get("stamped") is False:   # 봉인은 됐다. 외부 타임스탬프만 다음 바퀴에 다시 받는다
            head += " · 외부 타임스탬프는 아직"
        elif state in ("sealed", "already", "missed"):
            done.add(s.id)
        ok = ok and bool(res.get("ok"))
        heads.append(head)
        memo.append("%s: %s" % (name, str(res.get("result") or "")[:300]))
        memo.extend(str(m)[:400] for m in (res.get("memo") or [])[:12])
        if res.get("calls"):
            memo.append("이번 바퀴에 부른 횟수 %d (쓸 시간 %d초)" % (res["calls"], budget))
        if state == "missed":
            memo.append("놓친 발표는 뒤늦게 채우지 않습니다(docs/12 §6)")
        elif s.id not in done and res.get("ok"):   # 실패한 바퀴의 "다시 시도" 줄은 일꾼이 붙인다
            memo.append("%s: %d분 뒤 이어서 합니다" % (name, s.gap))
    if not heads:
        return {"ok": True, "result": "지금 봉인할 발표가 없습니다", "memo": [], "done": done, "lines": []}
    return {"ok": ok, "result": " | ".join(heads), "memo": memo, "done": done, "lines": []}


# 엔진 봉인은 맨 뒤에 둔다: 한 바퀴의 남은 시간을 재서 쓰므로 다른 작업이 먼저 끝나 있어야 한다
JOBS = [Job("collect_indicators", "지표 수집", indicator_slots, run_indicators),
        Job("load_drafts", "초안 싣기", draft_slots, run_drafts),
        Job("log_edits", "고친 기록", edit_slots, run_edits),
        Job("check_channels", "스레드 점검", channel_slots, run_channels),
        Job("pull_bot_signal", "장부 봉인", ledger_slots, run_ledger),
        Job("seal_forecasts", "엔진 봉인", engine_slots, run_engines)]


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
    if res.get("quiet"):   # 할 일이 없었던 바퀴: 기록만 남기고 로그와 조종판은 건드리지 않는다
        return res
    for line in res.get("lines") or []:
        log("   " + line)
    log("%s %s: %s%s" % (now.astimezone(KST).strftime("%Y-%m-%d %H:%M"), job.item, res["result"], " | " + " / ".join(memo) if memo else ""))
    note(board_opener, job.item, res["result"], " / ".join(memo), now, log)
    return res


def tick(now=None, env=None, db_path=None, jobs=None, opts=None, dry_run=False, board_opener=None, log=print):
    """한 바퀴. 돌린(돌릴) 작업의 [(job_id, [slot id], 결과 또는 None)]을 돌려준다."""
    now = now or datetime.now(timezone.utc)
    opts = dict(opts or {})
    opts.setdefault("tick_started", (opts.get("clock") or time.monotonic)())   # 엔진 봉인이 이 바퀴의 남은 시간을 잰다
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
            if job.id == "log_edits":
                print("   매시 7분  고친 문장 모으기")
                continue
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
        if job.id == "seal_forecasts" and not due:   # '오늘 현황'의 앞선 결과를 빈 줄로 덮지 않는다
            print("지금 봉인할 발표가 없습니다. 예정은: python -m pipeline.console.jobs plan")
            return 0
        env = envmod.load()
        res = run_job(job, due + [manual], now, {"db": store.DEFAULT_DB, "secrets": secrets_of(env), "tick_started": time.monotonic()}, store.DEFAULT_DB, lambda: B.open_board(env), print)
        return 0 if res["ok"] else 1
    ran = tick(now=now, dry_run=a.dry_run)
    if a.dry_run and not ran:
        print("지금 돌릴 작업이 없습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
