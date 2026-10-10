"""가격 적정성과 광고 수주 검토의 계산 — docs/19_pricing_and_ads_review.md 의 표는 모두 여기서 나온다.

순수익의 정의는 scripts/revenue_sim.py 와 같다: 총매출 / 1.1(부가세) x (1 - 결제 수수료) - 고정비.
소득세와 건강보험료는 이 정의에 들어 있지 않으므로 §7에서 따로 계산한다.
조사에서 온 숫자(광고 단가, 벤치마크, 세율)는 docs/19 의 출처를 따른다. 가정이지 예측이 아니다.
실행: python scripts/pricing_review.py
"""
from path_to_100m import run, grow, label

TARGET = 10_000_000          # 1차 목표: 월 순수익 1,000만원 (Nick, 2026-10-10)
VAT = 0.10
FIXED = 250_000              # docs/04 의 고정비 가정
FEE_NAVER = 0.104            # 네이버 프리미엄콘텐츠 8% + 결제 2.4% (docs/01)
FEE_STIBEE = 0.0352          # 스티비 유료 뉴스레터: PG 3.2% + 그 부가세
P_BASIC, P_PRO = 15_000, 59_000
USD = 1_400                  # 저장소의 환율 가정 (docs/10)


def per_sub(price, fee):
    """유료 구독자 한 명이 한 달에 남기는 돈(부가세·결제 수수료를 뺀 뒤)."""
    return price / (1 + VAT) * (1 - fee)


def gross_for(net, fee, fixed=FIXED):
    return (net + fixed) * (1 + VAT) / (1 - fee)


def subs_for(net, pro_share, fee, fixed=FIXED, pb=P_BASIC, pp=P_PRO):
    arpu = (1 - pro_share) * pb + pro_share * pp
    return gross_for(net, fee, fixed) / arpu


def won(x):
    return f"{x / 1e4:,.1f}만" if abs(x) < 1e5 else f"{x / 1e4:,.0f}만"


def first_month(rows, target, extra_fixed=0):
    for r in rows:
        if r["net"] - extra_fixed >= target:
            return r
    return None


def section(title):
    print(f"\n## {title}")


# ---------------------------------------------------------------- 1
section("1. 유료 구독자 한 명이 한 달에 남기는 돈")
for name, fee in (("네이버 프리미엄콘텐츠 10.4%", FEE_NAVER), ("스티비 유료 3.52%", FEE_STIBEE)):
    print(f"  {name}: 기본 {per_sub(P_BASIC, fee):,.0f}원 · 프로 {per_sub(P_PRO, fee):,.0f}원")

# ---------------------------------------------------------------- 2
section("2. 월 순수익 1,000만원에 필요한 유료 구독자 수")
print("  (고정비 25만원. 괄호는 필요한 총매출)")
for name, fee in (("네이버 10.4%", FEE_NAVER), ("스티비 3.52%", FEE_STIBEE)):
    g = gross_for(TARGET, fee)
    cells = [f"프로 {s:.0%} → {subs_for(TARGET, s, fee):,.0f}명" for s in (0.0, 0.10, 0.24)]
    print(f"  {name} (총매출 {won(g)}): " + " / ".join(cells))

print("  데이터 표시 계약이 붙을 때(네이버 10.4%, 프로 비중 10%):")
for lic_usd in (0, 399, 2_499):
    fixed = FIXED + lic_usd * USD
    print(f"    월 ${lic_usd:,} (고정비 {won(fixed)}) → {subs_for(TARGET, 0.10, FEE_NAVER, fixed):,.0f}명")

# ---------------------------------------------------------------- 3
section("3. 그 유료 구독자를 얻는 데 필요한 무료 구독자 수")
print("  (무료 구독자 가운데 유료인 사람의 비율별. 네이버 10.4%, 고정비 25만원)")
ratios = (0.0084, 0.02, 0.03, 0.05, 0.10)
print("  프로 비중 | " + " | ".join(f"{r * 100:g}%" for r in ratios))
for s_ in (0.0, 0.10, 0.24):
    need = subs_for(TARGET, s_, FEE_NAVER)
    print(f"  {s_:>5.0%}     | " + " | ".join(f"{need / r:>7,.0f}" for r in ratios))
print("  무료 구독자가 그 수에 닿는 달(유입은 docs/04 베이스 그대로, 프로 비중 10%):")
free_path = [r["free"] for r in run(growth=grow, conv_b=.03, conv_p=.01, churn=.08)]
for r in ratios:
    need = subs_for(TARGET, 0.10, FEE_NAVER) / r
    m = next((i + 1 for i, f in enumerate(free_path) if f >= need), None)
    print(f"    {r * 100:g}% → 무료 {need:,.0f}명 → " + (f"{label(m)} ({m}개월차)" if m else "60개월 안에 닿지 않음"))

# ---------------------------------------------------------------- 4
section("4. 지금의 모델(docs/04)로는 언제 닿는가")
print("  (path_to_100m.py 의 구조 그대로. 유입은 1년차 400→900명, 그 뒤 두 달마다 +100명)")
flat250 = lambda m: 300 if m == 1 else 250
cases = [
    ("베이스: 기본 12월 · 프로 1월 (D4), 전환 3%·1%, 이탈 8%", dict(growth=grow, conv_b=.03, conv_p=.01, churn=.08)),
    ("유료가 한 달 밀림: 기본 1월 · 프로 2월", dict(growth=grow, conv_b=.03, conv_p=.01, churn=.08, paid_start=4, pro_start=5)),
    ("프로 전환이 절반(0.5%)", dict(growth=grow, conv_b=.03, conv_p=.005, churn=.08)),
    ("프로 전환 0.33% (유료 가운데 프로가 10%쯤 되는 값)", dict(growth=grow, conv_b=.03, conv_p=.0033, churn=.08)),
    ("프로 없이 기본만", dict(growth=grow, conv_b=.03, conv_p=0.0, churn=.08)),
    ("이탈 11.72% (투자 유료 레터 중앙값)", dict(growth=grow, conv_b=.03, conv_p=.01, churn=.1172)),
    ("프로 절반 + 이탈 11.72%", dict(growth=grow, conv_b=.03, conv_p=.005, churn=.1172)),
    ("베어: 유입 월 250명, 전환 2%·0.6%, 이탈 10%", dict(growth=flat250, conv_b=.02, conv_p=.006, churn=.10)),
]
for name, kw in cases:
    rows = run(**kw)
    hit = first_month(rows, TARGET)
    if hit:
        paid = hit["basic"] + hit["pro"]
        print(f"  {name}\n    → {label(hit['m'])} ({hit['m']}개월차) · 무료 {hit['free']:,} · 유료 {paid:,}"
              f" (기본 {hit['basic']:,} · 프로 {hit['pro']:,}) · 무료 대비 유료 {paid / hit['free']:.1%}")
    else:
        last = rows[-1]
        print(f"  {name}\n    → 60개월 안에 닿지 않음 (60개월차 순수익 {won(last['net'])})")
base = run(growth=grow, conv_b=.03, conv_p=.01, churn=.08)
m12 = base[11]
pro_rev = m12["pro"] * P_PRO / m12["gross"]
stb = run(growth=grow, conv_b=.03, conv_p=.01, churn=.08, fee=FEE_STIBEE)
print(f"  결제를 스티비(3.52%)로 하면 같은 13개월차 순수익 {won(base[12]['net'])} → {won(stb[12]['net'])}")
m10k = next(r for r in base if r["free"] >= 10_000)
print(f"  베이스에서 무료 1만 명을 넘는 달: {label(m10k['m'])} ({m10k['m']}개월차) · 그 달의 순수익 {won(m10k['net'])}")
print(f"  베이스 12개월차: 유료 가운데 프로 {m12['pro'] / (m12['basic'] + m12['pro']):.0%}, 매출 가운데 프로 {pro_rev:.0%}")

# ---------------------------------------------------------------- 5
section("5. 기본 가격을 바꾸면")
print("  (기본만으로 1,000만원에 필요한 수, 네이버 10.4%. '같은 매출이 되는 전환 변화'는 15,000원 대비)")
for p in (9_900, 12_900, 15_000, 17_900, 19_000):
    need = subs_for(TARGET, 0.0, FEE_NAVER, pb=p)
    chg = P_BASIC / p - 1
    note = "기준" if p == P_BASIC else (f"유료 전환이 {chg:.0%} 늘어야 15,000원과 같은 매출" if chg > 0
                                      else f"유료 전환이 {-chg:.0%} 줄어도 15,000원과 같은 매출")
    print(f"  {p:>6,}원 → {need:>5,.0f}명 · {note}")
print("  프로 가격(프로 비중 10%일 때 필요한 유료 수):")
for p in (39_000, 49_000, 59_000):
    print(f"  {p:>6,}원 → {subs_for(TARGET, 0.10, FEE_NAVER, pp=p):,.0f}명")

# ---------------------------------------------------------------- 6
section("6. 유료 구독자 한 명의 생애 가치 (한 달 남기는 돈 ÷ 월 이탈)")
for churn in (0.08, 0.1172, 0.1667):
    print(f"  이탈 {churn:.2%}: 기본 {per_sub(P_BASIC, FEE_NAVER) / churn:,.0f}원 · 프로 {per_sub(P_PRO, FEE_NAVER) / churn:,.0f}원"
          f" (평균 {1 / churn:.1f}개월)")

# ---------------------------------------------------------------- 7
section("7. 세금과 건강보험료를 낸 뒤")
BRACKETS = [(14e6, .06), (50e6, .15), (88e6, .24), (150e6, .35), (300e6, .38), (500e6, .40), (1e9, .42), (float("inf"), .45)]
LOCAL = 0.10                 # 지방소득세 = 소득세의 10%
NHI, LTC, NHI_FLOOR = 0.0719, 0.1314, 20e6   # 2026년 건강보험료율, 장기요양(건보료 대비), 보수 외 소득 공제


def income_tax(base):
    tax, lo = 0.0, 0.0
    for hi, rate in BRACKETS:
        if base > lo:
            tax += (min(base, hi) - lo) * rate
        lo = hi
    return tax * (1 + LOCAL)


def after_tax(biz_year, wage_base):
    add_tax = income_tax(wage_base + biz_year) - income_tax(wage_base)
    nhi = max(0.0, biz_year - NHI_FLOOR) * NHI * (1 + LTC)
    return biz_year - add_tax - nhi, add_tax, nhi


print("  (사업소득금액 = 이 문서의 순수익 x 12 로 어림. 근로소득 과세표준은 가정 — 실제 값은 Nick만 안다)")
for wage in (60e6, 90e6, 120e6):
    left, tax, nhi = after_tax(TARGET * 12, wage)
    print(f"  근로 과세표준 {won(wage)}: 순수익 월 1,000만 → 소득세 {won(tax)}/년 · 건보료 {won(nhi)}/년"
          f" → 손에 남는 돈 월 {won(left / 12)} ({left / (TARGET * 12):.0%})")
    lo, hi = TARGET, TARGET * 4
    for _ in range(60):
        mid = (lo + hi) / 2
        if after_tax(mid * 12, wage)[0] / 12 < TARGET:
            lo = mid
        else:
            hi = mid
    print(f"    손에 월 1,000만이 남으려면 순수익 월 {won(hi)} (유료 약 {subs_for(hi, 0.10, FEE_NAVER):,.0f}명, 프로 비중 10%)")

# ---------------------------------------------------------------- 8
section("8. 광고 — 뉴스레터 광고 한 건의 환산 금액")
print("  (가) 대형 대중 매체 단가 구독자 1인당 16~22원 / (나) 해외 개인투자 CPM $30~60 x 오픈율 40% / (다) 타깃이 좁고 영업 조직이 있는 매체 60~120원")
basic_net = per_sub(P_BASIC, FEE_NAVER)
for n in (1_000, 5_000, 10_000, 30_000):
    a = (n * 16, n * 22)
    b = (n * 0.4 / 1000 * 30 * USD, n * 0.4 / 1000 * 60 * USD)
    c = (n * 60, n * 120)
    lo, hi = min(a[0], b[0]), max(a[1], b[1])
    print(f"  무료 {n:>6,}명: (가) {won(a[0])}~{won(a[1])} · (나) {won(b[0])}~{won(b[1])} · (다) {won(c[0])}~{won(c[1])}")
    print(f"    (가)·(나) 기준으로 월 4건을 다 팔면 {won(lo * 4)}~{won(hi * 4)} = 목표의 {lo * 4 / TARGET:.0%}~{hi * 4 / TARGET:.0%}"
          f" = 기본 구독자 {lo * 4 / basic_net:,.0f}~{hi * 4 / basic_net:,.0f}명분")

print("  같은 자리를 우리 유료 안내로 쓸 때: 기본 구독자 한 명의 생애 가치 "
      f"{basic_net / 0.08:,.0f}원(이탈 8%) · {basic_net / 0.1172:,.0f}원(이탈 11.72%)")
for n in (5_000, 10_000):
    ad_hi = max(n * 22, n * 0.4 / 1000 * 60 * USD)
    print(f"    무료 {n:,}명에서 광고 한 건 최대 {won(ad_hi)} = 기본 유료 전환 {ad_hi / (basic_net / 0.08):.1f}~{ad_hi / (basic_net / 0.1172):.1f}명과 같은 값")

print("  인스타 피드 광고(팔로워 1,000명당 1만원 공식): " + " · ".join(f"{f:,}명 {won(f / 1000 * 10_000)}" for f in (1_000, 5_000, 10_000, 50_000)))
print("  유튜브 쇼츠 광고 수익(조회 1,000회당 44~290원): " + " · ".join(f"월 {v // 10_000:,}만 회 {v / 1000 * 44:,.0f}~{v / 1000 * 290:,.0f}원" for v in (100_000, 1_000_000)))
