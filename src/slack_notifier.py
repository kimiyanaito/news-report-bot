"""Slack chat.postMessage でニュースレポートの URL を通知する。

Personal-bot 統合 (2026-05-13) で Incoming Webhook → Bot Token 方式に切り替え。
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

log = logging.getLogger(__name__)

_SLACK_POST_URL = "https://slack.com/api/chat.postMessage"


def _bot_token() -> str:
    token = os.environ.get("SLACK_BOT_TOKEN", "")
    if not token:
        raise RuntimeError("環境変数 SLACK_BOT_TOKEN が設定されていません")
    return token


def _channel_id() -> str:
    cid = os.environ.get("SLACK_CHANNEL_ID", "")
    if not cid:
        raise RuntimeError("環境変数 SLACK_CHANNEL_ID が設定されていません")
    return cid


def notify(report_url: str, subject: str) -> None:
    """Slack にレポート URL を通知する。"""
    payload = {
        "channel": _channel_id(),
        "text": f"*{subject}*\n:newspaper: 本日のニュースレポートが届きました。\n<{report_url}|レポートを読む>",
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        _SLACK_POST_URL,
        data=body,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {_bot_token()}",
        },
        method="POST",
    )

    log.info("Slack 通知送信中: url=%s", report_url)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_body = resp.read().decode("utf-8")
            data = json.loads(resp_body)
            if not data.get("ok"):
                raise RuntimeError(f"Slack API エラー: {data}")
            log.info("Slack 通知完了: ts=%s", data.get("ts"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise RuntimeError(f"Slack HTTP エラー: status={e.code}, body={error_body}") from e
