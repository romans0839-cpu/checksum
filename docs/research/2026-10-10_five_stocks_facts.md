# 다섯 종목의 사실 — 일정, 지난 분기 숫자, 상품 구조 (2026-10-10 조사)

D37(다섯 종목이 주인공)의 글을 쓰려고 모은 사실이다. 테슬라 · 엔비디아 · 알파벳은 회사의 공시와 보도자료, SOXL · QQQ는 운용사와 지수 사업자의 자료를 먼저 찾았다. 편성과 초안은 `docs/05_marketing_strategy.md` §0-1, `data/sns/drafts/2026-10-15_five_stocks_v5.md`.

- **세션이 원문을 다시 열어 확인한 것(10/10)**: 테슬라 3분기 인도 486,532대 · 생산 464,391대 · 에너지 저장 13.7GWh와 실적 발표 10/21 장 마감 뒤 · 질의응답 동부 17:30(SEC 8-K 첨부) / 알파벳 실적 콜 10/28 동부 16:30(회사 공지) / SOXL 기초 지수의 종목 수 30과 상위 10 비중(운용사 팩트시트, 6/30 기준) / QQQ 상위 10 비중과 합계 46.81%(Schwab, 10/8 기준 — 운용사 자료가 아니다)
- 나머지는 조사가 돌려준 그대로이고 세션이 원문을 다시 열지 않았다. **글에 쓰는 숫자는 쓰기 전에 그 줄의 링크를 다시 연다**
- "2차"라고 적힌 것은 회사 자료가 아니라 언론 · 데이터 사이트로 확인한 것이다. 엔비디아의 실적 발표일은 회사가 아직 알리지 않았다
- 이 문서는 조사 기반 정리이며 법률 자문이나 투자 권유가 아니다

## 1. 테슬라 · 엔비디아 · 알파벳

테슬라와 알파벳은 다음 실적 발표일을 회사가 공지했고, 엔비디아는 아직 공지하지 않았습니다. 숫자는 회사 보도자료와 SEC 공시에서 옮겼고, 언론으로만 확인한 것은 [2차]로 표시했습니다.

### 1. 테슬라 (TSLA)

**① 다음 실적 (회사 공식 발표)**
- 2026년 3분기 실적은 10/21(수) 장 마감 뒤에 나옵니다. 질의응답 웹캐스트는 동부 17:30이고, 한국 시간으로 **10/22(목) 06:30**입니다. https://www.sec.gov/Archives/edgar/data/0001318605/000162828026064366/exhibit991111111.htm

**② 지난 분기 (2026년 2분기, 7/22 발표)**

| 항목 | 2026 2분기 | 2025 2분기 |
|---|---|---|
| 매출 | $28,236M | $22,496M |
| 영업이익 / 영업이익률 | $398M / 1.4% | $923M / 4.1% |
| 주당순이익 GAAP / 비GAAP | $0.32 / $0.33 | $0.33 / $0.40 |
| 인도 / 생산 | 480,126 / 451,758대 | 384,122 / 410,244대 |
| 자동차 매출총이익률 (GAAP) | 16.9% | 17.2% |
| 같은 값, 규제 크레딧 제외 | 16.3% | 15.0% |
| 에너지 저장장치 배치 | 13.5 GWh | 9.6 GWh |
| 잉여현금흐름 (설비투자 $5,789M) | −$1,092M | $146M |

- GAAP 순이익에는 SpaceX 지분 미실현 평가이익 $1,005M(세전)이 들어 있습니다.
- 출처: https://www.sec.gov/Archives/edgar/data/0001318605/000162828026049213/exhibit991.htm

**③ 2026년 3분기 인도·생산 (10/2 발표)**

| 항목 | 2026 3분기 | 2025 3분기 | 2026 2분기 |
|---|---|---|---|
| 인도 | 486,532대 | 497,099대 | 480,126대 |
| 생산 | 464,391대 | 447,450대 | 451,758대 |
| 에너지 저장장치 | 13.7 GWh | 12.5 GWh | 13.5 GWh |

- 인도는 전년 동기 대비 −2.1%, 전 분기 대비 +1.3%이고, 생산은 각각 +3.8%, +2.8%입니다(제가 단순 계산한 값).
- 발표일 확인: https://www.sec.gov/Archives/edgar/data/1318605/000162828026064366/tsla-20261002.htm
- 전년 동기 값: https://www.sec.gov/Archives/edgar/data/1318605/000162828025043530/exhibit991111.htm

**④ 10/10~11/10 일정**
- 10/15(목): 로드스터 공개 행사. 10/1 예정이었으나 테슬라가 X에서 기상을 이유로 미뤘습니다. 시각과 중계 여부는 공지되지 않았습니다. [2차] https://www.electrive.com/2026/10/01/tesla-postpones-roadster-unveiling-due-to-weather/
- 10/21: 3분기 실적 (위 ①).
- 2026년 정기 주주총회: 날짜 미정. 4/30 기준 10-K/A에 "이사회가 아직 정하지 않았다"고 적혀 있습니다. https://www.sec.gov/Archives/edgar/data/1318605/000110465926053166/tm2611837d1_10ka.htm

**⑤ 최근 2주 공시**
- 9/29 8-K: 신용 약정 3건을 새로 맺었습니다. $20.0B 지연 인출 기한부 대출(3년), $8.0B 5년 한도 대출, $2.0B 364일 한도 대출입니다. 기존 $5.0B 한도는 해지했고, 9/29 현재 인출 잔액은 없습니다. https://www.sec.gov/Archives/edgar/data/1318605/000162828026063820/tsla-20260929.htm
- 9/29: SEC가 테슬라의 "개인 주주 자발적 상시 의결권 위임 프로그램"에 비조치 의견서를 냈습니다. https://www.sec.gov/rules-regulations/no-action-interpretive-exemptive-letters/division-corporation-finance-no-action/tesla-inc-092926
- 10/2 8-K: 3분기 인도·생산 (위 ③).

**⑥ 주식 수 변동**
- 최근 3개월 안에 분할이나 자사주 매입 발표는 찾지 못했습니다. 2분기 자료에도 언급이 없습니다.

### 2. 엔비디아 (NVDA)

**① 다음 실적 (회사 미발표)**
- 회계 2027년 3분기 실적입니다. 분기 종료일은 10/25로 추정합니다(2분기 종료 7/26에 13주를 더한 값).
- 회사 보도자료는 10/8까지 없습니다. 작년에는 10/29에 공지했습니다. https://nvidianews.nvidia.com/news/latest
- 외부 달력은 서로 다릅니다. Wall Street Horizon은 11/17(화) 장 마감 뒤를 "confirmed"로 적었고, days.to는 11/18(수) 17:00을 추정치로 적었습니다. [2차] https://www.wallstreethorizon.com/nvidia-earnings-calendar · https://days.to/nvidia-earnings
- 콜이 관례대로 동부 17:00이면 한국 시간으로 다음 날 07:00입니다(11월은 +14시간).

**② 지난 분기 (회계 2027년 2분기, 7/26 종료, 8/26 발표)**

| 항목 | 이번 분기 | 전년 동기 |
|---|---|---|
| 매출 | $96,221M | $46,743M |
| 영업이익 (GAAP) | $63,734M | $28,440M |
| 매출총이익률 GAAP / 비GAAP | 75.0% / 75.0% | 72.4% / 72.5% |
| 주당순이익 GAAP / 비GAAP | $2.46 / $2.22 | $1.08 / $1.01 |
| 데이터센터 매출 | $89.0B (전년 대비 +117%, 전 분기 대비 +18%) | 금액 미기재 |

- 다음 분기 전망: 매출 $108.0B ±2%, 매출총이익률 74.0% ±0.5%p. 중국 데이터센터 컴퓨트 매출은 전망에 넣지 않았습니다.
- 회계 2027년 1분기부터 비GAAP에서 주식보상비용을 빼지 않습니다. 그래서 전년 비GAAP 값은 당시 발표치와 다릅니다.
- 출처: https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-second-quarter-fiscal-2027

**④ 10/10~11/10 일정**
- 10/20~22: GTC 베를린. 젠슨 황 기조연설은 10/21 11:00 중부유럽 서머타임이고, 한국 시간으로 10/21 18:00입니다. https://www.nvidia.com/de-de/gtc/
- GTC 워싱턴은 11/30~12/3이라 범위 밖입니다. https://www.nvidia.com/en-us/gtc-dc/attend/

**⑤ 최근 2주 발표**
- 9/28: 자사주 매입 한도를 $150B 늘렸습니다. 남은 한도는 $235B이고, 회계 2028년까지 집행할 예정이라고 밝혔습니다. https://investor.nvidia.com/news/press-release-details/2026/NVIDIA-Announces-a-150-Billion-Share-Repurchase-Authorization-Increase/default.aspx
- 10/1: 분기 배당 주당 $0.25를 지급했습니다(기준일 9/10). 출처는 ②의 실적 보도자료입니다.
- 10/8: 미국 과학 연구에 5년간 $1B 상당을 지원한다고 발표했습니다. https://nvidianews.nvidia.com/news/nvidia-commits-1-billion-to-advance-us-science-over-the-next-five-years

**⑥ 주식 수 변동**
- 위 9/28 자사주 한도 증액이 해당합니다. 2분기 주주환원은 약 $26.0B였습니다.
- 9/2 8-K: 허깅페이스 인수 계약(약 $11.9B, 지분 기반 유지 프로그램 최대 약 $1.0B, 2027년 상반기 종결 예상). 대가를 현금으로 줄지 주식으로 줄지는 적혀 있지 않습니다. https://www.sec.gov/Archives/edgar/data/1045810/000104581026000078/nvda-20260902.htm
- 주식 분할은 찾지 못했습니다.

### 3. 알파벳 (GOOGL)

**① 다음 실적 (회사 공식 발표, 10/6 공지)**
- 2026년 3분기 실적 컨퍼런스콜은 10/28(수) 동부 16:30이고, 한국 시간으로 **10/29(목) 05:30**입니다.
- 실적 자료는 같은 날 "콜 전에" IR 사이트에 올린다고만 적혀 있습니다. 정확한 시각은 없습니다.
- 출처: https://abc.xyz/investor/news/news-details/2026/Alphabet-Announces-Date-of-Third-Quarter-2026-Financial-Results-Conference-Call-2026-8tpGZsLS6v/default.aspx

**② 지난 분기 (2026년 2분기, 7/22 발표)**

| 항목 | 2026 2분기 | 2025 2분기 |
|---|---|---|
| 매출 | $119,796M | $96,428M |
| 영업이익 / 영업이익률 | $40,770M / 34% | $31,271M / 32% |
| 희석 주당순이익 | $9.11 | $2.31 |
| 구글 검색 등 | $63,271M | $54,190M |
| 유튜브 광고 | $11,055M | $9,796M |
| 구글 클라우드 매출 / 영업이익 | $24,768M / $8,814M | $13,624M / $2,826M |
| 설비투자 | $44,924M | $22,446M |

- 주당순이익 $9.11에는 지분증권 평가이익 등 순이익 $98.0B의 효과 약 $6.26이 들어 있습니다(회사 설명).
- 출처: https://www.sec.gov/Archives/edgar/data/0001652044/000165204426000066/googexhibit991q22026.htm
- 2026년 연간 설비투자 계획: $195~205B로 올렸습니다(이전 $180~190B). 최고재무책임자가 콜에서 한 발언이고 보도자료에는 없습니다. [2차] https://www.marketbeat.com/instant-alerts/alphabet-q2-earnings-call-highlights-2026-07-22/

**④ 10/10~11/10 일정**
- 10/28 실적 말고는 회사가 공지한 일정을 찾지 못했습니다.

**⑤ 최근 2주 발표**
- 10/6: 3분기 실적 콜 날짜 공지 (위 ①).
- 10/8: 구글 클라우드가 "Gemini at Work '26" 행사에서 업무용 "Gemini agent"를 발표했습니다. https://googlecloudpresscorner.com/gemini-at-work-2026
- 10/8: 웨이모가 $5B 기한부 대출을 마무리했습니다(웨이모의 첫 차입). [2차, 로이터] https://investing.com/news/stock-market-news/alphabets-waymo-secures-5-billion-term-loan-to-accelerate-expansion-4939362
- 이 기간에 8-K는 찾지 못했습니다(제3자 목록 기준). https://www.marketbeat.com/stocks/NASDAQ/GOOG/sec-filings/

**⑥ 주식 수 변동**
- 6/1에 $80B 규모 증자 계획을 발표했습니다(3개월보다 조금 앞). 구성은 보통주 공모, 의무전환우선주, 버크셔 해서웨이 사모 $10B, 수시 매각 프로그램 $40B입니다. 수시 매각은 "3분기 시작 예정"이라고 적혀 있어 최근 3개월에 걸칩니다. https://www.sec.gov/Archives/edgar/data/0001652044/000119312526257724/d83560dex991.htm
- 2분기에 보통주 1억 1,400만 주($30,417M)와 6.25% 의무전환우선주($19,034M)를 발행했습니다. 상반기 자사주 매입은 0입니다. 7/15 기준 발행주식은 A 5,868 / B 835 / C 5,527백만 주입니다. https://www.sec.gov/Archives/edgar/data/0001652044/000165204426000071/goog-20260630.htm
- 6/30까지 수시 매각 실적은 없고, 자사주 매입 잔여 한도는 $69.5B입니다. [2차] https://nasdaq.com/articles/alphabet-paying-dividend-while-selling-85-billion-new-stock
- 주식 분할은 찾지 못했습니다.

### 확인하지 못한 것
- **엔비디아 실적 발표일**: 회사 공지를 찾지 못했습니다. 11/17과 11/18은 외부 달력 값이고 서로 다릅니다.
- **엔비디아 전년 동기 데이터센터 매출**: 금액이 이번 보도자료에 없습니다. 부문이 "Data Center / Edge Computing"으로 바뀌어 작년 발표치와 그대로 비교되는지도 확인하지 못했습니다.
- **테슬라 로드스터 행사**: 10/15의 시각, 장소, 중계 여부를 확인하지 못했습니다. 연기 공지인 X 게시물 원문도 직접 열지 못했습니다.
- **테슬라 주주총회**: 2026년 날짜와 위임장 제출 여부. 4월 이후 새 공지를 찾지 못했습니다.
- **알파벳 설비투자 계획**: 회사 원문(콜 녹취록)에서 확인하지 못했습니다.
- **알파벳 수시 매각**: 3분기에 실제로 팔았는지와 그 수량. 3분기 10-Q가 나와야 알 수 있습니다.
- **알파벳 배당**: 3분기 배당의 기준일과 지급일. 보통 실적 발표 때 공지합니다.
- **8-K 전수 확인**: SEC EDGAR 목록을 직접 열 수 없어 제3자 목록에 기댔습니다. 빠진 공시가 있을 수 있습니다.
- **엔비디아 투자자 행사**: 10~11월 참석 일정. IR 달력이 열리지 않았습니다.

### 검토 메모
- 표의 숫자는 회사 문서를 요약 도구로 읽어 옮긴 값입니다. 테슬라 자동차 매출총이익률 두 줄은 문서의 조정표 행을 다시 읽어 확인했고, 알파벳과 엔비디아는 전년 동기 값이 작년 발표치와 맞는지 대조했습니다.
- "테슬라-SpaceX 합병"은 언론의 추측이고 회사 발표가 아니어서 뺐습니다.
- 알파벳을 상대로 한 증권 집단소송 공지(10/5, 로펌 보도자료)도 회사 공시가 아니어서 뺐습니다.

## 2. SOXL · QQQ · TQQQ

발행 전에 알아 둘 점이 세 가지 있습니다.
- 운용사 원문 인용은 조회 도구의 길이 제한으로 일부만 확인한 문장이 있습니다. 발행 전에 원문과 대조해야 합니다.
- Invesco 공식 페이지는 수치가 로딩되지 않아 QQQ의 비중·순자산은 2차 자료입니다.
- QQQ 상위 10에서 브로드컴이 빠지고 마이크론·AMD가 4·5위입니다.

### 1. SOXL

현재 공식 이름은 "Direxion Daily Semiconductor Bull 3X ETF"입니다("Shares"가 아님) [S1][S2].

| 항목 | 값 | 기준일 | 출처 |
|---|---|---|---|
| 지수 · 사업자 | NYSE Semiconductor Index (ICESEMIT) · ICE Data Indices, LLC | 설명서 2026-02-27 | [S2] |
| 목표 배수 | "The Fund seeks daily investment results, before fees and expenses, of 300% of the daily performance of the Index." | 2026-02-27 | [S2] |
| 총보수 | 총 0.91% / 순 0.75% (운용보수 0.75%, 비용 상한 2027-09-01까지) | 2026-02-27 | [S1][S2] |
| 순자산 | 252.8억 달러(10-05) / 256.3억 달러(10-08), 2차 자료 | 2026-10 | [S4][S5] |
| NAV | 142.31달러 | 2026-10-08 | [S1] |
| 지수 종목 수 | 30개 (미국 상장 반도체 상위 30) | 2025-12-31 | [S2] |
| 펀드 실제 구성 | 지수 스왑 여러 건 + 현금성 자산 + 개별 주식, 43줄 (2차 자료) | 2026-10-08 | [S5] |

**지수 상위 10 (2026-06-30, 운용사 팩트시트 [S3])**
- 마이크론 8.55 · AMD 8.10 · 엔비디아 6.82 · 인텔 6.34 · 브로드컴 6.08
- 어플라이드 5.78 · KLA 5.65 · 마벨 5.23 · 램리서치 4.90 · TSMC 4.27 (%)

**더 최근의 근사치 (2026-10-07, 2차 자료 [S6])**: iShares SOXX 보유 비중입니다.
- AMD 9.55 · 인텔 8.79 · 마이크론 7.90 · 엔비디아 7.48 · 브로드컴 7.07 · TSMC 3.03 (%)
- SOXX가 지금도 같은 지수를 따르는지는 이번에 다시 확인하지 못했습니다. [S7]은 2021년 iShares 문서입니다.

**비중 상한 규칙** (2021-04 iShares 설명서 보충 [S7], 당시 이름 ICE Semiconductor Index)
- 전 종목 8% 상한, 상위 5개 밖은 4% 상한, ADR 합계 10% 상한.
- 매년 9월 전면 재구성, 3·6·12월 셋째 금요일 장 마감 뒤 리밸런싱.
- 현행 ICE 방법론 문서로는 확인하지 못했습니다.

**하루 넘겨 보유할 때의 문구**
- 요약 투자설명서 [S2]: "The Fund does not seek to achieve its stated investment objective for a period of time different than a trading day."
- 같은 문서 복리 위험 항목(두 조각으로 확인): "The Fund's performance for periods greater than a trading day will be the result of each day's returns compounded over the period, which is likely to differ from 300% of the Index's performance, before fees and expenses."
- 같은 문서: "For periods longer than a single day, the Fund will lose money if the Index's performance is flat…"
- 상품 페이지 [S1]: "The funds should not be expected to provide three times or negative three times the return of the benchmark's cumulative return for periods greater than a day."

**최근 1년 변경**
- 분할·병합: SOXL은 없습니다. Direxion의 2026-02-04, 2026-06-10 분할 공지 대상에 SOXL이 없고, 병합된 것은 SOXS입니다(1대10, 07-15부터 조정 거래) [S8].
- 분배금: 기준일 2026-09-22, 지급 09-29, 주당 0.09290달러. 그 전은 2025-09-23의 0.01008달러이고 사이에는 기록이 없습니다 [S1].
- 지수 변경: 최근 1년에는 없습니다. 마지막 교체는 2021-08-25경(PHLX → ICE Semiconductor) [S9].

**한국 투자자 보유**
- 보관금액 약 64.7억 달러, 해외주식 4위(테슬라·엔비디아·알파벳 다음). 예탁결제원 2026-08-26 기준 [S10].
- 기사는 시가총액 약 210억 달러로 나눠 약 30.8%로 계산했습니다. 시가총액의 출처는 기사에 없습니다 [S10].
- 한국은행 2025-03 보고서 당시 비중은 22.2%였습니다(같은 기사 인용) [S10].
- 최근 한 달(09-07~10-06) SOXL 매수 규모 약 30억 달러로 1위(순매수 아님). 미국주식 보관액 2,002억 달러(10-05) [S11].
- 09-17~23 주간에는 SOXL 순매도 8.17억 달러 [S12].

### 2. QQQ

| 항목 | 값 | 기준일 | 출처 |
|---|---|---|---|
| 지수 | Nasdaq-100 | — | [Q1] |
| 구조 변경 | 단위투자신탁(UIT) → 개방형 ETF, 주주 승인 | 보도자료 2025-12-19, 개방형 거래 2025-12-22 | [Q2] |
| 총보수 | 0.20% → 0.18% | 2025-12-22부터 | [Q2] |
| 순자산 | 5,079.5억 달러 (2차 자료) | 2026-10-06 | [Q3] |
| 최근 분배 | 분배락 2026-09-21 (분기, 2차 자료) | — | [Q4] |

**상위 10 (2026-10-08, Schwab [Q5], TradingView [Q6]과 일치, 2차 자료)**
- 엔비디아 8.32 · 애플 7.45 · 마이크로소프트 5.82 · 마이크론 4.84 · AMD 4.19
- 아마존 4.11 · 메타 3.21 · 알파벳A 3.06 · 테슬라 2.95 · 알파벳C 2.86 (%)
- 합계 46.81%. 알파벳 A+C는 5.92%.
- 브로드컴은 상위 10 밖입니다. 2.52%(09-24, 13위) [Q7], 2.79%(08-31) [Q3].
- 스페이스X(SPCX) 2.65%(09-24, 12위) [Q7].

**섹터 (2026-09-24, GICS, 2차 자료 [Q7])**
- 정보기술 59.1 · 통신서비스 15.2 · 임의소비재 10.2 · 필수소비재 5.4 · 헬스케어 3.7 · 산업재 3.0 (%)
- Invesco는 ICB 분류를 쓰므로 공식 수치와 다를 수 있습니다.

**지수 정기 변경 (방법론 [N1])**
- 연례 재구성: 기준일은 11월 마지막 거래일, 공지는 발효 6거래일 전 장 마감 뒤, 발효는 12월 셋째 금요일 다음 거래일 개장.
- 규칙대로 계산하면 2026년은 기준 11-30, 공지 12-11, 발효 12-21입니다. 나스닥이 날짜를 공지한 것은 아니고 제가 계산한 값입니다.
- 분기 리밸런싱: 3·6·9·12월 셋째 금요일 다음 거래일. 6월은 06-22 발효로 확인했습니다(06-11 공지) [N2].
- 2026-05-01 규칙 개정 [N3][N4]:
  - 빠른 편입: 시총 상위 40위권 신규 상장은 15거래일 뒤 편입, 종목 수가 100을 넘을 수 있음.
  - 유통주식 3배 상한.
  - 분기마다 125위 밖 종목 제외.
- 특별 리밸런싱은 다음 중 하나면 발동될 수 있습니다 [N1]:
  - 한 회사가 24% 초과.
  - 4.5%를 넘는 회사들의 합이 48% 초과.
- 정기 조정 때는 24% 초과 회사를 20%로, 합 48% 이상을 40%로 낮춥니다. 12월에는 종목 단위 규칙(15% 초과 → 14%, 상위 5개 합 40% 이상 → 38.5%)도 적용합니다 [N1].

**2026년 편출입**
- 스페이스X 편입 07-07 (06-26 공지, 빠른 편입) [N5].
- 모더나 편입, 워너브러더스 디스커버리 제외 10-09 (나스닥 10-01 발표) [N6].

### 3. TQQQ

| 항목 | 값 | 기준일 | 출처 |
|---|---|---|---|
| 목표 | "three times (3x) the daily performance" of the Nasdaq-100 | 설명서 2026-09-28 | [T1] |
| 총보수 | 총 0.94% / 순 0.78% (일부 데이터 사이트는 아직 0.82%) | 2026-09-28 | [T1] |
| 순자산 | 400.8억~407.0억 달러 (2차 자료) | 2026-10-09경 | [T2][T3] |
| 분할 | 1주를 2주로, 2025-11-20 개장 전 발효 | 발표 2025-11-04 | [T4] |
| 하루 넘김 문구 | "The performance of the Fund for periods longer than a single day will likely differ from the Daily Target." | 2026-09-28 | [T1] |

### 4. 겹침

| 종목 | QQQ 비중 (2026-10-08 [Q5]) | SOXL 기초 지수 비중 |
|---|---|---|
| 엔비디아 | 8.32% | 6.82% (2026-06-30 [S3]) / 7.48% (10-07, SOXX 근사 [S6]) |
| 테슬라 | 2.95% | 해당 없음 |
| 알파벳 A+C | 5.92% | 해당 없음 |

기준일은 맞추지 못했습니다. 운용사가 공개한 지수 비중이 06-30이 최신입니다.

### 5. 2026-10-10 ~ 11-10 예정

- 세 상품 모두 이 기간에 공지된 분배·분할·지수 정기 변경을 찾지 못했습니다.
- 분배는 셋 다 9월 하순에 끝났습니다. TQQQ 분배락은 09-23 [T2].
- 나스닥100의 다음 정기 일정은 12월입니다. 빠른 편입과 수시 교체는 예고 없이 나올 수 있습니다(10-09 모더나가 그 예).

### 확인하지 못한 것

- SOXL 순자산의 운용사 공식 수치(상품 페이지에 없음).
- NYSE Semiconductor Index의 현행 상한 규칙과 2026-09 재구성 결과(편출입, 재구성 뒤 비중).
- 지수 이름이 ICE에서 NYSE Semiconductor로 바뀐 날짜와 펀드 이름이 "Shares"에서 "ETF"로 바뀐 날짜.
- QQQ의 Invesco 공식 보유 비중·섹터·순자산과 12월 분배 일정.
- 나스닥100의 2026-09 분기 리뷰 결과 공지문과 12월 재구성 날짜의 공식 공지.
- 한국인 SOXL 보유 비중의 9~10월 수치. 30.8%는 기사의 계산이며 순자산 기준이 아닙니다.
- 한국인 보유분이 QQQ·TQQQ 순자산에서 차지하는 비중.

### 출처

- [S1] https://www.direxion.com/product/daily-semiconductor-bull-bear-3x-etfs
- [S2] https://www.sec.gov/Archives/edgar/data/1424958/000119312526078540/d50601d497k.htm
- [S3] https://www.direxion.com/uploads/SOXL-SOXS-Fact-Sheet.pdf
- [S4] https://www.etfcentral.com/fund/SOXL
- [S5] https://stockanalysis.com/etf/soxl/holdings/
- [S6] https://stockanalysis.com/etf/soxx/holdings/
- [S7] https://www.sec.gov/Archives/edgar/data/1100663/000119312521126827/d82642d497.htm
- [S8] https://www.direxion.com/press-release/direxion-to-split-nine-etfs
- [S9] https://www.direxion.com/uploads/Direxion-Changes-Index-for-Semiconductor-ETFs.pdf
- [S10] https://www.heraldk.com/article/2026082719291461574
- [S11] https://www.ebn.co.kr/news/articleView.html?idxno=1726984
- [S12] https://www.mt.co.kr/world/2026/09/28/2026092718122290284
- [Q1] https://invesco.com/qqq-etf/en/about.html
- [Q2] https://www.invesco.com/hk/en/investment-ideas/press-and-media/2025/invesco-qqq-shareholders-vote-to-approve-modernization.html
- [Q3] https://www.etfcentral.com/fund/QQQ
- [Q4] https://chartrow.com/quote/qqq/dividends
- [Q5] https://www.schwab.wallst.com/Prospect/Research/etfs/portfolio.asp?symbol=qqq
- [Q6] https://www.tradingview.com/symbols/BOATS-QQQ/holdings
- [Q7] https://portfolio-terminal.com/etf/qqq/holdings
- [N1] https://indexes.nasdaqomx.com/docs/Methodology_NDX.pdf
- [N2] https://www.stocktitan.net/articles/nasdaq-100-sp-500-rebalance-june-2026
- [N3] https://indexes.nasdaqomx.com/docs/2026_NDX_Changes_FAQ.pdf
- [N4] https://indexes.nasdaqomx.com/docs/Methodology_Change_Log_NDX.pdf
- [N5] https://www.fastcompany.com/91566621/spacex-stock-nasdaq-100-timeline-date-impact-qqq-401k
- [N6] https://ir.nasdaq.com/node/111076
- [T1] https://www.sec.gov/Archives/edgar/data/0001174610/000117461026001035/f46111d1.htm
- [T2] https://stockanalysis.com/etf/tqqq/
- [T3] https://etfdb.com/etf/TQQQ/
- [T4] https://www.proshares.com/press-releases/proshares-announces-etf-share-splits5
