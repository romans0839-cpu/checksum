# 파이프라인 설계 (v0.2, 2026-10-05 — D12 반영)

> 콘텐츠 생성 구조(DB, 사실 표, 초안·검사·말투 단계)는 **docs/11_content_system_design.md**가 기준이다. 아래 그림의 `judgments/`·`content/` 모듈은 그 구조 위에서 구현한다. 구현된 것: `ledger/`(장부 v0), `db/`(표 정의·생성), `forecast/`(엔진 예측의 등록·봉인·채점·사실 묶음 v0 — docs/12, 실행기는 아직 없음), `collect/`(노동통계국 지표 수집 v0 — docs/13, 서버의 예약 작업 일꾼 `console/jobs.py`가 돌린다. 뜨는 검색어 수집 v0 — docs/14), `content/schedule_check.py`(일정 체크 생성기 v0).

목표: 1인 운영으로 주간 리듬(화 본편·프로, 금 무료 레터) + 평일 자동 3줄. 검수는 화·금에 집중, 평일은 5분 이내.
v0.1과의 차이: 신호 원천을 실제 라이브 봇(`C:\us_swing_bot`, 주 1회)으로 정정, "실시간 시그널" 제거, 장부·채점표·수치 대조 lint 추가.

```
라이브 봇 (us_swing_bot — 주도 업종 대장주, 주 1회)
        │  화 09:00 KST 주간 신호 파일 signals/target_*.json
        │  (청산·진입 후보, 주도 업종, 종목별 종가·30주선)
        ▼
pipeline/signals/ingest.py ──▶ data/track_record/signals.csv   (후보 단위, 단일 진실 원천)
        │                               │
        ▼                               ▼
pipeline/ledger/                  pipeline/track_record/stats.py
  commit.py   해시 체인 + nonce      표본수·기간·승률·손익비·기대값(R)·연속손실
  stamp.py    일일 타임스탬프                 │
  reveal.py   T+7 평문 공개                   ▼
  verify.py   누구나 대조             data/metrics/YYYY-WW.json
        │
        ▼
pipeline/judgments/                (판정 = 사전 정의 규칙의 출력, 전부 장부에 커밋)
  groups.py     주도 업종 지도 (26개 업종 상대강도·지속 주수)
  ticker.py     종목 체크표 (30주선 위치·기울기·변동성 분위·업종 강도·과거 분포) — 메일과 웹 페이지에 같은 표
  risk50.py     Top 50 요약 (무료)
  regime.py     레짐 계기판 (느린 지표, 과거 전환 횟수)
  scorecard.py  13주 뒤 자동 채점 → 분기 채점표
        │
        ▼
pipeline/content/
  daily.py      평일 아침 체크 5줄 (미국장 3줄 + 금리·환율 + 일정, 사실만)
  global_.py    글로벌 체크 초안 (1차 발표문 → 4줄 형식) + 금리·환율 체크판
  tuesday.py    화요일 본편 (기본) / 주간 모델 포트폴리오 (프로)
  friday.py     금요일 무료 레터 (통념 체크 + 장부 지연 공개 + 채점표 요약)
        │
        ▼  초안 → data/newsletters/drafts/  (사람 검수)
pipeline/publish/
  lint.py       금지어·필수문구 + 수치 대조(본문 숫자 = 원천 표) → 실패 시 발행 차단
  stibee.py     무료/기본 뉴스레터 발송
  telegram.py   프로 주간 발행 알림 (댓글 잠금 채널)
  naver.py      네이버 프리미엄콘텐츠 업로드 (초기 수동)
```

## 원칙

- **숫자는 LLM이 쓰지 않는다.** 코드가 계산한 값이 템플릿 변수로만 들어간다. LLM은 문장만 다듬는다
- 문장 3등급: 사실 / 판정 / 해석. 해석은 표시를 달고 한 호에 한 단락 이하
- 실계좌 금액·수량·수익률은 어떤 파일에도 기록하지 않는다 (D3). 봇의 신호 파일에서 수량·잔고 필드는 ingest 단계에서 버린다
- 열린 포지션은 손익이 아니라 30주선까지의 여유(%)로만 표시
- 발행 시각과 운영자 집행 시각을 장부에 기록 (D11 구독자 선발송 증빙)
- 벤더 데이터에서 나온 파생 수치(상태·순위·분포·통계)는 발행 경로에 연결한다(D26, 잠정). 원시 가격·차트·데이터 파일은 연결하지 않는다. 벤더 유래 사실에는 출처(`vendor_px`)를 남겨 한 번에 걷어 낼 수 있게 한다 (docs/10)

## 모듈별 책임

| 모듈 | 입력 | 출력 | 비고 |
|---|---|---|---|
| signals/ingest.py | 봇의 주간 신호 JSON | signals.csv 행 추가 | 계좌 편입 여부와 무관하게 진입 후보 전체. 수량·잔고 필드 제외 |
| ledger/commit.py | 신규 행·판정 | 공개 장부(해시), 비공개 평문 | 0건인 주도 기록. 첫 행은 기점 이전 보유 스냅샷 |
| track_record/stats.py | signals.csv | 통계 JSON + 표 | 청산 건만 집계. 표본 30 미만이면 "표본 부족" 표시 |
| judgments/scorecard.py | 커밋된 판정, 13주 뒤 데이터 | 채점표 | 독립 표본 환산 병기. 판정한 상태가 실제로 일어났는지를 본다 |
| content/*.py | 판정·통계 표 | 마크다운 초안 | LLM 프롬프트는 `prompts/`에 버전 관리 |
| publish/lint.py | 초안 | pass/fail + 사유 | `templates/banned_terms.txt` + 수치 대조 |

## 구현 순서 (로드맵 W1~W2, 11월)

1. 장부 v0: 화요일 신호 파일 기록 + 일일 타임스탬프 (W1)
2. 장부 v1: 해시 체인·nonce·verify, 후보 전체 기록, 시각 기록 (W2)
3. daily3 + 수치 대조 lint + friday 템플릿 (W2)
4. stibee 발송 연결 (W3 창간)
5. judgments 3종 + tuesday 본편 (11월)
6. scorecard (첫 채점은 10월 판정분이 13주 지난 1월)

## 인프라

- 봇과 분리: 봇 저장소는 읽기만 한다. 파이프라인은 별도 사용자·venv
- 비밀정보는 `.env` (git 제외). 스티비·텔레그램·LLM API 키
- 발행 스케줄(KST): 평일 06:30 3줄 / 화 09:30 장부 커밋 → 10:00 프로 → 12:00 본편 / 금 무료 레터
