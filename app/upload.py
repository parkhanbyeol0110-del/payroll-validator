import os
import time

import pandas as pd
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from .extensions import db
from .models import PayrollUpload, PayrollRecord, ValidationRule, ValidationResult
from .validation.engine import normalize_dataframe, run_validation, StructuralError

upload_bp = Blueprint("upload", __name__)

ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".csv"}


@upload_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload_file():
    if request.method == "GET":
        existing_clients = [
            row[0] for row in
            db.session.query(PayrollUpload.client_name).distinct().order_by(PayrollUpload.client_name).all()
            if row[0]
        ]
        return render_template("upload.html", existing_clients=existing_clients)

    client_name = request.form.get("client_name", "").strip()
    payroll_month = request.form.get("payroll_month", "").strip()
    file = request.files.get("payroll_file")

    if not client_name:
        flash("고객사명을 입력해 주세요.", "error")
        return redirect(url_for("upload.upload_file"))

    if not payroll_month:
        flash("급여 기준월을 선택해 주세요.", "error")
        return redirect(url_for("upload.upload_file"))

    if not file or file.filename == "":
        flash("업로드할 파일을 선택해 주세요.", "error")
        return redirect(url_for("upload.upload_file"))

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        flash(f"지원하지 않는 파일 형식입니다: {ext} (xlsx, xls, csv만 가능)", "error")
        return redirect(url_for("upload.upload_file"))

    try:
        if ext == ".csv":
            df = pd.read_csv(file, dtype=str)
        else:
            df = pd.read_excel(file, dtype=str)
    except Exception as exc:
        flash(f"파일을 읽을 수 없습니다: {exc}", "error")
        return redirect(url_for("upload.upload_file"))

    try:
        norm_df = normalize_dataframe(df)
    except StructuralError as exc:
        flash(str(exc), "error")
        return redirect(url_for("upload.upload_file"))

    if len(norm_df) == 0:
        flash("업로드한 파일에 데이터가 없습니다.", "error")
        return redirect(url_for("upload.upload_file"))

    start_time = time.time()

    payroll_upload = PayrollUpload(
        client_name=client_name,
        payroll_month=payroll_month,
        file_name=file.filename,
        uploaded_by=current_user.id,
        employee_count=len(norm_df),
    )
    db.session.add(payroll_upload)
    db.session.flush()

    records = []
    for row in norm_df.to_dict(orient="records"):
        rec = PayrollRecord(
            upload_id=payroll_upload.id,
            employee_id=row.get("employee_id"),
            name=row.get("name"),
            org=row.get("org"),
            position=row.get("position"),
            base_pay=row.get("base_pay"),
            allowance=row.get("allowance"),
            bonus=row.get("bonus"),
            deduction=row.get("deduction"),
            net_pay=row.get("net_pay"),
        )
        records.append(rec)
    db.session.add_all(records)

    prev_upload = (
        PayrollUpload.query
        .filter(PayrollUpload.client_name == client_name, PayrollUpload.payroll_month < payroll_month)
        .order_by(PayrollUpload.payroll_month.desc())
        .first()
    )
    prev_records_by_emp = {}
    if prev_upload:
        for rec in prev_upload.records:
            if rec.employee_id:
                prev_records_by_emp[rec.employee_id] = {
                    "net_pay": rec.net_pay,
                    "name": rec.name,
                    "org": rec.org,
                }

    rules_by_code = {r.rule_code: r for r in ValidationRule.query.filter_by(is_active=True).all()}
    findings = run_validation(norm_df, prev_records_by_emp, rules_by_code)

    result_rows = []
    for f in findings:
        rule = rules_by_code[f["rule_code"]]
        result_rows.append(ValidationResult(
            upload_id=payroll_upload.id,
            employee_id=f["employee_id"],
            employee_name=f["employee_name"],
            org=f["org"],
            rule_id=rule.id,
            result_text=f["result_text"],
            severity=f["severity"],
            detected_value=f.get("detected_value"),
            expected_value=f.get("expected_value"),
        ))
    db.session.add_all(result_rows)

    payroll_upload.validation_seconds = round(time.time() - start_time, 3)
    db.session.commit()

    flash(f"검증 완료: 대상 {len(norm_df)}명 중 {len(result_rows)}건의 이상 항목이 발견되었습니다.", "success")
    return redirect(url_for("dashboard.upload_detail", upload_id=payroll_upload.id))
