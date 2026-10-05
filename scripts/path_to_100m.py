"""목표 경로 계산 — docs/09_service_moat_strategy.md §1 근거.

목표(D10): 3년 내 월 순수익 5,000만원, 5년 내 월 순수익 1억원.
순수익 정의는 scripts/revenue_sim.py 와 동일: 총매출 / 1.1(VAT) x (1 - 플랫폼 수수료 10.4%) - 고정비 25만원.
소득세·데이터 라이선스 비용은 반영하지 않음.
revenue_sim.py 의 구조(검토풀 = 당월 신규 무료 + 무료풀/6)를 그대로 쓰고 60개월로 연장.
13개월차 이후 무료 유입은 2개월마다 +100명씩 계속 증가한다고 가정(grow). 가정이지 예측이 아님.
실행: python scripts/path_to_100m.py
"""
Y1 = [400, 400, 500, 500, 600, 600, 700, 700, 800, 800, 900, 900]
FEE, VAT, FIXED = 0.104, 0.10, 250_000


def net_of(gross, fee=FEE):
    return gross / (1 + VAT) * (1 - fee) - FIXED


def gross_for_net(net, fee=FEE):
    return (net + FIXED) * (1 + VAT) / (1 - fee)


def run(growth, conv_b, conv_p, churn, pb=15_000, pp=59_000, months=60, paid_start=3, pro_start=4, fee=FEE):
    free = 0; b = 0.0; p = 0.0; out = []
    for m in range(1, months + 1):
        nf = growth(m); free = int(free + nf)
        pool = nf + free / 6
        if m >= paid_start: b = b * (1 - churn) + pool * conv_b
        if m >= pro_start:  p = p * (1 - churn) + pool * conv_p
        gross = b * pb + p * pp
        out.append(dict(m=m, free=free, basic=round(b), pro=round(p), gross=gross, net=net_of(gross, fee)))
    return out


grow = lambda m: Y1[m - 1] if m <= 12 else 900 + 100 * ((m - 11) // 2)   # 계속 가속
flat12 = lambda m: Y1[m - 1] if m <= 12 else 900                         # 1년차 뒤 정체
flat36 = lambda m: grow(m) if m <= 36 else grow(36)                      # 3년차 뒤 정체


def label(m):
    y, mo = divmod(9 + m, 12)   # m=1 -> 2026-10
    return f"{2026 + y}-{mo + 1:02d}"


def first(rows, key, target):
    for r in rows:
        if r[key] >= target: return label(r["m"])
    return "미도달"


def show(name, rows):
    a, c = rows[35], rows[59]
    print(f"{name}\n  36개월차 순수익 {a['net']/1e4:,.0f}만 (무료 {a['free']:,} · 유료 {a['basic']+a['pro']:,})"
          f" | 60개월차 순수익 {c['net']/1e4:,.0f}만 (무료 {c['free']:,} · 유료 {c['basic']+c['pro']:,})"
          f"\n  순수익 5천만 도달 {first(rows,'net',5e7)} · 1억 도달 {first(rows,'net',1e8)}")


if __name__ == "__main__":
    print(f"필요 총매출: 순수익 5천만 → {gross_for_net(5e7)/1e4:,.0f}만 / 순수익 1억 → {gross_for_net(1e8)/1e4:,.0f}만")
    print(f"자체 결제(수수료 3.5% 가정) 시: 5천만 → {gross_for_net(5e7,0.035)/1e4:,.0f}만 / 1억 → {gross_for_net(1e8,0.035)/1e4:,.0f}만\n")
    show("S0 현행 베이스 (이탈 8%, 전환 기본 3%·프로 1%, 유입 계속 가속)", run(grow, .03, .01, .08))
    show("S1 이탈 16.67% (금융 유료 레터 벤치마크)", run(grow, .03, .01, .1667))
    show("S2 유입이 1년차 뒤 월 900명에서 정체", run(flat12, .03, .01, .08))
    show("S3 유입이 3년차 뒤 정체", run(flat36, .03, .01, .08))
    show("S4 프로 전환 0.5% (주 1회·승률 40% 시스템이 덜 팔릴 때)", run(grow, .03, .005, .08))
    show("S5 프로 전환 0.5% + 기본 전환 5% (기본 티어가 엔진)", run(grow, .05, .005, .08))
    show("S6 S5 + 이탈 5%", run(grow, .05, .005, .05))
    show("S7 이탈 5% + 프로 전환 1.5%", run(grow, .03, .015, .05))
    show("S8 S6 + 유입 1.5배", run(lambda m: 1.5 * grow(m), .05, .005, .05))
    show("S9 S0 + 자체 결제(수수료 3.5%)", run(grow, .03, .01, .08, fee=0.035))
    print()
    for share in (0.10, 0.24, 0.40):
        arpu = (1 - share) * 15_000 + share * 59_000
        print(f"프로 비중 {share:.0%}: 유료 1인당 {arpu:,.0f}원 → 순수익 5천만에 유료 {gross_for_net(5e7)/arpu:,.0f}명 / 1억에 {gross_for_net(1e8)/arpu:,.0f}명")
