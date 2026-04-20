"""Gmail SMTP（アプリパスワード）でメールを送信する。"""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from .config import gmail_address, gmail_app_password, recipient_email

log = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465  # SSL


def send(subject: str, html_body: str, *, from_display_name: str = "News Report Bot") -> None:
    """HTML メールを送信する。DRY_RUN 判定は呼び出し側で行う。"""
    sender = gmail_address()
    recipient = recipient_email()

    msg = MIMEMultipart("alternative")
    msg["From"] = formataddr((from_display_name, sender))
    msg["To"] = recipient
    msg["Subject"] = subject

    # フォールバック用のプレーンテキスト（HTML のみクライアント対応のため）
    plain = "このメールは HTML 形式です。HTML 表示可能なメールクライアントでご覧ください。"
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    log.info("SMTP 接続: %s:%d (from=%s, to=%s)", SMTP_HOST, SMTP_PORT, sender, recipient)
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.login(sender, gmail_app_password())
        server.send_message(msg)
    log.info("メール送信完了: subject=%s", subject)
