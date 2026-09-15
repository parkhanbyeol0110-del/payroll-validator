"""Rule-based payroll validation engine.

Takes a parsed pandas DataFrame of a single month's payroll rows and
(optionally) the previous month's records, and returns a list of
finding dicts ready to be persisted as ValidationResult rows.
"""

COLUMN_MAP = {
    "사번": "employee_id",
    "성명": "name",
    "조직": "org",
    "직급": "position",
    "기본급": "base_pay",
    "수당": "allowance",
    "상여": "bonus",
    "공제": "deduction",
    "실지급액": "net_pay",
}

REQUIRED_COLUMNS = ["사번", "성명", "조직", "기본급", "실지급액"]
NUMERIC_FIELDS = ["base_pay", "allowance", "bonus", "deduction", "net_pay"]

FLOAT_TOLERANCE = 1.0  # KRW tolerance for rounding differences


class StructuralError(Exception):
    pass


def normalize_dataframe(df):
    """Validate required columns exist and rename to internal keys.

    Raises StructuralError with a Korean message if required columns
    are missing. Returns a DataFrame with internal column names and
    numeric fields coerced (NaN kept as-is for missing-value checks).
    """
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise StructuralError(f"필수 컬럼이 없습니다: {', '.join(missing)}")

    df = df.rename(columns=COLUMN_MAP)
    keep_cols = [v for v in COLUMN_MAP.values() if v in df.columns]
    df = df[keep_cols].copy()

    for field in NUMERIC_FIELDS:
        if field not in df.columns:
            df[field] = 0.0
        else:
            df[field] = df[field].apply(_to_number)

    for field in ["employee_id", "name", "org", "position"]:
        if field not in df.columns:
            df[field] = None
        else:
            df[field] = df[field].astype(object).where(df[field].notna(), None)

    return df


def _to_number(value):
    try:
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def run_validation(df, prev_records_by_emp, rules_by_code):
    """Run all active rules over the normalized dataframe.

    prev_records_by_emp: dict employee_id -> dict(net_pay=..., ...) for the
        most recent prior upload, or {} if there is none.
    rules_by_code: dict rule_code -> ValidationRule (only active rules should
        be passed in; caller filters by is_active).

    Returns list of finding dicts:
        employee_id, employee_name, org, rule_code, result_text,
        severity, detected_value, expected_value
    """
    findings = []
    rows = df.to_dict(orient="records")

    # RULE_001: duplicate employee_id
    if "RULE_001" in rules_by_code:
        seen = {}
        for row in rows:
            emp = row.get("employee_id")
            if emp is None:
                continue
            seen.setdefault(emp, 0)
            seen[emp] += 1
        for row in rows:
            emp = row.get("employee_id")
            if emp is not None and seen.get(emp, 0) > 1:
                findings.append(_finding(row, "RULE_001", rules_by_code,
                                          f"사번 {emp} 중복 ({seen[emp]}건)",
                                          detected_value=str(seen[emp]), expected_value="1"))

    for row in rows:
        emp = row.get("employee_id")

        # RULE_002: required field missing
        if "RULE_002" in rules_by_code:
            missing_fields = [label for label, key in
                              [("사번", "employee_id"), ("성명", "name"), ("조직", "org"),
                               ("기본급", "base_pay"), ("실지급액", "net_pay")]
                              if row.get(key) is None]
            if missing_fields:
                findings.append(_finding(row, "RULE_002", rules_by_code,
                                          f"필수값 누락: {', '.join(missing_fields)}",
                                          detected_value="NULL", expected_value="값 존재"))

        # RULE_003: negative base pay
        if "RULE_003" in rules_by_code and row.get("base_pay") is not None:
            if row["base_pay"] < 0:
                findings.append(_finding(row, "RULE_003", rules_by_code,
                                          f"기본급이 음수입니다 ({row['base_pay']:,.0f})",
                                          detected_value=f"{row['base_pay']:,.0f}", expected_value=">= 0"))

        # RULE_004: calculation mismatch
        if "RULE_004" in rules_by_code and all(
            row.get(k) is not None for k in ["base_pay", "allowance", "bonus", "deduction", "net_pay"]
        ):
            expected = row["base_pay"] + row["allowance"] + row["bonus"] - row["deduction"]
            if abs(expected - row["net_pay"]) > FLOAT_TOLERANCE:
                findings.append(_finding(row, "RULE_004", rules_by_code,
                                          f"계산값({expected:,.0f})과 실지급액({row['net_pay']:,.0f})이 다릅니다",
                                          detected_value=f"{row['net_pay']:,.0f}",
                                          expected_value=f"{expected:,.0f}"))

        # RULE_005: month-over-month change
        if "RULE_005" in rules_by_code and emp is not None and emp in prev_records_by_emp:
            prev_net = prev_records_by_emp[emp].get("net_pay")
            cur_net = row.get("net_pay")
            if prev_net and cur_net is not None and prev_net != 0:
                rate = (cur_net - prev_net) / prev_net
                threshold = rules_by_code["RULE_005"].threshold or 0.3
                if abs(rate) > threshold:
                    findings.append(_finding(row, "RULE_005", rules_by_code,
                                              f"전월 대비 실지급액 변동률 {rate * 100:+.1f}%",
                                              detected_value=f"{rate * 100:+.1f}%",
                                              expected_value=f"±{threshold * 100:.0f}% 이내"))

        # RULE_006: new hire (not present in previous month)
        if "RULE_006" in rules_by_code and prev_records_by_emp and emp is not None:
            if emp not in prev_records_by_emp:
                findings.append(_finding(row, "RULE_006", rules_by_code,
                                          "전월에 없던 신규 사번입니다",
                                          detected_value="신규", expected_value="-"))

    # RULE_007: departed (present previously, missing this month)
    if "RULE_007" in rules_by_code and prev_records_by_emp:
        current_ids = {row.get("employee_id") for row in rows if row.get("employee_id") is not None}
        for emp, prev_row in prev_records_by_emp.items():
            if emp not in current_ids:
                findings.append({
                    "employee_id": emp,
                    "employee_name": prev_row.get("name"),
                    "org": prev_row.get("org"),
                    "rule_code": "RULE_007",
                    "result_text": "전월 대비 급여 대상에서 제외되었습니다 (퇴사 추정)",
                    "severity": rules_by_code["RULE_007"].severity,
                    "detected_value": "제외",
                    "expected_value": "-",
                })

    return findings


def _finding(row, rule_code, rules_by_code, text, detected_value=None, expected_value=None):
    return {
        "employee_id": row.get("employee_id"),
        "employee_name": row.get("name"),
        "org": row.get("org"),
        "rule_code": rule_code,
        "result_text": text,
        "severity": rules_by_code[rule_code].severity,
        "detected_value": detected_value,
        "expected_value": expected_value,
    }
