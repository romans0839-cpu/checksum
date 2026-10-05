# CLAUDE.md — 프로젝트 작업 규칙

이 저장소는 한국 서학개미 대상 미국주식 정보 구독 서비스(서비스명: Checksum / 체크섬)의 사업 운영 프로젝트다. 코드와 문서를 함께 관리한다.

**원본은 이 깃허브 저장소(`romans0839-cpu/checksum`, 비공개)다(D24).** 세션은 저장소를 받아 고치고 올린다. 올린 코드는 서버가 10분 안에 받아 자체 시험을 통과할 때만 쓴다. PC 폴더 `C:\usstock-sub`는 사본이므로 그곳의 저장소 파일을 직접 고치지 않는다.

## 먼저 읽을 것
0. `plan/status.md` — **진행 중 항목·대기 사유·다음 행동**. 세션 시작 시 가장 먼저 읽고, 상태가 바뀌면 즉시 갱신(주간 리뷰를 기다리지 않음)
1. `plan/decisions.md` — 확정된 결정(D1~D25). 이와 충돌하는 제안을 하기 전에 반드시 근거를 제시하고 결정 항목을 새로 추가할 것
2. `plan/roadmap_2026Q4.md` — 현재 주차의 할 일
3. `docs/03_regulation_checklist.md` — 규제 제약. 모든 콘텐츠·기능 제안은 이 문서를 위반하면 안 됨

4. `docs/05_marketing_strategy.md` — 채널 역할·콘텐츠 기둥·시간 예산. SNS 콘텐츠 제안은 이 틀 안에서

## 절대 규칙
- **수익률을 근거로 종목을 공유하는 서비스에 매몰되지 않는다 (D12).** 기능·콘텐츠·카피 제안의 근거가 '수익률이 좋았다'이면 버린다. 수익률은 KPI가 아니다. 시그널은 과정의 증거이지 상품의 중심이 아니다
- "검증된 시그널"이라고 쓰지 않는다. 시스템의 지위는 '표본외 1차 필터 통과, 최종 판정은 라이브 계측'. 시스템 사실은 `C:\us_swing_bot\LIVE_LOGIC_ASIS.md` 기준(읽기 전용, `.env`·`kis_token_cache.json`은 읽지 않음)
- 데이터 라이선스 확정 전에는 벤더 데이터 유래 수치·지표를 싣는 발행물을 "발행 가능"이라고 하지 않는다 (docs/10)
- 발행물의 숫자는 코드가 계산한 값만 쓴다. 열린 포지션의 손익, 실적·금리·지수 방향 전망, 원인 단정은 쓰지 않는다. 글로벌 경제·시황은 맥락 설명으로 다룬다(무슨 일 / 서학개미에게 닿는 길 / 시장이 이미 알던 것 / 아직 모르는 것)
- 예측의 예외는 엔진 예측 하나다(D18, docs/12): 미국 경제지표의 발표값을 이름 붙은 엔진이 범위로 내고, 발표 전에 장부에 봉인하고 발표 뒤 채점한다. 가격·지수·환율·개별 실적·기준금리 결정은 대상이 아니다. 과거 데이터로 엔진 성능을 재지 않고, 엔진이 낸 값은 사람이 고치지 않으며, 정확도를 카피로 쓰지 않는다. **발표 전 예측값은 발행물·SNS·영상 어디에도 싣지 않는다.** 연말까지는 발표가 끝난 뒤의 성적만 공개하고, 준비 과정은 메이킹 형식으로 보여 줄 수 있다. 메이킹 화면에서 레시피·사실 묶음·API 키·실계좌·새 후보 종목명은 가린다(D20)
- 콘텐츠 구조는 docs/14가 기준이다(D21): 네 줄기(뉴스·엔진·종목 체크·사람과 과정) × 세 깊이 × 다섯 채널. 재미 뉴스 코너 이름은 "트렌디 체크". **종목 체크에는 엔진 이름을 붙이지 않고, 엔진의 종목 전망·평가는 만들지 않는다.** 엔진의 해석은 표시를 달고 양쪽 경우를 함께 쓰며 봉인된 범위에 묶는다. 개인별 레터(내 종목)는 표준 카드의 조립으로만 설계한다 — 보유 수량·매수가를 받지 않고 개인을 향한 문장을 만들지 않으며, 규제 답변 전에는 "열 수 있다"고 하지 않는다. 메신저는 일방향 채널만(텔레그램 기본, 카카오 오픈채팅·그룹 금지)
- **콘텐츠 후보(트렌디 체크 등)를 낼 때는 사실만 내지 않는다. 해석과 의미를 가설 2~3개로 함께 낸다(D22).** 가설은 "제 가설은"으로 표시하고 산업·소비·정책·경기의 의미에 대해 구체적으로 쓴다. 방어적으로 줄이지 않는다 — 고르고 싣는 책임은 Nick에게 있다. 남는 선은 특정 종목·가격의 방향, 매매 권유, 단정·선동 표현뿐이다. 숫자는 출처에서 인용하고 링크를 단다
- 운영은 PC가 아니라 서버(EC2)와 조종판(Google 시트)을 전제로 설계한다(D23, docs/15). Nick이 PC에서 직접 실행해야 하는 일을 새로 만들지 않는다. 사람이 승인하지 않은 글이 올라가는 경로를 만들지 않는다. 장부는 한 곳에서만 쓴다
- API 키는 서버의 `.env`(와 PC의 `C:\usstock-sub\.env`)에만 둔다. 키 값을 채팅·문서·로그·커밋에 적지 않는다. 저장소에는 `.env`, 키 파일, `data/private/`, DB를 올리지 않는다. 올리기 전에 자체 시험 4종을 돌린다 — main에 올라간 코드는 키가 있는 서버에서 돈다(D24). 엔진 이름은 아들러/플레처(D19)이며 "AI가 기관보다 정확하다"는 봉인 기록이 생기기 전에는 쓰지 않는다
- 발행물의 감정 표현은 한 호에 한두 곳, 사람과 이미 일어난 일에만 붙인다. 가격 방향·행동 권유와 섞지 않고, 후보만 내고 고르는 것은 Nick이다 (D17, `templates/voice_guide.md`)
- 콘텐츠 생성은 docs/11의 흐름을 따른다: LLM은 사실 표만 보고, 숫자는 코드가 만든 문장으로만 들어간다. 뉴스의 중요도는 숫자가 정한다
- 용어는 '체크'(D14). '검산'은 쓰지 않는다. 결과는 상태로만 쓰고 "통과/불통과"로 쓰지 않는다
- 유튜브·영상 기획은 얼굴 비공개·본인 목소리·PC 화면 녹화 주력(손 오프닝·엔딩만 아이폰) 전제(D15). AI 음성·스톡 영상·버튜버 아바타는 제안하지 않는다
- 실계좌 금액·수량·수익률은 어떤 파일에도 기록하지 않는다 (`data/private/`는 git 제외이며 그곳에만). 공개 통계는 R배수 기반 시그널 단위
- 발행물 초안은 `templates/banned_terms.txt` 기준 lint 통과 전에는 "발행 가능"이라고 표현하지 않는다
- 양방향 소통(개별 상담·질의응답·유튜브 멤버십·오픈채팅) 기능을 제안하지 않는다
- 평일 90분·주말 3시간 시간 예산을 넘는 계획을 제안하지 않는다. 자동화로 풀 수 없으면 범위를 줄인다
- 스레드·X·인스타 포스트 초안에는 링크를 넣지 않는다(셀프 답글에만). 수익률·예측·추천 톤 금지
- 조사 자료의 수치는 출처 URL과 함께 기록한다

## 작업 방식
- **마지막 검토를 한 번 더 한다.** 산출물(문서·코드·초안)을 내보내기 전에 다시 읽고, 검토에서 고친 것과 남은 불확실성을 함께 밝힌다 (Nick 요청, D17)
- 문서는 한국어 마크다운. 결정은 `plan/decisions.md`에 날짜와 근거로 남긴다
- SNS 초안은 `data/sns/drafts/`에 초안 파일로 올린다(D25, 형식은 `pipeline/console/drafts.py` 머리말). 올리기 전에 `python -m pipeline.console.drafts check <파일>`을 돌린다. 올리면 서버가 대기열에 '초안'으로 싣는다. 아직 일어나지 않은 일에 기대는 글에는 `- 조건:`을 적고, 나중에 채울 값은 `[채울 것: …]`으로 둔다. 지금 없는 기능을 있는 것처럼 쓰지 않는다
- 서버에서 도는 작업을 더할 때는 `pipeline/console/jobs.py`의 작업표에 더한다(cron 줄을 늘리지 않는다). 결과는 "오늘 현황"에 한 줄로 남긴다
- 주간 리뷰(금요일): 로드맵 체크박스 갱신 → 지표 스냅샷 `data/metrics/YYYY-WW.json` → 결정 기록
- 코드는 Python 3.11+, 표준 라이브러리 우선. 비밀정보는 `.env`
- 수익 가정을 바꾸면 `scripts/revenue_sim.py`를 다시 돌리고 `docs/04_revenue_model.md`의 표를 갱신한다

## 자주 쓰는 명령
```
python scripts/revenue_sim.py                       # 수익 시뮬레이션
python scripts/path_to_100m.py                      # D10 목표 경로 (36·60개월)
python -m pipeline.track_record.stats --since 2026-10-06   # 공개용 시그널 통계
python -m pipeline.publish.lint data/newsletters/drafts/<file>.md   # 발행 전 검사
python -m pipeline.ledger.commit                    # 이번 주 신호 장부 봉인 (ledger_commit.bat)
python -m pipeline.ledger.verify                    # 장부 점검
python -m pipeline.db.init                          # 콘텐츠 DB 생성 (data/db/checksum.db)
python -m pipeline.collect.bls                      # 노동통계국 지표 수집 — 서버에서는 예약 작업 일꾼이 돌린다. --dry-run 은 저장 없이 확인만(PC의 collect_indicators.bat)
python -m pipeline.collect.selftest                 # 수집·DB·사실 묶음 자체 시험 (인터넷·실제 DB 안 씀)
python -m pipeline.collect.trends                   # 뜨는 검색어 수집(한국·미국) — 트렌디 체크 후보 재료
python -m pipeline.content.schedule_check           # 일정 체크(7일). --tonight 은 오늘 밤 것만
python -m pipeline.content.selftest                 # 일정 체크 자체 시험
python -m pipeline.console.selftest                 # 조종판 일꾼 자체 시험 (시트·계정 안 씀)
python -m pipeline.console.worker run --dry-run     # 조종판에서 승인된 글을 올리지 않고 미리 보기 (서버)
python -m pipeline.console.drafts check data/sns/drafts/<file>.md   # SNS 초안 파일을 올리기 전 검사. 올리면 서버가 대기열에 '초안'으로 싣는다 (docs/15 §5-3)
python -m pipeline.console.jobs tick                # 서버: 때가 된 예약 작업(지표 수집 등)을 돌리고 '오늘 현황'에 적는다 (cron 5분마다). plan 은 앞으로의 예정, run <작업> 은 지금 한 번
bash scripts/server_sync.sh                         # 서버: 새 코드 받기 → 자체 시험 → 반영 또는 되돌림 (cron 10분마다)
bash scripts/server_cron.sh                         # 서버: 예약 세 줄 맞추기 (한 번). 예약 작업의 시각은 cron 이 아니라 pipeline/console/jobs.py 가 정한다
python -m pipeline.forecast.bundle --event CPI --ref 2026-09   # 엔진에 줄 사실 묶음 만들기
python -m pipeline.forecast.selftest                # 엔진 예측 봉인·채점 자체 시험 (실제 장부는 건드리지 않음)
python -m pipeline.forecast.seal --file <예측.json>  # 예측 봉인 (발표 12시간 전까지)
python -m pipeline.forecast.score                   # 봉인된 예측 채점
```

## 폴더
- `claude-project/` Claude 프로젝트용 시스템 프롬프트와 지식 업로드 파일. docs/가 바뀌면 00_context_brief.md도 갱신
- `docs/` 조사·사업계획·규제·재무·마케팅·전략(09)·데이터 라이선스(10)·콘텐츠 시스템 구조(11)·두 엔진 예측(12)·지표 데이터 수집(13)·콘텐츠 구조(14)·PC 없이 도는 운영(15) (참조용, 큰 변경은 새 버전 번호)
- `plan/` 로드맵·의사결정 (매주 갱신)
- `pipeline/` 시그널 수집 → 통계 → 콘텐츠 생성 → 발행
- `templates/` 뉴스레터 템플릿, disclaimer, 금지어
- `data/` 트랙레코드 CSV, 주간 지표, 뉴스레터 초안/발행본, SNS 초안 파일(`data/sns/drafts/` — 올리면 서버가 조종판 대기열에 '초안'으로 싣는다)
- `scripts/` 일회성 분석 스크립트
