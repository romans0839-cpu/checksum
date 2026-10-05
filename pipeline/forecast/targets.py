"""예측 대상 정의. 연방 통계기관이 정해진 날 숫자로 발표하는 지표만 넣는다 (docs/12 §3).

넣지 않는 것: 주가·지수·환율·개별 종목 실적·기준금리 결정, 민간 기관 지표(ISM, 미시간대 등 — 재게재 권리 없음).
ref_period 표기: 월 "2026-09" / 분기 "2026Q3" / 주 "2026-10-10"(그 주의 마지막 날, 토요일).
"""
import re

# event_kind -> (이름, 출처 source_id, 주기)
EVENTS = {
    "CPI": ("소비자물가", "bls", "M"),
    "EMP": ("고용보고서", "bls", "M"),
    "PCE": ("개인소득·지출(PCE 물가)", "bea", "M"),
    "GDP_ADV": ("GDP 속보치", "bea", "Q"),
    "PPI": ("생산자물가", "bls", "M"),
    "CLAIMS": ("주간 신규 실업수당 청구", "dol", "W"),
}

# target_id -> (event_kind, 이름, 단위, 발표 자릿수, 묶음)
#   묶음 1 = 핵심(독자가 기다리는 발표) / 2 = 표본을 빨리 쌓는 용도
TARGETS = {
    "CPI_MOM": ("CPI", "CPI 전월비(계절조정)", "%", 1, 1),
    "CPI_CORE_MOM": ("CPI", "근원 CPI 전월비(계절조정)", "%", 1, 1),
    "CPI_YOY": ("CPI", "CPI 전년비", "%", 1, 1),
    "NFP_CHG": ("EMP", "비농업 취업자 증감", "천 명", 0, 1),
    "UNRATE": ("EMP", "실업률", "%", 1, 1),
    "PCE_CORE_MOM": ("PCE", "근원 PCE 물가 전월비", "%", 1, 1),
    "PCE_YOY": ("PCE", "PCE 물가 전년비", "%", 1, 1),
    "GDP_ADV_QOQ": ("GDP_ADV", "실질 GDP 전기비 연율(속보치)", "%", 1, 1),
    "PPI_FD_MOM": ("PPI", "PPI 최종수요 전월비", "%", 1, 2),
    "CLAIMS_INIT": ("CLAIMS", "신규 실업수당 청구(계절조정)", "천 건", 0, 2),
}

# 기준선. 엔진과 같은 봉인 기록에 함께 들어간다
BASELINES = {"prev": "직전 발표값 그대로"}

INTERVAL = 0.80   # 엔진이 내는 구간(p10~p90)이 담아야 하는 비율
MIN_SCORED_EVENTS = 30   # 이보다 적으면 '표본 부족'으로 표시한다

_REF = {"M": r"^\d{4}-(0[1-9]|1[0-2])$", "Q": r"^\d{4}Q[1-4]$", "W": r"^\d{4}-\d{2}-\d{2}$"}


def ref_period_ok(event_kind, ref_period):
    return bool(re.match(_REF[EVENTS[event_kind][2]], str(ref_period)))


def decimals(target):
    return TARGETS[target][3]
