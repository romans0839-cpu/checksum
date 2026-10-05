"""시그널 트랙레코드 통계 — data/track_record/signals.csv 기반.

공개 통계 원칙 (docs/03 §4, decisions D3):
- 승률, 손익비, 기대값(R), 표본수, 최대 연속손실, 기간을 함께 공개
- 실계좌 금액·수익률은 다루지 않음. R배수(risk multiple)만 사용
실행: python -m pipeline.track_record.stats [--since 2026-10-06]
"""
import argparse
import csv
import json
from pathlib import Path
from statistics import mean

CSV = Path(__file__).resolve().parents[2] / "data" / "track_record" / "signals.csv"


def load(since: str | None):
    rows = [r for r in csv.DictReader(CSV.open(encoding="utf-8")) if r["outcome"] in ("win", "loss", "flat")]
    if since:
        rows = [r for r in rows if r["ts_signal"] >= since]
    return rows


def stats(rows):
    if not rows:
        return {"n": 0}
    r = [float(x["r_multiple"]) for x in rows]
    wins = [v for v in r if v > 0]
    losses = [-v for v in r if v < 0]
    streak = worst = 0
    for v in r:
        streak = streak + 1 if v <= 0 else 0
        worst = max(worst, streak)
    return {
        "n": len(r),
        "period": [min(x["ts_signal"] for x in rows), max(x["ts_signal"] for x in rows)],
        "win_rate": round(len(wins) / len(r), 3),
        "avg_win_R": round(mean(wins), 2) if wins else 0,
        "avg_loss_R": round(mean(losses), 2) if losses else 0,
        "payoff_ratio": round(mean(wins) / mean(losses), 2) if wins and losses else None,
        "expectancy_R": round(mean(r), 3),
        "max_consecutive_losses": worst,
        "slippage_included": True,
        "note": "시그널 단위 통계. 실계좌 수익률 아님. 과거 성과가 미래를 보장하지 않음.",
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=None)
    a = ap.parse_args()
    print(json.dumps(stats(load(a.since)), ensure_ascii=False, indent=2))
