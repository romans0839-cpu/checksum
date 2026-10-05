# 데이터 라이선스 — 현황, 대안, 문의 메일 초안 (2026-10-05)

상태: 조사 완료, 견적 전. 결정 기한 **10/16**(창간 10/20 전). 이 문서는 조사 기반 정리이며 법률 자문이 아니다.

> **2026-10-06 방향 변경 (D26, Nick 결정).** 문의는 보내되 **가입자라고 밝히지 않고** 일반 문의로 보낸다(§4 초안을 그렇게 고쳤다). 답을 기다리지 않고, **벤더 데이터에서 나온 파생 수치(상태·순위·분포·통계)와 신호 종목명은 발행하는 방향**으로 간다. 답변을 본 뒤 따로 판단하며, 그때 바꿀 수 있다.
> 그대로인 것: 원시 가격표·가격 차트·데이터 파일이나 내보내기는 싣지 않는다(처음부터 계획에 없다). 아래 §0~§3의 조사 내용(약관이 무엇을 요구하는가)은 사실 기록으로 그대로 둔다 — 바뀐 것은 약관이 아니라 우리의 방향이다.
> 남는 위험(Nick이 알고 정함): 약관과 어긋난다고 벤더가 판단하면 계정이 해지될 수 있고, 라이브 봇이 같은 데이터(Norgate)로 돈다. 답변이 "불가"이거나 계정에 영향이 오면 즉시 해당 수치를 내리고 소스 교체를 정한다. 그래서 벤더 유래 사실에는 DB에서 출처(`vendor_px`) 표시를 남겨, 어느 발행물의 어느 문장이 해당하는지 바로 찾을 수 있게 한다.
> 라이선스와 별개로 남는 확인: 백테스트 수치의 게재 범위, 무료 지연 공개가 추천에 해당하는지(변호사), 신고 전후의 표현 규칙(docs/03).

## 0. 결론

1. **어느 벤더든 "다른 사람이 보게 되는 순간" 상업·표시 계약이 필요하다.** 원시 가격이 아니라 파생 지표(30주선 위/아래, 순위, 등락률)만 실어도 마찬가지다. 무료 발행물도 포함된다.
2. **표시 권한이 포함된 가격은 전부 문의제다.** 공개된 숫자로 본 범위는 월 $399(시작가)~$2,499. 환율 1,400원 가정 시 약 56만~350만원으로, D5의 도구비 상한(월 5~7만원)과 고정비 가정(25만원)을 넘는다 → 견적을 받은 뒤 별도 예산 항목으로 결정해야 한다.
3. **이번 주 할 일은 메일 4통**(§4). 답이 오기 전 창간호는 벤더 데이터에서 나온 수치 없이 구성한다(§3).

## 1. 지금 쓰는 소스의 조건

| 소스 | 용도 | 약관상 조건 | 판단 |
|---|---|---|---|
| Norgate | 라이브 신호·백테스트 (2027-02 만료 예정) | 개인·비상업 용도 한정. 원자료 제공·배포·출판 금지. 백테스트 결과·통계·매매 규칙 같은 파생물 보유는 허용. 제한적 발췌 출판은 사전 허가 필요 | 유료 서비스에 쓰는 것 자체가 비상업 조건과 충돌할 수 있다. 문의 필요 |
| FMP | 이관 예정 소스(12월 목표), 실적 일정 | 개인 요금제(월 $22~149)는 발행 권리 없음. 차트·표·파생 지표를 유·무료 발행물에 싣려면 Data Display and Licensing Agreement 필요. 가격은 문의 | 이관 계획과 맞으므로 1순위 문의 대상 |
| Sharadar | 실적 발표일 연구 | 미확인 | 발행물에 쓰기 전 확인 |

## 2. 대안 비교

| 벤더 | 개인 요금 | 타인에게 표시할 때 | 공개된 상업 가격 |
|---|---|---|---|
| FMP | 월 $22~149 (연 결제) | 별도 표시·라이선스 계약 | 문의 |
| Massive (구 Polygon.io) | 월 $29~199 | Business 구독 필수. 테스터·동료가 보는 것도 해당. 파생 값 표시도 Business 범위 | 문의 |
| EODHD | — | 개인 요금제는 원본·재가공 형태 모두 표시 금지. Internal 요금제(월 $399)도 외부 표시 불가 | Custom 월 $399부터(견적), Enterprise 월 $2,499 |
| Tiingo | 개인 $30 / 상업 $50 | 두 요금제 모두 내부 사용만. 표시·재배포는 별도 라이선스 | 문의 |

참고: 일반 가이드는 고객 대상 표시 라이선스를 월 $2,000~25,000로 잡지만, 실시간 시세를 앱에 보여 주는 경우 기준이다. 우리는 종가 기반·파생 지표·주간 발행이라 범위를 좁혀 협상할 여지가 있다.

비용이 손익에 주는 영향(순수익 식 기준, 유료 1인당 25,560원): 월 56만원이면 유료 약 27명분, 350만원이면 약 168명분이 라이선스에 들어간다.

## 3. 비용과 위험을 줄이는 설계

- **범위를 좁혀 문의한다**: 종가(EOD)만, 파생 판정만(원시 가격표·차트 없음), 다운로드·API 제공 없음, 주간 발행. 메일 초안에 반영했다.
- **소스를 하나로**: 신호·본편·3줄을 같은 계약 소스에서 만든다. 봇의 FMP 이관(12월)과 일정이 맞는다.
- **확정 전 창간호 구성**: 글로벌 체크(금리·세계 경제 — 연준·재무부 등 공공 1차 출처), 일정 체크, 서비스 소개, 리딩방 수익률 캡처 읽는 법. 가격 데이터 벤더가 필요 없다(docs/09 §5-3).
- **고정관념 체크**는 Norgate 데이터로 만든 백테스트 통계다. 약관이 보유를 허용한 파생물이지만 상업적 게재는 별개 문제라 Norgate 메일에서 명시적으로 묻는다. 답을 받기 전에는 수치를 싣지 않는다.
- 공공 출처로 대체 가능한 것: 실적·공시 원문(SEC EDGAR), 서학개미 보관 상위 종목(예탁결제원 세이브로 — 이용 조건 확인 필요).

## 4. 메일 초안 (10/6 고침 — 가입자라고 밝히지 않는 일반 문의, D26)

`[ ]` 부분만 채워 보내면 된다. 발신은 hello@checksumlab.com. 기존 계정의 요금제·가입 메일은 적지 않는다. 사실과 다른 말은 쓰지 않는다 — 밝히지 않을 뿐이다. 계정을 물으면 그때 답한다.
4통이 부담이면 4-1(Norgate)과 4-2(FMP)만 보낸다. 봇이 지금 쓰는 곳과 옮겨 갈 곳이다.

### 4-1. Norgate (support@norgatedata.com — 주소는 사이트에서 확인)

Subject: Licensing inquiry — publishing derived analysis in a subscription newsletter

Hello,

I am preparing to launch a Korean-language investment newsletter (free and paid tiers, operated by a sole proprietor in South Korea). I would like to know whether Norgate Data offers a license that covers the use below, and what it costs.

What the newsletter would publish:
1. Weekly output of a rule-based system computed from end-of-day data: ticker symbols of entry candidates and exits. No raw prices or volumes.
2. Derived status indicators per stock and per industry group: above/below the 30-week moving average, relative-strength rank of industry groups, rank of 13-week return within a group.
3. Aggregate backtest statistics in educational articles (for example, "exit rule A vs. exit rule B over 1994–2018").

What it would not do: distribute data files, price tables, charts of price series, or any export or API access.

Audience: starting from zero; a few thousand free readers and a few hundred paying subscribers expected within the first year.

Questions:
- Is there a license that permits items 1–3, and what does it cost?
- Is attribution required, and in what form?

Thank you,
Checksum (checksumlab.com)

### 4-2. FMP (문의 양식 — 발행 권리 안내 글이 요구하는 항목 순서)

Subject: Data Display and Licensing Agreement inquiry — newsletter with derived end-of-day indicators

Hello,

I would like to request terms for a Data Display and Licensing Agreement.

Use case: a Korean-language investment newsletter with free and paid tiers, operated by a sole proprietor in South Korea.

Audience size and type: retail investors in Korea. Zero today; a few thousand free readers and a few hundred paying subscribers expected in year one.

Datasets and endpoints: end-of-day historical prices for US equities and ETFs (Russell 1000 constituents plus about 50 widely held names), index constituents, earnings calendar. No real-time or intraday data. No fundamentals at launch.

What is displayed:
- Derived indicators only: above/below 30-week moving average, industry-group relative-strength ranks, volatility buckets, weekly entry/exit candidates of a rule-based system.
- A three-line daily market summary with index and sector percentage changes.
- Later (2027): one public status page per ticker showing the same derived indicators.

Publication frequency: a short email on weekdays, two fuller issues per week.

Download/export: none. No data files, no price tables, no API pass-through.

Questions:
- What is the fee for this scope, and does it differ between the free and paid tiers or by audience size?
- Which attribution is required?

Thank you,
Checksum (checksumlab.com)

### 4-3. 견적 요청 (EODHD sales@eodhistoricaldata.com · Massive sales@massive.com)

Subject: Quote request — display license for derived end-of-day indicators in a newsletter

Hello,

I am preparing a Korean-language investment newsletter (free and paid tiers, sole proprietor in South Korea). I need a license that allows displaying derived indicators computed from US end-of-day equity and ETF prices to newsletter readers and, later, on public web pages.

Scope: end-of-day prices with history from 1993 including delisted tickers if available; index constituents; earnings dates. Displayed content is derived only (moving-average status, relative-strength ranks, percentage changes). No raw price tables, no downloads, no API pass-through. Audience: zero today, a few thousand readers within a year.

Could you tell me which plan covers this and the monthly cost?

Thank you,
Checksum (checksumlab.com)

## 5. 답변을 보고 판단할 때 볼 것 (기한을 두지 않는다 — D26. 답이 오는 대로)

- 표시 권한 포함 월 비용, 최소 계약 기간
- 1993년부터의 이력과 상폐 종목 포함 여부(고정관념 체크·기저율에 필요)
- 무료 발행물·공개 웹페이지까지 포함되는지
- 출처 표기 조건
- 봇 이관 일정(FMP 12월, Norgate 만료 2027-02)과 맞는지

## Sources

- Norgate 이용약관: https://norgatedata.com/subscribe/eula.php
- FMP 발행 권리: https://site.financialmodelingprep.com/ru/insights/platform/can-you-publish-fmpsourced-charts-tables-or-research-in-a-newsletter · 요금: https://site.financialmodelingprep.com/pricing-plans
- Massive 표시 조건: https://massive.com/knowledge-base/article/which-plan-do-i-need-to-show-massive-data-in-my-app · 요금: https://massive.com/pricing
- EODHD 약관: https://eodhd.com/financial-apis/terms-conditions · 상업 요금: https://eodhd.com/commercial-pricing
- Tiingo 요금: https://www.tiingo.com/about/pricing
- 라이선스 유형 일반 가이드: https://terms.law/Trading-Legal/guides/api-license-trading-data.html
