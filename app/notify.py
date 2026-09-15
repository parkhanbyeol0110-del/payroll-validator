"""Upload-time alerts so staff don't have to open the dashboard to know something needs attention.

Currently supports Slack via an incoming webhook (SLACK_WEBHOOK_URL env var). If the env var
isn't set, notify_upload_result() is a no-op — the feature is opt-in and never blocks an upload.
"""
import json
import os
import urllib.request

SLACK_WEBHOOK_URL = "SLACK_WEBHOOK_URL"


def notify_upload_result(upload, critical_count, warning_count, detail_url):
    webhook = os.environ.get(SLACK_WEBHOOK_URL)
    if not webhook:
        return

    if critical_count == 0 and warning_count == 0:
        return  # nothing worth interrupting anyone for

    lines = [f"*{upload.client_name} {upload.payroll_month}* 급여 검증 완료 — 대상 {upload.employee_count}명"]
    if critical_count:
        lines.append(f":red_circle: 오류 {critical_count}건")
    if warning_count:
        lines.append(f":large_orange_circle: 경고 {warning_count}건")
    lines.append(f"<{detail_url}|검증 상세 보기>")

    payload = json.dumps({"text": "\n".join(lines)}).encode("utf-8")
    req = urllib.request.Request(webhook, data=payload, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass  # a notification failure must never break the upload flow
