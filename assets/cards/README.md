# 카드 틀 — 코드가 그리는 1080×1350 이미지

상태: **D35(2026-10-10)로 정했다 — 스레드 글에 한 장부터.** 첫 장은 10/19(월) 미국장 시간표. 근거는 `docs/16_expression_formats.md` §3, 진행은 `plan/status.md` 1-6.

## 무엇이 있나
| 파일 | 내용 |
|---|---|
| `card.css` | 틀. 색과 글꼴은 `assets/brand/README.md` 그대로 |
| `render.py` | 설계 파일(JSON) → PNG. 찍기 전에 글자를 검사하고(금지어 · 쓰지 않는 말 · 주소 · 채우지 않은 칸), 찍은 뒤에 넘침을 본다 |
| `specs/*.json` | 카드 설계 파일. 글과 숫자가 여기에 있다. `memo`에 짝이 되는 초안과 숫자의 출처를 적는다 |
| `samples/*.png` | 설계 파일로 찍은 그림(시안 17장) |

## 만드는 법
```
cd assets/cards && npm install @fontsource/gothic-a1 @fontsource/plus-jakarta-sans   # 한 번만. 둘 다 SIL Open Font License
python assets/cards/render.py assets/cards/specs/us_market_hours.json            # samples/ 에 PNG
python assets/cards/render.py assets/cards/specs/us_market_hours.json --jpeg     # 인스타 API 는 JPEG 만 받는다
python assets/cards/render.py assets/cards/specs/us_market_hours.json --check    # 글자 검사만
```
브라우저(Playwright의 Chromium)가 있어야 한다. 서버(EC2)에는 없다 — 지금은 세션이 만들어 올린다.

## 설계 파일의 모양
```json
{"id": "week-1012", "kicker": "이번 주 체크", "memo": "짝이 되는 글과 숫자의 출처",
 "slides": [{"type": "agenda", "title": ["첫 줄", "*형광펜* 줄."], "items": [...], "note": "주석"}]}
```
- 카드 종류(`type`): `cover` 표지 / `shift` 바뀌기 전과 후 / `figs` 숫자 줄 / `ord` 번호가 붙은 설명 / `text` 글 / `sheet` 한 장 정리 표 / `agenda` 일정 / `end` 마지막 장(고지)
- 글 안의 표시: `*…*` 형광펜(제목) 또는 짙은 초록(본문), `**…**` 굵게, 줄바꿈은 `\n`. 제목이 마침표로 끝나면 로고의 둥근 점으로 그린다
- 바탕(`theme`): 표지는 초록, 나머지는 옅은 초록이 기본. `"white"`를 주면 흰 바탕
- 한 장짜리 설계 파일에는 쪽 번호가 붙지 않는다(스레드 글에 붙이는 용도)
- 발의 고지는 기본이 "원금 손실 가능 · 개별 상담 불가"다. 신고 뒤에는 설계 파일의 `legal_short`로 바꾼다(docs/16 §3)

## 지킬 것
- 글자와 숫자만. 사진, 가격 차트, 상승 화살표, 얼굴은 틀에 없다(D26, D12, D15)
- 숫자는 짝이 되는 글과 데이터 파일에서 옮긴다. 카드에서 새로 계산하지 않는다
- 이미지는 본문 없이 돌아다닌다. 계산 조건과 "과거 데이터로 계산한 결과"라는 말은 카드의 주석에 넣는다
- 카드 속 문장도 `templates/copy_guide.md` 문체다(D31)
- 백테스트 숫자가 든 카드(`sell_early`)는 틀을 보이려는 시안이다. 올릴지는 Nick이 정한다(docs/16 §3)
