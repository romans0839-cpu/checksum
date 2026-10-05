"""콘텐츠 DB를 만들고 기본 행(출처, 작업 일정)을 넣는다. 여러 번 실행해도 안전하다.

실행 (프로젝트 루트에서):
    python -m pipeline.db.init                 data/db/checksum.db 생성
    python -m pipeline.db.init --db 경로        다른 위치에 생성
표준 라이브러리만 사용 (Python 3.9+).
"""
import argparse
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

# (source_id, name, kind, rights, attribution, url, note)
SOURCES = [
    ("fed", "미 연방준비제도", "primary", "public", "출처: 연방준비제도", "https://www.federalreserve.gov", "성명·점도표·금리"),
    ("treasury", "미 재무부", "primary", "public", "출처: 미 재무부", "https://home.treasury.gov", "일별 국채 금리"),
    ("bls", "미 노동통계국", "primary", "public", "출처: 미 노동통계국", "https://www.bls.gov", "물가·고용"),
    ("bea", "미 경제분석국", "primary", "public", "출처: 미 경제분석국", "https://www.bea.gov", "GDP·PCE"),
    ("sec", "미 증권거래위원회 EDGAR", "primary", "public", "출처: SEC EDGAR", "https://www.sec.gov/edgar", "실적 공시 원문"),
    ("fred", "FRED (세인트루이스 연은)", "aggregator", "cite_required", "출처: FRED, 세인트루이스 연방준비은행", "https://fred.stlouisfed.org",
     "공공·'인용 필요' 시리즈만. 제3자 저작권 시리즈는 쓰지 않는다. API로 저장해 재제공 금지"),
    ("bok", "한국은행", "primary", "unverified", "출처: 한국은행", "https://ecos.bok.or.kr", "달러/원. 이용 조건 확인 전"),
    ("ksd", "한국예탁결제원 세이브로", "primary", "unverified", "출처: 한국예탁결제원", "https://seibro.or.kr", "서학개미 보관·결제. 이용 조건 확인 전"),
    ("bot", "체크섬 시스템 신호", "internal", "public", "체크섬 자체 산출", None, "봇의 주간 신호. 장부 공개 규칙(T+7)에 따른다"),
    ("vendor_px", "가격 데이터 벤더(미정)", "vendor", "unverified", None, None, "표시 라이선스 확정 전 (docs/10). 확정되면 licensed_display로"),
    ("press", "언론 기사", "press", "link_only", None, None, "제목·링크·자체 요약만. 전문 저장·전재 금지"),
    ("dol", "미 노동부 고용훈련국", "primary", "public", "출처: 미 노동부", "https://www.dol.gov/ui/data.pdf", "주간 실업수당 청구"),
    ("eia", "미 에너지정보청", "primary", "public", "출처: 미 에너지정보청", "https://www.eia.gov", "주간 휘발유 소매가 (엔진 입력용)"),
    ("clevfed", "클리블랜드 연방준비은행", "primary", "unverified", "출처: 클리블랜드 연방준비은행", "https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting",
     "물가 나우캐스트. 상업적 게재 허가 확인 전 (docs/12 §9)"),
    ("atlfed", "애틀랜타 연방준비은행", "primary", "internal_only", None, "https://www.atlantafed.org/cqer/research/gdpnow",
     "GDPNow. 이용약관상 비상업적 복제만 허용 → 내부 비교용"),
    ("consensus", "시장 예상치(통신사·단말기 집계)", "vendor", "internal_only", None, None, "유료 자료. 게재 권리 없음 → 내부 비교용"),
    ("engine", "체크섬 엔진 예측", "internal", "internal_only", "체크섬 자체 산출", None, "공개 형태 결정 전까지 발행물에 쓰지 않는다 (D18). 결정되면 public으로"),
    ("gtrends", "Google 트렌드 지금 뜨는 검색어", "aggregator", "cite_required", "자료: Google 트렌드 (https://www.google.com/trends)", "https://trends.google.com/trending/rss",
     "후보를 찾는 데 쓴다. 순위·검색량을 발행물에 쓰면 출처 표기. 검색량은 어림값"),
    ("nyse", "뉴욕증권거래소", "primary", "public", "출처: NYSE", "https://www.nyse.com/markets/hours-calendars", "휴장·조기 폐장 일정"),
]

# (job_id, schedule_kst, description, blocks_publish)
JOBS = [
    ("collect_rates", "화~토 아침 (발표 시각 확인 후 확정)", "미 국채 금리·기준금리 수집", 1),
    ("collect_fx", "평일 아침·오후", "달러/원 수집 (출처 조건 확인 후 켠다)", 0),
    ("collect_calendar", "월 20:00", "다음 2주 일정 수집 (FOMC·물가·고용·어닝·휴장)", 1),
    ("collect_primary_docs", "매일 06:00·21:00", "1차 발표문 수집과 자체 요약", 0),
    ("pull_bot_signal", "화 09:40", "봇 주간 신호를 받아 장부에 봉인 (운영자 집행 23:31 전)", 1),
    ("detect_moves", "화~토 아침", "큰 움직임 판정 → 급락 체크 발동 여부", 0),
    ("build_morning", "평일 아침 (겨울철 미국장 마감 06:00 KST 반영)", "아침 체크 5줄: 사실 묶음 → 문장 → 검사", 0),
    ("build_weekly", "화 10:30", "주간 체크 본편 초안 → 검수 요청", 0),
    ("build_myth", "목 21:00", "통념 체크 초안 → 검수 요청", 0),
    ("score_judgments", "화 11:00", "13주 지난 판정 채점", 0),
    ("backup_db", "매일 03:00", "DB 파일 백업", 0),
    ("collect_indicators", "매일 07:10 + 발표 2분 뒤 (값이 올 때까지 10분마다)", "물가·고용·생산자물가 발표값과 과거 값 수집 (노동통계국. 서버의 예약 작업 일꾼이 돌린다)", 0),
    ("seal_forecasts", "화 09:40 (자동화 뒤에는 발표 전날)", "그 주 발표분 엔진 예측을 장부에 봉인 (발표 12시간 전 마감)", 0),
    ("score_forecasts", "발표 다음 날 아침", "봉인된 예측을 처음 발표값으로 채점", 0),
    ("collect_trends", "하루 3번 (아침·낮·저녁)", "뜨는 검색어 수집(한국·미국) → 트렌디 체크 후보 재료", 0),
    ("build_schedule_check", "매일 아침, 월 20:30", "일정 체크: 오늘 밤 발표와 이번 주 일정을 사실 문장으로", 0),
    ("console_worker", "5분마다", "조종판(시트)에서 승인된 글을 검사해 SNS에 올리고 결과를 다시 적는다", 0),
    ("refresh_threads_token", "매월 1일", "스레드 토큰 갱신(60일 만료)", 0),
    ("load_drafts", "새 초안이 저장소에 올라오면 (5분 안)", "저장소의 SNS 초안(data/sns/drafts/*.md)을 조종판 게시 대기열에 '초안'으로 싣는다. 승인은 사람만", 0),
]


def connect(path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init(path):
    con = connect(path)
    with open(os.path.join(HERE, "schema.sql"), encoding="utf-8") as f:
        con.executescript(f.read())
    con.executemany("INSERT OR IGNORE INTO source(source_id,name,kind,rights,attribution,url,note) VALUES (?,?,?,?,?,?,?)", SOURCES)
    con.executemany("INSERT INTO job(job_id,schedule_kst,description,blocks_publish) VALUES (?,?,?,?) "
                    "ON CONFLICT(job_id) DO UPDATE SET schedule_kst=excluded.schedule_kst, description=excluded.description", JOBS)   # 표기는 코드가 기준
    from pipeline.forecast import targets as T   # 예측 대상 목록은 코드가 기준 (pipeline/forecast/targets.py)
    con.executemany("INSERT OR IGNORE INTO forecast_target(target_id,event_kind,name_ko,unit,decimals,source_id,tier) VALUES (?,?,?,?,?,?,?)",
                    [(t, v[0], v[1], v[2], v[3], T.EVENTS[v[0]][1], v[4]) for t, v in T.TARGETS.items()])
    con.executemany("INSERT OR IGNORE INTO engine_version(engine,version,label_ko,mode,registered_at) VALUES (?,?,?,?,datetime('now'))",
                    [(name, "", label, "baseline") for name, label in T.BASELINES.items()])
    con.commit()
    return con


def main(argv=None):
    ap = argparse.ArgumentParser(description="콘텐츠 DB 생성")
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "db", "checksum.db"))
    a = ap.parse_args(argv)
    con = init(a.db)
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    print("DB: %s" % a.db)
    print("표 %d개: %s" % (len(tables), ", ".join(tables)))
    print("출처 %d개, 작업 %d개" % (con.execute("SELECT COUNT(*) FROM source").fetchone()[0],
                                con.execute("SELECT COUNT(*) FROM job").fetchone()[0]))
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
