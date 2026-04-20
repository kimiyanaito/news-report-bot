"""Jinja2 で HTML メール本文を生成する。"""

from __future__ import annotations

from datetime import datetime
from typing import List

import pytz
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import TEMPLATES_DIR, claude_model, timezone_name
from .models import GenreReport


_WEEKDAY_JA = ["月", "火", "水", "木", "金", "土", "日"]


def _now_jst() -> datetime:
    return datetime.now(pytz.timezone(timezone_name()))


def subject_line() -> str:
    now = _now_jst()
    wd = _WEEKDAY_JA[now.weekday()]
    return f"📰 朝のニュースレポート {now.strftime('%Y/%m/%d')}（{wd}）"


def _date_str() -> str:
    now = _now_jst()
    wd = _WEEKDAY_JA[now.weekday()]
    return f"{now.strftime('%Y年%m月%d日')}（{wd}）"


def _generated_at_str() -> str:
    return _now_jst().strftime("%Y-%m-%d %H:%M %Z")


def render_email(sections: List[GenreReport], subject: str) -> str:
    """2 ジャンル分の GenreReport から HTML メール本文を生成する。"""
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("news_email.html.j2")
    return template.render(
        subject=subject,
        date_str=_date_str(),
        sections=sections,
        generated_at=_generated_at_str(),
        model=claude_model(),
    )
