"""Upload-time alerts so staff don't have to open the dashboard to know something needs attention.

Sends an email via SMTP when SMTP_HOST and NOTIFY_EMAIL_TO are both configured. If either is
missing, notify_upload_result() is a no-op — the feature is opt-in and never blocks an upload.

Required env vars to enable:
    SMTP_HOST          e.g. smtp.gmail.com / smtp.office365.com / smtp-relay.brevo.com
    NOTIFY_EMAIL_TO    comma-separated recipient list, e.g. "a@company.com,b@company.com"

Optional env vars:
    SMTP_PORT          default 587
    SMTP_USERNAME       default: none (some internal relays allow unauthenticated send)
    SMTP_PASSWORD
    SMTP_FROM           default: SMTP_USERNAME, or "payroll-validator@localhost" if unset
    SMTP_USE_TLS        default "1" (STARTTLS); set to "0" to disable
"""
import os
import smtplib
from email.message import EmailMessage


def notify_upload_result(upload, critical_count, warning_count, detail_url):
    smtp_host = os.environ.get("SMTP_HOST")
    recipients_raw = os.environ.get("NOTIFY_EMAIL_TO")
    if not smtp_host or not recipients_raw:
        return

    if critical_count == 0 and warning_count == 0:
        return  # nothing worth interrupting anyone for

    recipients = [addr.strip() for addr in recipients_raw.split(",") if addr.strip()]
    if not recipients:
        return

    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_username = os.environ.get("SMTP_USERNAME")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    smtp_from = os.environ.get("SMTP_FROM") or smtp_username or "payroll-validator@localhost"
    use_tls = os.environ.get("SMTP_USE_TLS", "1") != "0"

    subject = f"[급여검증] {upload.client_name} {upload.payroll_month} - 오류 {critical_count}건 · 경고 {warning_count}건"

    lines = [
        f"{upload.client_name} {upload.payroll_month} 급여 검증이 완료되었습니다.",
        f"대상 인원: {upload.employee_count}명",
        "",
    ]
    if critical_count:
        lines.append(f"오류(CRITICAL): {critical_count}건")
    if warning_count:
        lines.append(f"경고(WARNING): {warning_count}건")
    lines.append("")
    lines.append(f"검증 상세 보기: {detail_url}")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg["To"] = ", ".join(recipients)
    msg.set_content("\n".join(lines))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            if use_tls:
                server.starttls()
            if smtp_username and smtp_password:
                server.login(smtp_username, smtp_password)
            server.send_message(msg)
    except Exception:
        pass  # a notification failure must never break the upload flow
