"""두 엔진의 월 호출 비용 어림 (docs/12 §7). 가정이 바뀌면 여기 숫자를 고쳐 다시 돌린다.

    python scripts/engine_cost.py

요금(100만 토큰당 달러, 2026-10-05 확인):
  - Claude: 공식 요금표 https://platform.claude.com/docs/en/about-claude/pricing
  - GPT-6 Astra: 공식 요금표(https://openai.com/api/pricing/)에서는 확인하지 못했다. 아래 값은 제3자 집계 사이트의 숫자다
    (https://www.aipricing.guru/openai-pricing/). OpenAI 계정에서 실제 제공 여부와 요금을 확인한 뒤 고친다.
환율 1,400원은 docs/10 과 같은 가정이다.
"""
EVENTS_PER_MONTH = {"핵심만": 3.5, "핵심+보조": 9.2}        # scripts/forecast_schedule.py 가 센 값
N_RUNS = 5                                                  # 한 발표에 엔진을 몇 번 돌려 합치는가
TOKENS = {"가볍게": (6_000, 4_000), "넉넉히": (12_000, 16_000)}   # (입력, 출력·추론 포함) 1회 호출당
PRICES = {                                                  # (입력, 출력) 달러 / 100만 토큰
    "최상위 (Fable 5.1 · Astra*)": (10, 50),
    "상위 (Opus 5.5)": (4, 20),
    "중간 (Sonnet 5.5 · GPT-5.6 Terra는 출력 12)": (2, 10),
}
KRW = 1400


def main():
    print("가정: 발표 1회당 %d번 실행, 엔진 2개, 환율 %d원. 일괄 처리(batch)는 절반." % (N_RUNS, KRW))
    for scope, ev in EVENTS_PER_MONTH.items():
        print("\n[%s] 월 발표 %.1f회 → 엔진당 월 %d회 호출" % (scope, ev, round(ev * N_RUNS)))
        for tier, (pin, pout) in PRICES.items():
            cells = []
            for size, (tin, tout) in TOKENS.items():
                per_call = tin / 1e6 * pin + tout / 1e6 * pout
                month_usd = per_call * ev * N_RUNS * 2
                cells.append("%s $%.0f (약 %.1f만원, 일괄 %.1f만원)" % (size, month_usd, month_usd * KRW / 1e4, month_usd * KRW / 2e4))
            print("  %-40s %s" % (tier, " / ".join(cells)))
    print("\n* Astra 요금은 공식 요금표 미확인 값.")


if __name__ == "__main__":
    main()
