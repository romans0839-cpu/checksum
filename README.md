# usstock-sub — Checksum(체크섬) 사업 운영 폴더

서학개미가 사고팔기 전에 들르는 "체크". 종목과 시장의 상태를 숫자로 가려 주는 도구와 레터를 함께 내는 구독 서비스.

## 어디에 무엇이 있나

| 알고 싶은 것 | 파일 |
|---|---|
| 지금 무엇이 진행 중이고 무엇이 막혀 있나 | `plan/status.md` (세션 시작 시 가장 먼저) |
| 무엇을 결정했나, 왜 | `plan/decisions.md` (D1~, 미결 포함) |
| 언제 무엇을 하나 | `plan/roadmap_2026Q4.md` (일정 변동은 status.md가 기준) |
| **사업 전체 그림** (정체성·상품·콘텐츠·유튜브·해자·목표) | `docs/09_service_moat_strategy.md` |
| 사업계획서 요약 | `docs/02_business_plan.md` |
| 수익 모델과 목표 경로 | `docs/04_revenue_model.md`, `scripts/revenue_sim.py`, `scripts/path_to_100m.py` |
| 글이 만들어지는 구조 (DB, 사실, 초안, 검사) | `docs/11_content_system_design.md`, `pipeline/db/` |
| **콘텐츠 구조** (줄기 × 깊이 × 채널, D21 확정) | `docs/14_content_architecture.md` |
| 두 엔진 지표 예측 (봉인·채점) | `docs/12_forecast_engines.md`, `pipeline/forecast/`, `data/forecast/` |
| **PC 없이 도는 운영** (조종판 시트 + 서버 일꾼 + SNS 게시) | `docs/15_ops_console.md`, `pipeline/console/`, `pipeline/publish/threads.py`, `pipeline/publish/x.py`, `requirements-server.txt` |
| **SNS 초안이 조종판에 들어오는 길** (저장소의 초안 파일 → 대기열 '초안') | `docs/15_ops_console.md` §5-3, `pipeline/console/drafts.py`, `data/sns/drafts/` |
| **코드가 서버에 가는 길** (원본 = 이 저장소, 서버가 받아 자체 시험 뒤 반영, D24) | `docs/15_ops_console.md` §5-1, `scripts/server_sync.sh`, `sync.bat`(PC 사본 맞추기) |
| 트렌디 체크 후보 재료·일정 체크 | `pipeline/collect/trends.py`, `pipeline/content/schedule_check.py`, `data/calendar/` (운영은 예약 작업 "트렌디 체크 후보") |
| 지표 데이터 수집 (통계기관 API → DB → 사실 묶음). **서버에서 돈다** | `docs/13_indicator_data.md`, `pipeline/collect/`, `pipeline/console/jobs.py`(예약 작업 일꾼, docs/15 §5-2), `scripts/server_cron.sh`, `.env.example` |
| 말투와 감정 규칙 | `templates/voice_guide.md` (표본은 `data/private/voice/`) |
| SNS 글의 컨셉과 카피 원칙 (D27) | `docs/05_marketing_strategy.md` §0 · `templates/copy_guide.md` · `templates/avoid_terms.txt` |
| 규제에서 지킬 것 | `docs/03_regulation_checklist.md`, `templates/banned_terms.txt`, `templates/disclaimer.md` |
| 데이터 라이선스 | `docs/10_data_license.md` |
| 마케팅·채널 | `docs/05_marketing_strategy.md`, `docs/07_channel_setup.md` |
| 사업자등록·신고 | `docs/08_business_registration.md` |
| 시장 조사 | `docs/01_market_research.md` |
| 장부(신호 봉인) | `pipeline/ledger/`, `ledger_commit.bat` |
| Claude 작업 규칙 | `CLAUDE.md`, `claude-project/PROJECT_PROMPT.md`(프로젝트 지침 원본) |

## 일하는 체계

1. 세션을 시작하면 `plan/status.md` → `plan/decisions.md` → `plan/roadmap_2026Q4.md` 순으로 읽는다.
2. 결정은 `plan/decisions.md`에 번호·날짜·근거·기각한 대안과 함께 쌓는다. 기존 항목은 덮어쓰지 않는다. 번호는 마지막 번호 + 1.
3. 상태가 바뀌면 그 자리에서 `plan/status.md`를 고친다. 여러 세션이 이 파일로 서로의 진행을 본다.
4. 결정이 바뀌면 기준 문서(docs/09)와 관련 문서를 함께 고치고, `claude-project/00_context_brief.md`와 프로젝트 지식을 맞춘다.
5. 산출물은 내보내기 전에 마지막 검토를 한 번 더 하고, 고친 것과 남은 불확실성을 밝힌다.
6. 금요일 주간 리뷰: 로드맵 체크, 지표 기록(`data/metrics/`), 다음 주 우선순위.

## 명령

```
python scripts/revenue_sim.py
python scripts/path_to_100m.py
python -m pipeline.ledger.commit      (또는 ledger_commit.bat)
python -m pipeline.ledger.verify
python -m pipeline.db.init
python -m pipeline.forecast.selftest  (엔진 예측 봉인·채점 자체 시험)
python -m pipeline.collect.bls        (노동통계국 지표 수집. 서버에서는 python -m pipeline.console.jobs tick 이 때맞춰 돌린다)
python -m pipeline.collect.selftest   (수집·DB·사실 묶음 자체 시험)
python -m pipeline.publish.lint data/newsletters/drafts/<file>.md
```
