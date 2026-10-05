# 장부 (ledger) v0

주간 신호를 결과가 나오기 전에 봉인해 두고, 나중에 원문을 공개했을 때 누구나 대조할 수 있게 하는 기록.

## 매주 화요일 (봇 신호 생성 뒤, 봇 집행 23:31 전)

`C:\usstock-sub\ledger_commit.bat` 더블클릭. 또는

```
cd C:\usstock-sub
python -m pipeline.ledger.commit
python -m pipeline.ledger.verify
```

정상이면 "기록 #N (이번 주 신호)"와 "이상 없음"이 나온다. 같은 주에 다시 실행해도 중복되지 않는다.
첫 실행 때는 기록 #1(기점 이전 보유 종목, 통계 제외)과 #2(그 주 신호)가 함께 생긴다.

## 파일

| 위치 | 내용 | 공개 |
|---|---|---|
| `data/ledger/public/ledger.jsonl` | 한 줄 = 한 기록. 해시·건수·시각만 | 공개 가능 |
| `data/ledger/public/seals/seal_*.txt` + `.ots` | 그 시점 마지막 해시 + 외부 타임스탬프 증명 | 공개 가능 |
| `data/private/ledger/*.json` | 원문(청산·진입 후보·보유 종목명)과 nonce | T+7 공개 전까지 비공개. 백업 필수 |
| `data/track_record/signals.csv` | 새 진입 후보 행(가격·결과는 체결 기준 확정 뒤 기입) | 내부 |

기록하지 않는 것: 수량, 계좌 금액, 가격, 지표 값.

## 주의

- `data/private/ledger/`를 잃으면 원문 공개(대조)를 할 수 없다. 주 1회 다른 곳에 복사해 둔다.
- 공개 장부는 고치지 않는다. 신호가 바뀌면 개정 기록이 뒤에 추가된다.
- 외부 타임스탬프(.ots)는 실패해도 기록은 남고, 다음 실행 때 다시 시도한다. 받은 .ots는 '대기' 상태이며
  `pip install opentimestamps-client` 후 `ots upgrade 파일.ots`로 완성한다. (v0에서는 실서버 수신 시험 전)

## 아직 없는 것 (v1, W2)

- T+7 원문 공개(`reveal`)와 웹 대조 화면
- 발행 시각·운영자 집행 시각 기록 (D11)
- 판정(업종·종목 상태·국면) 봉인과 13주 뒤 채점
- 공개 저장소로 내보내기
