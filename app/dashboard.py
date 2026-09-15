import time

from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user

from .extensions import db
from .models import PayrollUpload, ValidationRule, ValidationResult, ResolutionHistory
from .validation.engine import run_validation

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def index():
    clients = _client_list()
    selected_client = request.args.get("company") or (clients[0] if clients else None)

    latest_upload = _latest_upload(selected_client)
    uploads = (
        PayrollUpload.query.filter_by(client_name=selected_client).order_by(PayrollUpload.uploaded_at.desc()).limit(6).all()
        if selected_client else []
    )

    company_rows = []
    for c in clients:
        u = _latest_upload(c)
        if u:
            s = _upload_summary(u)
            company_rows.append({
                "client_name": c, "upload_id": u.id, "month": u.payroll_month,
                "headcount": u.employee_count, "critical": s["critical_count"],
                "warning": s["warning_count"], "info": s["info_count"],
                "unresolved": s["unresolved_count"],
            })

    summary = _upload_summary(latest_upload) if latest_upload else None

    return render_template("dashboard.html", latest_upload=latest_upload, summary=summary, uploads=uploads,
                            clients=clients, selected_client=selected_client, company_rows=company_rows)


@dashboard_bp.route("/uploads/<int:upload_id>")
@login_required
def upload_detail(upload_id):
    upload = PayrollUpload.query.get_or_404(upload_id)
    summary = _upload_summary(upload)

    severity_filter = request.args.get("severity")
    status_filter = request.args.get("status")

    query = ValidationResult.query.filter_by(upload_id=upload_id)
    if severity_filter:
        query = query.filter_by(severity=severity_filter)
    if status_filter:
        query = query.filter_by(status=status_filter)

    results = query.order_by(ValidationResult.severity.desc(), ValidationResult.id).all()

    return render_template("detail.html", upload=upload, summary=summary, results=results,
                            severity_filter=severity_filter, status_filter=status_filter)


@dashboard_bp.route("/results/<int:result_id>/resolve", methods=["POST"])
@login_required
def resolve_result(result_id):
    result = ValidationResult.query.get_or_404(result_id)
    new_status = request.form.get("status")
    reason = request.form.get("reason", "").strip()

    if new_status not in {"검토중", "정상", "수정완료", "미처리"}:
        abort(400)

    result.status = new_status
    db.session.add(ResolutionHistory(
        validation_result_id=result.id,
        status=new_status,
        reason=reason,
        resolved_by=current_user.id,
    ))
    db.session.commit()
    flash("처리 결과가 저장되었습니다.", "success")
    return redirect(url_for("dashboard.upload_detail", upload_id=result.upload_id))


@dashboard_bp.route("/uploads/<int:upload_id>/revalidate", methods=["POST"])
@login_required
def revalidate(upload_id):
    upload = PayrollUpload.query.get_or_404(upload_id)

    ValidationResult.query.filter_by(upload_id=upload_id).delete()
    db.session.flush()

    prev_upload = (
        PayrollUpload.query
        .filter(PayrollUpload.client_name == upload.client_name, PayrollUpload.payroll_month < upload.payroll_month)
        .order_by(PayrollUpload.payroll_month.desc())
        .first()
    )
    prev_records_by_emp = {}
    if prev_upload:
        for rec in prev_upload.records:
            if rec.employee_id:
                prev_records_by_emp[rec.employee_id] = {
                    "net_pay": rec.net_pay, "name": rec.name, "org": rec.org,
                }

    rules_by_code = {r.rule_code: r for r in ValidationRule.query.filter_by(is_active=True).all()}

    import pandas as pd
    rows = [{
        "employee_id": r.employee_id, "name": r.name, "org": r.org, "position": r.position,
        "base_pay": r.base_pay, "allowance": r.allowance, "bonus": r.bonus,
        "deduction": r.deduction, "net_pay": r.net_pay,
    } for r in upload.records]
    df = pd.DataFrame(rows)

    start_time = time.time()
    findings = run_validation(df, prev_records_by_emp, rules_by_code)

    result_rows = []
    for f in findings:
        rule = rules_by_code[f["rule_code"]]
        result_rows.append(ValidationResult(
            upload_id=upload.id, employee_id=f["employee_id"], employee_name=f["employee_name"],
            org=f["org"], rule_id=rule.id, result_text=f["result_text"], severity=f["severity"],
            detected_value=f.get("detected_value"), expected_value=f.get("expected_value"),
        ))
    db.session.add_all(result_rows)
    upload.validation_seconds = round(time.time() - start_time, 3)
    db.session.commit()

    flash(f"재검증 완료: {len(result_rows)}건의 이상 항목이 발견되었습니다.", "success")
    return redirect(url_for("dashboard.upload_detail", upload_id=upload.id))


@dashboard_bp.route("/history")
@login_required
def history():
    clients = _client_list()
    selected_client = request.args.get("company")

    query = PayrollUpload.query
    if selected_client:
        query = query.filter_by(client_name=selected_client)
    uploads = query.order_by(PayrollUpload.client_name, PayrollUpload.payroll_month.desc()).all()
    rows = []
    for u in uploads:
        s = _upload_summary(u)
        rows.append((u, s))
    return render_template("history.html", rows=rows, clients=clients, selected_client=selected_client)


@dashboard_bp.route("/stats/org")
@login_required
def org_stats():
    clients = _client_list()
    selected_client = request.args.get("company") or (clients[0] if clients else None)
    latest_upload = _latest_upload(selected_client)
    if not latest_upload:
        return render_template("stats_org.html", latest_upload=None, clients=clients, selected_client=selected_client)

    headcount_by_org = {}
    for rec in latest_upload.records:
        org = rec.org or "미지정"
        headcount_by_org[org] = headcount_by_org.get(org, 0) + 1

    severity_by_org = {}
    status_by_org = {}
    error_emp_by_org = {}  # distinct employees with CRITICAL or WARNING, per org
    for r in latest_upload.results:
        org = r.org or "미지정"
        sev = severity_by_org.setdefault(org, {"CRITICAL": 0, "WARNING": 0, "INFO": 0})
        sev[r.severity] += 1
        st = status_by_org.setdefault(org, {"resolved": 0, "unresolved": 0})
        if r.status == "미처리":
            st["unresolved"] += 1
        else:
            st["resolved"] += 1
        if r.severity in ("CRITICAL", "WARNING") and r.employee_id:
            error_emp_by_org.setdefault(org, set()).add(r.employee_id)

    org_rows = []
    for org in sorted(set(headcount_by_org) | set(severity_by_org)):
        hc = headcount_by_org.get(org, 0)
        sev = severity_by_org.get(org, {"CRITICAL": 0, "WARNING": 0, "INFO": 0})
        st = status_by_org.get(org, {"resolved": 0, "unresolved": 0})
        error_emp_count = len(error_emp_by_org.get(org, set()))
        org_rows.append({
            "org": org,
            "headcount": hc,
            "critical": sev["CRITICAL"],
            "warning": sev["WARNING"],
            "info": sev["INFO"],
            "unresolved": st["unresolved"],
            "resolved": st["resolved"],
            "error_rate": (error_emp_count / hc * 100) if hc else 0,
        })
    org_rows.sort(key=lambda r: -(r["critical"] + r["warning"]))

    # Month x org trend (CRITICAL + WARNING count) to surface repeat-offender orgs (PRD 14장)
    all_uploads = (
        PayrollUpload.query.filter_by(client_name=selected_client)
        .order_by(PayrollUpload.payroll_month).all()
    )
    months = [u.payroll_month for u in all_uploads]
    trend = {}
    for u in all_uploads:
        for r in u.results:
            if r.severity in ("CRITICAL", "WARNING"):
                org = r.org or "미지정"
                trend.setdefault(org, {})
                trend[org][u.payroll_month] = trend[org].get(u.payroll_month, 0) + 1

    trend_orgs = sorted(trend.keys(), key=lambda o: -sum(trend[o].values()))

    return render_template("stats_org.html", latest_upload=latest_upload, org_rows=org_rows,
                            months=months, trend=trend, trend_orgs=trend_orgs,
                            clients=clients, selected_client=selected_client)


@dashboard_bp.route("/rules")
@login_required
def rules():
    if not current_user.is_admin:
        abort(403)
    all_rules = ValidationRule.query.order_by(ValidationRule.rule_code).all()
    return render_template("rules.html", rules=all_rules)


@dashboard_bp.route("/rules/<int:rule_id>/toggle", methods=["POST"])
@login_required
def toggle_rule(rule_id):
    if not current_user.is_admin:
        abort(403)
    rule = ValidationRule.query.get_or_404(rule_id)
    rule.is_active = not rule.is_active
    db.session.commit()
    return redirect(url_for("dashboard.rules"))


@dashboard_bp.route("/rules/<int:rule_id>/threshold", methods=["POST"])
@login_required
def update_threshold(rule_id):
    if not current_user.is_admin:
        abort(403)
    rule = ValidationRule.query.get_or_404(rule_id)
    value = request.form.get("threshold", "").strip()
    rule.threshold = float(value) if value else None
    db.session.commit()
    flash("Rule 기준값이 업데이트되었습니다.", "success")
    return redirect(url_for("dashboard.rules"))


def _client_list():
    rows = db.session.query(PayrollUpload.client_name).distinct().order_by(PayrollUpload.client_name).all()
    return [r[0] for r in rows if r[0]]


def _latest_upload(client_name):
    if not client_name:
        return None
    return (
        PayrollUpload.query.filter_by(client_name=client_name)
        .order_by(PayrollUpload.payroll_month.desc(), PayrollUpload.uploaded_at.desc())
        .first()
    )


def _upload_summary(upload):
    results = upload.results
    total = upload.employee_count
    error_emp_ids = {r.employee_id for r in results if r.severity == "CRITICAL"}
    warning_emp_ids = {r.employee_id for r in results if r.severity == "WARNING"} - error_emp_ids
    normal_count = max(total - len(error_emp_ids) - len(warning_emp_ids), 0)

    by_rule = {}
    for r in results:
        key = (r.rule.rule_code, r.rule.rule_name)
        by_rule.setdefault(key, 0)
        by_rule[key] += 1

    return {
        "total": total,
        "normal": normal_count,
        "warning": len(warning_emp_ids),
        "error": len(error_emp_ids),
        "critical_count": sum(1 for r in results if r.severity == "CRITICAL"),
        "warning_count": sum(1 for r in results if r.severity == "WARNING"),
        "info_count": sum(1 for r in results if r.severity == "INFO"),
        "unresolved_count": sum(1 for r in results if r.status == "미처리"),
        "resolved_count": sum(1 for r in results if r.status in ("정상", "수정완료")),
        "by_rule": sorted(by_rule.items(), key=lambda kv: -kv[1]),
    }
