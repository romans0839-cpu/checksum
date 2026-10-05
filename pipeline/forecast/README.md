# 엔진 예측 (forecast) v0

미국 경제지표의 발표값을 발표 전에 장부에 봉인하고, 발표 뒤에 채점한다. 설계와 규칙은 `docs/12_forecast_engines.md`, 결정은 D18.
지금은 비공개 봉인 단계다. 예측 값은 발행물에 싣지 않는다.

## 명령

```
python -m pipeline.forecast.selftest                      이 PC에서 제대로 도는지 확인(임시 폴더, 실제 장부는 건드리지 않음)
python -m pipeline.forecast.engine register --name adler --label 아들러 --version 1 --model <모델ID> --n-runs 5 --dir data/private/engines/adler/v1
python -m pipeline.forecast.engine list
python -m pipeline.collect.bls                            지표 수집. 서버의 예약 작업 일꾼이 돌린다 (docs/13 §8)
python -m pipeline.forecast.bundle --event CPI --ref 2026-09   두 엔진에 줄 사실 묶음 만들기
python -m pipeline.forecast.seal --file <예측파일.json>     발표 12시간 전까지. --dry-run 으로 미리 보기
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
| `data/forecast/schedule_2026Q4.csv` | 발표 일정(미 동부·한국 시간·UTC) | 공공 일정 |
| `data/forecast/actuals.csv` | 발표값. 한 줄 = 한 값, 수정치는 줄을 덧붙인다 | 공공 통계 |
| `data/private/forecast/scores.csv` | 채점 결과 | 공개 형태 결정 전까지 내부 |

## 예측 파일 형식 (엔진 실행기가 만든다)

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

## 규칙 (코드가 막는 것)

- 발표 12시간 전 마감을 넘긴 봉인, 발표 뒤 봉인
- 등록되지 않은 엔진·버전, 등록 뒤 레시피 폴더가 바뀐 엔진 → 바꾸려면 새 버전으로 등록
- 같은 발표·같은 엔진·같은 지표의 두 번째 봉인
- 기준선이 빠진 지표, p10 <= p50 <= p90 이 아닌 값, 발표 자릿수보다 두 자리 이상 잘게 쓴 값
- 엔진 이름에 모델 회사·모델 이름
- 빈 장부에 엔진 등록 (기점 기록이 먼저 있어야 한다)

엔진이 낸 값은 사람이 고치지 않는다. 놓친 발표는 뒤늦게 채우지 않는다.

## 아직 없는 것

- 경제분석국·에너지정보청·노동부 수집기 (노동통계국은 `pipeline/collect/`에 있음)
- 엔진 실행기(API 호출)와 레시피 v1 — 키가 준비되면 만들고 실제 호출로 시험한다
- 시장 예상치 내부 기록의 봉인 (docs/12 §6)
- 발표 뒤 원문 공개(`reveal`)와 DB 표(`forecast`, `forecast_score`)로 옮겨 싣기
- EC2 자동 실행(발표 전날 봉인, 다음 날 채점)
