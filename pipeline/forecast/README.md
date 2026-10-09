# 엔진 예측 (forecast) v0

미국 경제지표의 발표값을 발표 전에 장부에 봉인하고, 발표 뒤에 채점한다. 설계와 규칙은 `docs/12_forecast_engines.md`, 결정은 D18.
지금은 비공개 봉인 단계다. 예측 값은 발행물에 싣지 않는다.

## 명령

```
python -m pipeline.forecast.selftest                      이 PC에서 제대로 도는지 확인(임시 폴더, 실제 장부는 건드리지 않음)
python -m pipeline.forecast.engine register …            엔진 등록의 원래 명령. 보통은 아래 runner register 를 쓴다(모델·횟수를 레시피에서 읽는다)
python -m pipeline.forecast.engine list
python -m pipeline.collect.bls                            지표 수집. 서버의 예약 작업 일꾼이 돌린다 (docs/13 §8)
python -m pipeline.forecast.bundle --event CPI --ref 2026-09   두 엔진에 줄 사실 묶음 만들기
python -m pipeline.forecast.runner check                  레시피 폴더 검사 (호출 없음)
python -m pipeline.forecast.runner probe                  레시피의 모델을 짧게 한 번씩 불러 본다 (키·모델·잔액 확인)
python -m pipeline.forecast.runner render --event CPI --ref 2026-09    엔진에 줄 사실 표를 화면에 (호출 없음)
python -m pipeline.forecast.runner preview --event CPI --ref 2026-09   미리 보기: 엔진마다 한 번 불러 형식만 본다. 답은 저장도 표시도 하지 않는다
python -m pipeline.forecast.runner register --name adler --label 아들러 --version 1   레시피의 모델·횟수 그대로 장부에 등록
python -m pipeline.forecast.runner run --event CPI --ref 2026-09       실제 실행: 묶음 → 엔진 호출 → 합치기 → 봉인 (여러 번 돌려도 받은 답은 다시 받지 않는다)
python -m pipeline.forecast.seal --file <예측파일.json>     발표 12시간 전까지. --dry-run 으로 미리 보기 (실행기가 부른다. 손으로 돌릴 일은 없다)
python -m pipeline.forecast.score                         처음 발표값으로 채점
python scripts/forecast_schedule.py                       발표 일정표 다시 만들기 (Windows는 pip install tzdata 필요)
python scripts/engine_cost.py                             비용 어림
```

## 파일

| 위치 | 내용 | 공개 |
|---|---|---|
| `pipeline/forecast/targets.py` | 대상 지표 목록, 구간 비율(80%), 표본 기준(발표 30회) | — |
| `data/private/engines/<이름>/v<버전>/` | 레시피(프롬프트·설정). 비공개 로직 | 비공개. 해시만 장부에 |
| `data/ledger/public/ledger.jsonl` | `engine`·`forecast` 기록이 주간 신호 기록과 같은 장부에 이어진다. 해시·발표 종류·엔진 목록만 | 공개 가능 |
| `data/private/ledger/NNNNNN_forecast_*.json` | 예측 원문(값)과 nonce | 발표 뒤 공개 가능. 지금은 내부 |
| `data/private/forecast/bundles/` | 사실 묶음(엔진 입력). 무엇을 골라 주는지가 노하우 | 비공개 |
| `data/private/forecast/runs/<발표>_<기간>/` | 실행기의 작업 폴더: 그 발표에 쓴 엔진 목록(plan.json), 사실 묶음(bundle.json), 받은 답 하나씩(`<엔진@버전>/runNN_ansMM.json`), 오지 않은 호출의 기록(errors.jsonl), 봉인에 넣은 예측 파일 | 비공개. 발표 전 답이 들어 있다 |
| `data/forecast/schedule_2026Q4.csv` | 발표 일정(미 동부·한국 시간·UTC) | 공공 일정 |
| `data/forecast/actuals.csv` | 발표값. 한 줄 = 한 값, 수정치는 줄을 덧붙인다 | 공공 통계 |
| `data/private/forecast/scores.csv` | 채점 결과 | 공개 형태 결정 전까지 내부 |

## 예측 파일 형식 (엔진 실행기 `runner.py` 가 만든다)

```json
{
  "event": {"kind": "CPI", "ref_period": "2026-09", "release_at_utc": "2026-10-14T12:30:00Z"},
  "data_cutoff_utc": "2026-10-12T12:00:00Z",
  "bundle_sha256": "<두 엔진에 준 사실 묶음 파일의 sha256>",
  "bundle_spec": "CPI/0.1",
  "forecasts": [
    {"engine": "adler", "version": "1", "target": "CPI_MOM", "p10": 0.2, "p50": 0.3, "p90": 0.4, "n_runs": 5},
    {"engine": "fletcher", "version": "1", "target": "CPI_MOM", "p10": 0.2, "p50": 0.35, "p90": 0.5, "n_runs": 5},
    {"engine": "prev", "target": "CPI_MOM", "p50": 0.4}
  ]
}
```

`prev`는 기준선(직전 발표값 그대로)이며 지표마다 반드시 들어간다. 위 숫자는 형식을 보이기 위한 예시다.
실행기가 만든 파일에는 엔진의 값마다 번별 답(`runs`)이 붙고, 맨 바깥에 실행 기록(`execution`: 보낸 글의 해시, 응답한 모델, 맞는 답의 수, 토큰 수)이 붙는다. 둘 다 비공개 원문에만 남는다.

## 레시피 폴더 (`data/private/engines/<이름>/v<버전>/`)

| 파일 | 내용 |
|---|---|
| `recipe.json` | 설정. 항목을 모두 적는다(기본값 없음): `format`(recipe/1) · `provider`(anthropic / openai) · `model` · `n_runs` · `min_valid_runs` · `max_attempts` · `timeout_sec` · `render`(table/1) · `answer`(json/1) · `aggregate`(median) · `request`(그 회사 API의 요청 항목) |
| `prompt.md` | 사용자 메시지 틀. `{{FACTS}}` 자리에 사실 표, `{{ANSWER_FORMAT}}` 자리에 답 형식이 들어간다 |
| `system.md` | 시스템 지시문 (없어도 된다) |

- `request`에는 정해 둔 항목만 넣을 수 있다. anthropic: `max_tokens`(필수) `thinking` `output_config` `temperature` `top_p` `top_k` `stop_sequences` `service_tier` / openai: `max_output_tokens` `reasoning` `text` `temperature` `top_p` `service_tier`. 도구·웹 검색·이어 붙이기는 넣을 수 없다.
- `timeout_sec`은 한 번 부르는 데 기다리는 시간이다. 서버의 예약 작업은 한 번에 10분을 넘지 못하므로 300 안팎으로 잡는다. 실제로 걸리는 시간은 미리 보기가 알려 준다.
- 사실 표(`table/1`)·답 형식(`json/1`)·합치기(`median`)는 코드에 있고 자체 시험이 지킨다. 고칠 때는 새 번호를 더하고 엔진을 새 버전으로 등록한다.
- 등록하기 전에 `check` → `preview`로 본다. 등록한 뒤에는 폴더의 어떤 파일도 고칠 수 없다(고치면 그 엔진은 불리지 않는다).

## 규칙 (코드가 막는 것)

- 발표 12시간 전 마감을 넘긴 봉인, 발표 뒤 봉인 (`--min-lead-hours`로 마감을 당길 수는 있어도 12시간보다 늦출 수는 없다)
- 등록되지 않은 엔진·버전, 등록 뒤 레시피 폴더가 바뀐 엔진 → 바꾸려면 새 버전으로 등록
- 같은 발표·같은 엔진·같은 지표의 두 번째 봉인
- 기준선이 빠진 지표, p10 <= p50 <= p90 이 아닌 값, 발표 자릿수보다 두 자리 이상 잘게 쓴 값
- 엔진 이름에 모델 회사·모델 이름
- 빈 장부에 엔진 등록 (기점 기록이 먼저 있어야 한다)

엔진이 낸 값은 사람이 고치지 않는다. 놓친 발표는 뒤늦게 채우지 않는다.

실행기가 더 막는 것 (`runner.py` 머리말)
- 엔진이 낸 값과 답의 글을 화면·로그·조종판에 찍는 것 (건수·해시·토큰 수·상태만 찍는다)
- 형식이 맞는 답을 받은 번을 다시 부르는 것. 다시 받는 것은 형식이 틀린 답뿐이고 `max_attempts`까지다. API·통신 오류는 답이 아니므로 세지 않고, 마감 한 시간 전까지 실행할 때마다 다시 부른다
- 답의 끝이 아닌 곳에 적힌 초안을 답으로 읽는 것 (글의 마지막 `}`로 끝나는 `{"forecasts": …}` 하나만 읽는다)
- 형식이 맞는 답이 `min_valid_runs`에 못 미친 엔진의 제출 ("미제출")
- 첫 답을 받은 뒤에 사실 묶음이나 엔진 목록을 바꾸는 것, 등록 뒤 레시피가 바뀐 엔진을 부르는 것
- 같은 발표를 두 실행이 함께 다루는 것 (작업 폴더 잠금)

답이 다 모인 엔진은 다른 엔진을 기다리지 않고 바로 봉인한다. 그래서 한 발표의 예측 기록이 엔진마다 한 건씩, 두 건이 될 수 있다(같은 묶음·같은 기준선).

## 아직 없는 것

- 경제분석국·에너지정보청·노동부 수집기 (노동통계국은 `pipeline/collect/`에 있음)
- 레시피 v1 — 실행기(`runner.py`)는 있다(10/9). 실제 API로는 아직 불러 보지 않았다: 서버에서 `probe`와 `preview`가 첫 시험이다
- 서버의 예약 작업(발표 전날 `run`을 되풀이해 부르는 줄) — `pipeline/console/jobs.py`에 더한다
- 도전자 버전을 현 버전과 함께 돌리는 것 — 지금은 이름마다 가장 높은 버전만 고른다(`run --engines`로 직접 줄 수는 있다)
- 시장 예상치 내부 기록의 봉인 (docs/12 §6)
- 발표 뒤 원문 공개(`reveal`)와 DB 표(`forecast`, `forecast_score`)로 옮겨 싣기
- 다음 날 자동 채점
