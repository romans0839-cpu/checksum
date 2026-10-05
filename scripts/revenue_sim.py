"""무료 뉴스레터 → 유료 전환 퍼널 기반 월별 MRR 시뮬레이션.

가정은 assumptions 딕셔너리에서 조정. 실행: python scripts/revenue_sim.py [--scenario base|bear|bull]
"""
import argparse
import json

SCENARIOS = {
    "bear": dict(free_growth=[300, 250, 250, 250, 250, 250, 250, 250, 250, 250, 250, 250],
                 conv_basic=0.02, conv_pro=0.006, churn=0.10),
    "base": dict(free_growth=[400, 400, 500, 500, 600, 600, 700, 700, 800, 800, 900, 900],
                 conv_basic=0.03, conv_pro=0.01, churn=0.08),
    "bull": dict(free_growth=[600, 700, 800, 1000, 1200, 1400, 1600, 1800, 2000, 2200, 2400, 2600],
                 conv_basic=0.04, conv_pro=0.015, churn=0.06),
}

COMMON = dict(
    price_basic=15_000,      # 월, 부가세 포함
    price_pro=59_000,
    platform_fee=0.104,      # 네이버 프리미엄콘텐츠 8% + PG 2.4%
    vat=0.10,                # 부가세 (매출에서 제외)
    paid_start_month=3,      # 무료 뉴스레터 시작 후 유료 오픈 (1=10월, 3=12월)
    pro_start_month=4,       # 프로 티어 오픈 (트랙레코드 12주 확보 후)
    fixed_cost=250_000,      # 월 고정비 (AWS, 데이터 API, 도구)
    months=12,
)
MONTH_LABELS = ["26-10", "26-11", "26-12", "27-01", "27-02", "27-03",
                "27-04", "27-05", "27-06", "27-07", "27-08", "27-09"]


def run(name):
    s = {**COMMON, **SCENARIOS[name]}
    free, basic, pro = 0, 0.0, 0.0
    rows = []
    for m in range(1, s["months"] + 1):
        new_free = s["free_growth"][m - 1]
        free += new_free
        # 유료 전환: 당월 유입 + 기존 무료 풀의 일부(1/6)가 매월 전환 검토
        pool = new_free + free / 6
        if m >= s["paid_start_month"]:
            basic = basic * (1 - s["churn"]) + pool * s["conv_basic"]
        if m >= s["pro_start_month"]:
            pro = pro * (1 - s["churn"]) + pool * s["conv_pro"]
        gross = basic * s["price_basic"] + pro * s["price_pro"]
        net = gross / (1 + s["vat"]) * (1 - s["platform_fee"]) - s["fixed_cost"]
        rows.append(dict(month=MONTH_LABELS[m - 1], free=free, basic=round(basic),
                         pro=round(pro), gross_mrr=round(gross), net=round(net)))
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="all")
    args = ap.parse_args()
    names = SCENARIOS if args.scenario == "all" else [args.scenario]
    for n in names:
        rows = run(n)
        print(f"\n[{n}]  month  free  basic  pro  gross_MRR  net_after_fee&fixed")
        for r in rows:
            print(f"  {r['month']}  {r['free']:>5}  {r['basic']:>5}  {r['pro']:>4}  "
                  f"{r['gross_mrr']:>10,}  {r['net']:>10,}")
        print(f"  12개월 누적 순수익: {sum(r['net'] for r in rows):,}원")
