-- 체크섬 콘텐츠 DB (SQLite) v0.4 — 설계 근거: docs/11_content_system_design.md, 엔진 예측은 docs/12_forecast_engines.md
-- 원칙: (1) 덮어쓰지 않는다. 값이 바뀌면 새 행을 쌓는다  (2) 모든 값에 "언제 알게 됐는가"(known_at, UTC)를 남긴다
--       (3) 출처마다 발행 권리를 적고, 발행물은 권리가 있는 사실만 쓴다  (4) LLM은 fact 표만 본다
--       (5) 계좌 금액·수량·수익률, 벤더 가격 원자료는 이 DB에 넣지 않는다
PRAGMA foreign_keys = ON;

-- 0. 출처와 발행 권리 -------------------------------------------------------
CREATE TABLE IF NOT EXISTS source (
  source_id   TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  kind        TEXT NOT NULL CHECK (kind IN ('primary','aggregator','vendor','press','internal')),
  rights      TEXT NOT NULL CHECK (rights IN ('public','cite_required','licensed_display','link_only','internal_only','unverified')),
  attribution TEXT,              -- 발행물에 붙일 출처 표기
  url         TEXT,
  note        TEXT
);

-- 1. 수집 기록 (원자료 파일은 data/raw/ 에, 여기에는 위치와 해시) -----------------
CREATE TABLE IF NOT EXISTS raw_fetch (
  fetch_id    INTEGER PRIMARY KEY,
  source_id   TEXT NOT NULL REFERENCES source(source_id),
  url         TEXT,
  fetched_at  TEXT NOT NULL,     -- UTC ISO-8601
  http_status INTEGER,
  sha256      TEXT NOT NULL,
  path        TEXT,
  run_id      INTEGER
);

-- 2. 시계열 ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS series (
  series_id        TEXT PRIMARY KEY,   -- 예: UST_10Y, FED_FUNDS_UPPER, USDKRW
  name_ko          TEXT NOT NULL,
  unit             TEXT,
  freq             TEXT NOT NULL CHECK (freq IN ('D','W','M','Q','E')),
  source_id        TEXT NOT NULL REFERENCES source(source_id),
  stale_after_days INTEGER NOT NULL DEFAULT 5,   -- 이보다 묵으면 사실로 쓰지 않는다
  note             TEXT
);
CREATE TABLE IF NOT EXISTS observation (
  obs_id      INTEGER PRIMARY KEY,
  series_id   TEXT NOT NULL REFERENCES series(series_id),
  obs_date    TEXT NOT NULL,     -- 값이 가리키는 날짜(기간의 끝)
  value       REAL NOT NULL,
  known_at    TEXT NOT NULL,     -- 우리가 이 값을 알게 된 시각(UTC). 수정치는 새 행으로 쌓인다
  released_at TEXT,              -- 공식 발표 시각(알 때만)
  fetch_id    INTEGER REFERENCES raw_fetch(fetch_id),
  UNIQUE (series_id, obs_date, known_at)   -- 수집기는 최신값과 다를 때만 새 행을 넣는다(2.9 -> 3.0 -> 2.9 같은 재수정도 보존)
);
CREATE INDEX IF NOT EXISTS ix_observation ON observation(series_id, obs_date, known_at);
-- 최신값 보기 (같은 날짜에 여러 행이면 가장 나중에 알게 된 값)
CREATE VIEW IF NOT EXISTS v_observation_latest AS
SELECT o.* FROM observation o
WHERE o.known_at = (SELECT MAX(known_at) FROM observation x WHERE x.series_id = o.series_id AND x.obs_date = o.obs_date);

-- 3. 일정 ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS event (
  event_id     INTEGER PRIMARY KEY,
  kind         TEXT NOT NULL,    -- FOMC, CPI, NFP, GDP, EARNINGS, HOLIDAY, BOJ, ECB ...
  title_ko     TEXT NOT NULL,
  region       TEXT,
  symbol       TEXT NOT NULL DEFAULT '',
  scheduled_at TEXT NOT NULL,    -- UTC
  importance   INTEGER NOT NULL DEFAULT 1 CHECK (importance BETWEEN 1 AND 3),  -- 규칙으로 부여
  status       TEXT NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled','released','moved','cancelled')),
  source_id    TEXT REFERENCES source(source_id),
  known_at     TEXT NOT NULL,
  UNIQUE (kind, scheduled_at, symbol)
);
CREATE TABLE IF NOT EXISTS event_value (
  event_id  INTEGER NOT NULL REFERENCES event(event_id),
  field     TEXT NOT NULL CHECK (field IN ('actual','previous','revised','consensus')),  -- consensus는 권리 확인 뒤에만
  value     REAL,
  text      TEXT,
  known_at  TEXT NOT NULL,
  source_id TEXT REFERENCES source(source_id),
  PRIMARY KEY (event_id, field, known_at)
);

-- 4. 문서: 1차 발표문과 기사 메타 (기사 전문은 저장하지 않는다) -----------------------
CREATE TABLE IF NOT EXISTS document (
  doc_id       INTEGER PRIMARY KEY,
  source_id    TEXT NOT NULL REFERENCES source(source_id),
  kind         TEXT NOT NULL CHECK (kind IN ('primary','press')),
  url          TEXT NOT NULL UNIQUE,
  title        TEXT NOT NULL,
  lang         TEXT,
  published_at TEXT,
  fetched_at   TEXT NOT NULL,
  summary_own  TEXT,             -- 자체 요약
  humanitarian INTEGER NOT NULL DEFAULT 0 CHECK (humanitarian IN (0,1)),  -- 인명 피해·재난·분쟁. 감정 규칙에서 쓴다
  fetch_id     INTEGER REFERENCES raw_fetch(fetch_id)
);
CREATE TABLE IF NOT EXISTS doc_link (
  doc_id   INTEGER NOT NULL REFERENCES document(doc_id),
  ref_type TEXT NOT NULL CHECK (ref_type IN ('event','series','symbol','tag')),
  ref_id   TEXT NOT NULL,
  PRIMARY KEY (doc_id, ref_type, ref_id)
);

-- 5. 큰 움직임 (뉴스의 중요도는 헤드라인이 아니라 숫자가 정한다) ---------------------
CREATE TABLE IF NOT EXISTS market_move (
  move_id      INTEGER PRIMARY KEY,
  subject      TEXT NOT NULL,    -- series_id 또는 종목
  move_date    TEXT NOT NULL,
  change       REAL NOT NULL,
  pctile       REAL NOT NULL,    -- 과거 분포에서의 백분위(0~1)
  window_n     INTEGER NOT NULL, -- 비교한 과거 표본 수
  rule_version TEXT NOT NULL,
  UNIQUE (subject, move_date, rule_version)
);

-- 6. 사실: LLM이 볼 수 있는 유일한 재료 ----------------------------------------
CREATE TABLE IF NOT EXISTS fact (
  fact_id     INTEGER PRIMARY KEY,
  kind        TEXT NOT NULL CHECK (kind IN ('level','change','percentile','event','base_rate','state','doc','schedule')),
  subject     TEXT NOT NULL,
  as_of       TEXT NOT NULL,
  value       REAL,
  unit        TEXT,
  n           INTEGER,           -- 기저율이면 표본 수
  text_ko     TEXT NOT NULL,     -- 코드가 만든 한 줄 문장(숫자 포함)
  refs        TEXT NOT NULL,     -- JSON: [{"t":"obs","id":1},{"t":"doc","id":7}]
  publishable INTEGER NOT NULL CHECK (publishable IN (0,1)),  -- 출처 권리에서 계산
  computed_by TEXT NOT NULL,     -- 코드·규칙 버전
  created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_fact ON fact(as_of, kind, subject);

-- 7. 판정과 채점 (장부와 연결) ------------------------------------------------
CREATE TABLE IF NOT EXISTS judgment (
  judgment_id  INTEGER PRIMARY KEY,
  rule_id      TEXT NOT NULL,
  rule_version TEXT NOT NULL,
  subject      TEXT NOT NULL,
  state        TEXT NOT NULL,
  as_of        TEXT NOT NULL,
  ledger_seq   INTEGER,          -- 봉인된 장부 기록 번호
  fact_id      INTEGER REFERENCES fact(fact_id),
  UNIQUE (rule_id, rule_version, subject, as_of)
);
CREATE TABLE IF NOT EXISTS score (
  judgment_id   INTEGER NOT NULL REFERENCES judgment(judgment_id),
  horizon_weeks INTEGER NOT NULL,
  outcome       TEXT NOT NULL,   -- 판정한 상태가 실제로 일어났는가
  measured      REAL,
  scored_at     TEXT NOT NULL,
  PRIMARY KEY (judgment_id, horizon_weeks)
);

-- 8. 발행물 ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS issue (
  issue_id       INTEGER PRIMARY KEY,
  product        TEXT NOT NULL CHECK (product IN ('morning','weekly','myth','crash','monthly','special')),
  slot_date      TEXT NOT NULL,
  tier           TEXT NOT NULL DEFAULT 'free' CHECK (tier IN ('free','basic','pro')),
  status         TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','checked','approved','sent','held')),
  fact_pack      TEXT,           -- JSON: 이번 호에 허용된 fact_id 목록
  model          TEXT,
  prompt_version TEXT,
  voice_version  TEXT,
  draft_text     TEXT,
  final_text     TEXT,
  approved_by    TEXT,
  sent_at        TEXT,
  UNIQUE (product, slot_date, tier)
);
CREATE TABLE IF NOT EXISTS issue_sentence (
  issue_id INTEGER NOT NULL REFERENCES issue(issue_id),
  idx      INTEGER NOT NULL,
  grade    TEXT NOT NULL CHECK (grade IN ('fact','judgment','context','emotion','note')),
  text     TEXT NOT NULL,
  fact_ids TEXT,                 -- JSON 배열. fact·judgment 등급은 비어 있으면 발행 차단
  PRIMARY KEY (issue_id, idx)
);
CREATE TABLE IF NOT EXISTS correction (
  correction_id INTEGER PRIMARY KEY,
  issue_id      INTEGER NOT NULL REFERENCES issue(issue_id),
  idx           INTEGER,
  wrong         TEXT NOT NULL,
  right         TEXT NOT NULL,
  cause         TEXT,
  found_at      TEXT NOT NULL,
  published_in  INTEGER REFERENCES issue(issue_id)
);

-- 9. 말투와 감정 ------------------------------------------------------------
-- 말투 표본(메일 등)은 DB가 아니라 data/private/voice/ 파일로만 둔다.
CREATE TABLE IF NOT EXISTS edit_log (      -- 검수에서 고친 문장. 다음 초안의 말투 기준이 된다
  edit_id   INTEGER PRIMARY KEY,
  issue_id  INTEGER NOT NULL REFERENCES issue(issue_id),
  idx       INTEGER,
  before    TEXT NOT NULL,
  after     TEXT NOT NULL,
  edited_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS phrase_log (    -- 이미 쓴 인사·감정 표현. 최근 8주 안의 반복을 막는다
  phrase_id INTEGER PRIMARY KEY,
  issue_id  INTEGER REFERENCES issue(issue_id),
  role      TEXT NOT NULL CHECK (role IN ('opening','closing','emotion','transition')),
  emotion   TEXT CHECK (emotion IN ('concern','support','curiosity','relief','apology','solidarity')),
  text      TEXT NOT NULL,
  used_at   TEXT NOT NULL
);

-- 10. 작업 일정과 실행 기록 ----------------------------------------------------
CREATE TABLE IF NOT EXISTS job (
  job_id         TEXT PRIMARY KEY,
  schedule_kst   TEXT NOT NULL,  -- 사람이 읽는 표기. 실제 예약은 cron
  description    TEXT NOT NULL,
  enabled        INTEGER NOT NULL DEFAULT 0 CHECK (enabled IN (0,1)),
  blocks_publish INTEGER NOT NULL DEFAULT 0 CHECK (blocks_publish IN (0,1))  -- 실패하면 그날 발행을 막는가
);
CREATE TABLE IF NOT EXISTS job_run (
  run_id      INTEGER PRIMARY KEY,
  job_id      TEXT NOT NULL REFERENCES job(job_id),
  started_at  TEXT NOT NULL,
  finished_at TEXT,
  status      TEXT CHECK (status IN ('ok','fail','skipped')),
  detail      TEXT
);

-- 11. 엔진 예측 (D18, docs/12) ------------------------------------------------
-- 예측 원문의 기준은 장부(data/private/ledger)다. 아래 표는 조회·채점·발행용 사본이며 장부에서 다시 만들 수 있다.
CREATE TABLE IF NOT EXISTS engine_version (
  engine        TEXT NOT NULL,      -- 엔진 이름. 모델 회사·모델 이름을 넣지 않는다
  version       TEXT NOT NULL,
  label_ko      TEXT,
  mode          TEXT NOT NULL CHECK (mode IN ('api','manual','baseline')),
  model         TEXT,               -- 기반 모델 ID
  n_runs        INTEGER,
  recipe_sha256 TEXT,               -- 레시피 폴더 해시. 레시피 내용은 DB에 넣지 않는다
  registered_at TEXT NOT NULL,
  ledger_seq    INTEGER,
  status        TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('shadow','active','retired')),
  PRIMARY KEY (engine, version)
);
CREATE TABLE IF NOT EXISTS forecast_target (
  target_id  TEXT PRIMARY KEY,      -- pipeline/forecast/targets.py 와 같은 목록
  event_kind TEXT NOT NULL,
  name_ko    TEXT NOT NULL,
  unit       TEXT NOT NULL,
  decimals   INTEGER NOT NULL,      -- 발표 자릿수
  source_id  TEXT NOT NULL REFERENCES source(source_id),
  tier       INTEGER NOT NULL,
  active     INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1))
);
CREATE TABLE IF NOT EXISTS forecast (
  forecast_id   INTEGER PRIMARY KEY,
  target_id     TEXT NOT NULL REFERENCES forecast_target(target_id),
  ref_period    TEXT NOT NULL,      -- 2026-09 / 2026Q3 / 2026-10-10
  release_at    TEXT NOT NULL,      -- 발표 시각(UTC)
  engine        TEXT NOT NULL,
  version       TEXT NOT NULL DEFAULT '',
  p10           REAL,
  p50           REAL NOT NULL,
  p90           REAL,
  n_runs        INTEGER,
  bundle_sha256 TEXT,               -- 엔진들에게 준 사실 묶음의 해시
  data_cutoff   TEXT,               -- 자료 마감 시각(UTC)
  sealed_at     TEXT NOT NULL,      -- 장부 봉인 시각(UTC). 발표 시각보다 앞서야 채점한다
  ledger_seq    INTEGER NOT NULL,
  UNIQUE (target_id, ref_period, engine, version)
);
CREATE TABLE IF NOT EXISTS forecast_score (
  forecast_id     INTEGER PRIMARY KEY REFERENCES forecast(forecast_id),
  actual          REAL NOT NULL,    -- 처음 발표된 값(수정치로 다시 채점하지 않는다)
  actual_known_at TEXT NOT NULL,
  abs_error       REAL NOT NULL,
  in_interval     INTEGER CHECK (in_interval IN (0,1)),
  interval_score  REAL,
  scored_at       TEXT NOT NULL
);

-- 12. 뜨는 검색어 (트렌디 체크의 후보 재료, D21·D22, docs/14) ---------------------
-- 검색어와 대략의 검색량만 둔다. 붙어 온 기사는 document(제목·링크만)에 넣고 doc_link 의 tag 'trend:<trend_id>' 로 잇는다.
CREATE TABLE IF NOT EXISTS trend (
  trend_id       INTEGER PRIMARY KEY,
  geo            TEXT NOT NULL,       -- KR, US
  term           TEXT NOT NULL,
  approx_traffic INTEGER,             -- 피드가 주는 어림값(2000+ -> 2000)
  pub_at         TEXT,                -- 피드의 게시 시각(UTC)
  first_seen_at  TEXT NOT NULL,
  last_seen_at   TEXT NOT NULL,
  flag           TEXT NOT NULL DEFAULT '',   -- 규칙으로 붙인 제외 표시: disaster / politics / '' (최종 판단은 후보 단계와 사람)
  source_id      TEXT NOT NULL REFERENCES source(source_id),
  UNIQUE (geo, term, pub_at)
);
CREATE INDEX IF NOT EXISTS ix_trend ON trend(geo, first_seen_at);

-- 13. SNS 게시 기록 (조종판, D23, docs/15) --------------------------------------
-- 올라간 글마다 한 줄. 처음 문안과 올린 문안을 함께 남겨 말투 기준으로 쓴다.
CREATE TABLE IF NOT EXISTS sns_post (
  post_id       INTEGER PRIMARY KEY,
  board_no      TEXT,                -- 조종판의 번호
  channel       TEXT NOT NULL,       -- 스레드, X
  slot_kst      TEXT,
  text_original TEXT,                -- 초안으로 들어온 문안
  text_final    TEXT NOT NULL,       -- 승인되어 올라간 문안
  edited        INTEGER NOT NULL DEFAULT 0 CHECK (edited IN (0,1)),
  remote_id     TEXT,
  url           TEXT,
  reply_id      TEXT,
  posted_at     TEXT NOT NULL        -- UTC
);

CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
INSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', '0.4');
