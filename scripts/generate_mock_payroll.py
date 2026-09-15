"""
BPO 데모용 가상 고객사 급여 목업 데이터 생성기.

실행:
    python scripts/generate_mock_payroll.py

- 회사별로 업종에 맞는 조직/직급/급여 밴드를 갖는 가상 인원을 생성한다.
- 1월(정상 기준월)과 2월(변동+이상치 포함) 두 달치를 각 회사별 엑셀 파일로 만든다.
- 컬럼은 payroll-validator 앱의 필수 컬럼과 완전히 동일하다:
  사번, 성명, 조직, 직급, 기본급, 수당, 상여, 공제, 실지급액
- 이름/사번/회사명은 전부 무작위 조합으로 생성한 가상 데이터이며 실존 인물과 무관하다.
"""
import os
import random

import pandas as pd

random.seed(42)

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sample_data", "mock_companies")
os.makedirs(OUT_DIR, exist_ok=True)

SURNAMES = ["김", "이", "박", "최", "정", "강", "조", "윤", "장", "임", "한", "오", "서", "신", "권", "황", "안", "송", "전", "홍"]
GIVEN_1 = ["민", "서", "지", "도", "하", "예", "은", "수", "재", "현", "우", "성", "준", "aa", "태", "유", "진", "승", "채", "규"]
GIVEN_2 = ["준", "연", "우", "윤", "은", "빈", "율", "aa", "훈", "아", "원", "호", "민", "경", "영", "린", "찬", "혁", "서", "율"]
GIVEN_2 = [g for g in GIVEN_2 if g != "aa"]
GIVEN_1 = [g for g in GIVEN_1 if g != "aa"]


def random_name(used):
    while True:
        name = random.choice(SURNAMES) + random.choice(GIVEN_1) + random.choice(GIVEN_2)
        if name not in used:
            used.add(name)
            return name


class Company:
    def __init__(self, code, name, industry, depts, position_bands, headcount):
        self.code = code
        self.name = name
        self.industry = industry
        self.depts = depts  # list of dept names
        self.position_bands = position_bands  # dict position -> (base_min, base_max)
        self.headcount = headcount


COMPANIES = [
    Company(
        code="SJL",
        name="세종물류",
        industry="물류",
        depts=["물류운영팀", "배송관리팀", "품질관리팀", "인사총무팀"],
        position_bands={
            "사원": (2600000, 3100000),
            "주임": (2900000, 3400000),
            "대리": (3300000, 3900000),
            "과장": (3900000, 4600000),
            "차장": (4600000, 5400000),
        },
        headcount=36,
    ),
    Company(
        code="HBE",
        name="한빛전자",
        industry="제조",
        depts=["생산1팀", "생산2팀", "품질보증팀", "구매팀", "연구개발팀"],
        position_bands={
            "사원": (2700000, 3200000),
            "주임": (3000000, 3500000),
            "대리": (3400000, 4000000),
            "과장": (4000000, 4800000),
            "차장": (4800000, 5600000),
            "부장": (5600000, 6500000),
        },
        headcount=52,
    ),
    Company(
        code="GTF",
        name="그린테이블푸드",
        industry="외식/급식",
        depts=["조리팀", "매장운영팀", "위생관리팀", "영업지원팀"],
        position_bands={
            "사원": (2400000, 2800000),
            "주임": (2700000, 3100000),
            "대리": (3000000, 3500000),
            "과장": (3500000, 4100000),
        },
        headcount=26,
    ),
    Company(
        code="PTS",
        name="파인트리소프트",
        industry="IT/소프트웨어",
        depts=["개발팀", "QA팀", "디자인팀", "경영지원팀"],
        position_bands={
            "사원": (3200000, 3800000),
            "대리": (3900000, 4600000),
            "과장": (4600000, 5500000),
            "차장": (5500000, 6500000),
        },
        headcount=22,
    ),
]


def gen_allowance(base_pay):
    return round(base_pay * random.uniform(0.04, 0.09) / 1000) * 1000


def gen_deduction(gross):
    return round(gross * random.uniform(0.085, 0.11) / 1000) * 1000


def build_employee(company, emp_no, used_names):
    position = random.choices(
        list(company.position_bands.keys()),
        weights=[max(6 - i, 1) for i in range(len(company.position_bands))],
    )[0]
    lo, hi = company.position_bands[position]
    base_pay = round(random.uniform(lo, hi) / 10000) * 10000
    allowance = gen_allowance(base_pay)
    bonus = 0
    gross = base_pay + allowance + bonus
    deduction = gen_deduction(gross)
    net_pay = gross - deduction
    return {
        "employee_id": f"{company.code}{emp_no:04d}",
        "name": random_name(used_names),
        "org": random.choice(company.depts),
        "position": position,
        "base_pay": base_pay,
        "allowance": allowance,
        "bonus": bonus,
        "deduction": deduction,
        "net_pay": net_pay,
    }


def to_df(rows):
    df = pd.DataFrame(rows)
    df = df.rename(columns={
        "employee_id": "사번", "name": "성명", "org": "조직", "position": "직급",
        "base_pay": "기본급", "allowance": "수당", "bonus": "상여",
        "deduction": "공제", "net_pay": "실지급액",
    })
    return df[["사번", "성명", "조직", "직급", "기본급", "수당", "상여", "공제", "실지급액"]]


def generate_company(company):
    used_names = set()
    jan_rows = [build_employee(company, i + 1, used_names) for i in range(company.headcount)]

    feb_rows = [dict(r) for r in jan_rows]

    # 1) 승진/인상: 상위 2명 급여 40~55% 인상 (RULE_005 전월 대비 급증 트리거)
    for r in random.sample(feb_rows, k=2):
        raise_rate = random.uniform(0.4, 0.55)
        r["base_pay"] = round(r["base_pay"] * (1 + raise_rate) / 10000) * 10000
        r["allowance"] = gen_allowance(r["base_pay"])
        gross = r["base_pay"] + r["allowance"] + r["bonus"]
        r["deduction"] = gen_deduction(gross)
        r["net_pay"] = gross - r["deduction"]

    # 2) 퇴사자 1~2명: 2월 명단에서 제외 (RULE_007)
    leavers = random.sample(feb_rows, k=random.randint(1, 2))
    leaver_ids = {r["employee_id"] for r in leavers}
    feb_rows = [r for r in feb_rows if r["employee_id"] not in leaver_ids]

    # 3) 신규 입사자 1~2명 (RULE_006)
    next_no = company.headcount + 1
    for _ in range(random.randint(1, 2)):
        feb_rows.append(build_employee(company, next_no, used_names))
        next_no += 1

    # 4) 사번 중복 1건 (RULE_001): 임의 직원 행을 복제
    dup_source = random.choice(feb_rows)
    feb_rows.append(dict(dup_source))

    # 5) 필수값 누락 1건 (RULE_002): 성명 비움
    target = random.choice([r for r in feb_rows if r is not dup_source])
    target["name"] = ""

    # 6) 계산 불일치 1건 (RULE_004): 실지급액을 임의로 어긋나게
    target2 = random.choice([r for r in feb_rows if r is not target and r is not dup_source])
    target2["net_pay"] = target2["net_pay"] + random.choice([-50000, 70000, 120000])

    # 7) 음수 급여 1건 (RULE_003), 위 항목들과 겹치지 않게 선택
    candidates = [r for r in feb_rows if r not in (target, target2, dup_source)]
    target3 = random.choice(candidates)
    target3["base_pay"] = -abs(target3["base_pay"])
    gross3 = target3["base_pay"] + target3["allowance"] + target3["bonus"]
    target3["net_pay"] = gross3 - target3["deduction"]

    random.shuffle(feb_rows)

    jan_df = to_df(jan_rows)
    feb_df = to_df(feb_rows)

    jan_path = os.path.join(OUT_DIR, f"{company.name}_2026-01.xlsx")
    feb_path = os.path.join(OUT_DIR, f"{company.name}_2026-02.xlsx")
    jan_df.to_excel(jan_path, index=False)
    feb_df.to_excel(feb_path, index=False)
    return jan_path, feb_path


def main():
    print(f"출력 경로: {OUT_DIR}\n")
    for company in COMPANIES:
        jan_path, feb_path = generate_company(company)
        print(f"[{company.name}] ({company.industry}, 인원 {company.headcount}명)")
        print(f"  - {os.path.basename(jan_path)}")
        print(f"  - {os.path.basename(feb_path)}")


if __name__ == "__main__":
    main()
