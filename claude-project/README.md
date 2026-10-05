# Claude 프로젝트 셋업

## 1. 프로젝트 생성
- 이름: `Checksum` (서비스명, D8)
- 지침(시스템 프롬프트): `PROJECT_PROMPT.md` 전체를 붙여넣기

## 2. 프로젝트 지식 업로드 (요약본 — 폴더 docs/가 원본)
1. `00_context_brief.md` — 1장 요약 (필수)
2. `../docs/01_market_research.md` — 한국·일본 시장 조사 원문
3. `../docs/03_regulation_checklist.md` — 규제 체크리스트
4. `../docs/05_marketing_strategy.md` — 마케팅 전략
5. `../plan/decisions.md` — 결정 기록 (폴더 연결이 안 된 대화용 백업)

02 사업계획과 04 수익모델은 00에 요약돼 있고 폴더에서 읽으면 되므로 생략 가능. 지식이 많을수록 매 대화 컨텍스트가 무거워지니 5개 이내 유지.

## 3. 파일시스템 연결
- Claude 데스크톱 앱 → 이 프로젝트의 대화에서 "+" → Add folder → `C:\usstock-sub`
- 연결 후 첫 메시지 예: "plan/decisions.md와 roadmap을 읽고 이번 주 할 일 정리해줘. 그리고 서비스명 후보 10개 뽑자"

## 4. 유지 규칙
- `docs/`나 `plan/decisions.md`가 크게 바뀌면 `00_context_brief.md`를 갱신하고 프로젝트 지식에 재업로드
- 프로젝트 지침은 단계가 바뀔 때만 수정 (현재: "네이밍부터 시작" → 네이밍 끝나면 해당 문단을 다음 단계로 교체)
