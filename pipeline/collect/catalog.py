"""수집할 계열 목록 (노동통계국). 계열 번호는 첫 실행 때 API가 돌려주는 제목과 대조한다.

한 줄 = (계열 번호, 묶음, 한글 이름, 단위, 제목에 있어야 하는 말, 만들 파생값)
파생값: pc1 = 전월 대비 %, pc12 = 전년 같은 달 대비 %, nc1 = 전월 대비 증감
제목이 맞지 않는 계열은 저장은 하되 '불일치'로 표시하고 사실 묶음에 넣지 않는다.
"""

BLS = [
    # --- 소비자물가 (CPI-U, 미국 도시 평균)
    ("CUSR0000SA0", "CPI", "CPI 전 품목(계절조정)", "지수", ("all items",), ("pc1",)),
    ("CUSR0000SA0L1E", "CPI", "근원 CPI(식품·에너지 제외, 계절조정)", "지수", ("all items less food and energy",), ("pc1",)),
    ("CUUR0000SA0", "CPI", "CPI 전 품목(원계열)", "지수", ("all items",), ("pc1", "pc12")),
    ("CUUR0000SA0L1E", "CPI", "근원 CPI(원계열)", "지수", ("all items less food and energy",), ("pc1", "pc12")),
    ("CUSR0000SA0E", "CPI", "에너지", "지수", ("energy",), ("pc1",)),
    ("CUSR0000SETB01", "CPI", "휘발유", "지수", ("gasoline",), ("pc1",)),
    ("CUSR0000SAF1", "CPI", "식품", "지수", ("food",), ("pc1",)),
    ("CUSR0000SAH1", "CPI", "주거", "지수", ("shelter",), ("pc1",)),
    ("CUSR0000SEHC", "CPI", "자가주거비(OER)", "지수", ("owners' equivalent rent",), ("pc1",)),
    ("CUSR0000SEHA", "CPI", "임대료", "지수", ("rent of primary residence",), ("pc1",)),
    ("CUSR0000SETA02", "CPI", "중고차", "지수", ("used cars and trucks",), ("pc1",)),
    ("CUSR0000SETA01", "CPI", "신차", "지수", ("new vehicles",), ("pc1",)),
    ("CUSR0000SAA", "CPI", "의류", "지수", ("apparel",), ("pc1",)),
    ("CUSR0000SAM2", "CPI", "의료 서비스", "지수", ("medical care services",), ("pc1",)),
    ("CUSR0000SETG01", "CPI", "항공료", "지수", ("airline fare",), ("pc1",)),
    ("CUSR0000SACL1E", "CPI", "근원 상품", "지수", ("commodities less food and energy",), ("pc1",)),
    ("CUSR0000SASLE", "CPI", "근원 서비스", "지수", ("services less energy services",), ("pc1",)),
    # --- 고용보고서
    ("CES0000000001", "EMP", "비농업 취업자 수", "천 명", ("total nonfarm",), ("nc1",)),
    ("CES0500000001", "EMP", "민간 취업자 수", "천 명", ("total private",), ("nc1",)),
    ("LNS14000000", "EMP", "실업률", "%", ("unemployment rate",), ()),
    ("LNS11300000", "EMP", "경제활동참가율", "%", ("participation rate",), ()),
    ("CES0500000003", "EMP", "민간 시간당 평균임금", "달러", ("average hourly earnings",), ("pc1", "pc12")),
    ("CES0500000002", "EMP", "민간 주당 평균 근로시간", "시간", ("average weekly hours",), ()),
    # --- 생산자물가
    ("WPSFD4", "PPI", "PPI 최종수요(계절조정)", "지수", ("final demand",), ("pc1",)),
    ("WPSFD49104", "PPI", "PPI 최종수요(식품·에너지 제외)", "지수", ("final demand", "less foods and energy"), ("pc1",)),
    ("WPSFD41", "PPI", "PPI 최종수요 상품", "지수", ("final demand goods",), ("pc1",)),
    ("WPSFD42", "PPI", "PPI 최종수요 서비스", "지수", ("final demand services",), ("pc1",)),
]

# 예측 대상 -> (계열 번호, 파생값 또는 "" = 수준 그대로). 여기 없는 대상은 수집기가 아직 없다
TARGET_SERIES = {
    "CPI_MOM": ("CUSR0000SA0", "pc1"),
    "CPI_CORE_MOM": ("CUSR0000SA0L1E", "pc1"),
    "CPI_YOY": ("CUUR0000SA0", "pc12"),
    "NFP_CHG": ("CES0000000001", "nc1"),
    "UNRATE": ("LNS14000000", ""),
    "PPI_FD_MOM": ("WPSFD4", "pc1"),
}

# 사실 묶음에 함께 넣는 다른 묶음 (발표 전에 이미 나와 있는 것만 들어간다)
RELATED = {"CPI": ("PPI", "EMP"), "PPI": ("CPI",), "EMP": ()}

SOURCE_URL = {"CPI": "https://www.bls.gov/news.release/cpi.nr0.htm", "EMP": "https://www.bls.gov/news.release/empsit.nr0.htm",
              "PPI": "https://www.bls.gov/news.release/ppi.nr0.htm"}


def series_id(bls_id, derived=""):
    return "BLS." + bls_id + ("." + derived if derived else "")


def target_series_id(target):
    bls_id, derived = TARGET_SERIES[target]
    return series_id(bls_id, derived)
