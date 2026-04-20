"""環境変数 / prompts.yaml の読み込み。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List

import yaml
from dotenv import load_dotenv

from .models import GenreConfig


# --- ディレクトリ -----------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# プロジェクトルートの .env を自動読み込み（なければ無視）
# Railway 本番では環境変数が直接注入されるため影響なし
load_dotenv(PROJECT_ROOT / ".env", override=True)
CONFIG_DIR = PROJECT_ROOT / "config"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
OUT_DIR = PROJECT_ROOT / "out"


# --- env helpers ------------------------------------------------------------


def _env(name: str, default: str | None = None, required: bool = False) -> str | None:
    value = os.environ.get(name, default)
    if required and not value:
        raise RuntimeError(f"環境変数 {name} が設定されていません")
    return value


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# --- 設定値（モジュール読み込み時に評価しない: 関数経由で取得）---------


def anthropic_api_key() -> str:
    return _env("ANTHROPIC_API_KEY", required=True)  # type: ignore[return-value]


def claude_model() -> str:
    return _env("CLAUDE_MODEL", default="claude-sonnet-4-5")  # type: ignore[return-value]


def gmail_address() -> str:
    return _env("GMAIL_ADDRESS", required=True)  # type: ignore[return-value]


def gmail_app_password() -> str:
    return _env("GMAIL_APP_PASSWORD", required=True)  # type: ignore[return-value]


def recipient_email() -> str:
    return _env("RECIPIENT_EMAIL", required=True)  # type: ignore[return-value]


def timezone_name() -> str:
    return _env("TIMEZONE", default="Asia/Tokyo")  # type: ignore[return-value]


def dry_run() -> bool:
    return _env_bool("DRY_RUN", default=False)


def write_preview() -> bool:
    return _env_bool("WRITE_PREVIEW", default=False)


# --- prompts.yaml 読み込み --------------------------------------------------


def load_genres() -> List[GenreConfig]:
    """config/prompts.yaml から全ジャンル設定を読み込む。"""
    path = CONFIG_DIR / "prompts.yaml"
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    genres_raw = data.get("genres", [])
    genres: List[GenreConfig] = []
    for raw in genres_raw:
        genres.append(
            GenreConfig(
                key=str(raw["key"]),
                name=str(raw["name"]),
                emoji=str(raw.get("emoji", "")),
                prompt=str(raw["prompt"]),
            )
        )
    if not genres:
        raise RuntimeError("config/prompts.yaml に genres が定義されていません")
    return genres
