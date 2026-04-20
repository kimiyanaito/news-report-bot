"""Slack Incoming Webhook でニュースレポートの URL を通知する。"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

log = logging.getLogger(__name__)


def _webhook_url() -> str:
    url = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not url:
        raise RuntimeError("環境変数 SLACK_WEBHOOK_URL が設定されていません")
    return url


def notify(report_url: str, subject: str) -> None:
    """Slack にレポート URL を通知する。"""
    message = {
        "text": f"*{subject}*\n:newspaper: 本日のニュースレポートが届きました。\n<{report_url}|レポートを読む>",
    }

    payload = json.dumps(message).encode("utf-8")
    req = urllib.request.Request(
        _webhook_url(),
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    log.info("Slack 通知送信中: url=%s", report_url)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            log.info("Slack 通知完了: status=%d, response=%s", resp.status, body)
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise RuntimeError(f"Slack Webhook エラー: status={e.code}, body={error_body}") from e
