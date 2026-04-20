"""データモデル定義。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class Source:
    """ニュース記事の情報源（媒体 + URL）。"""

    name: str
    url: str


@dataclass
class NewsItem:
    """1 件のニュース記事。"""

    title: str
    summary: str
    sources: List[Source] = field(default_factory=list)


@dataclass
class GenreConfig:
    """prompts.yaml の 1 ジャンル分の設定。"""

    key: str        # 例: "finance"
    name: str       # 例: "国内外の金融・マクロ経済ニュース"
    emoji: str      # 例: "💹"
    prompt: str     # Claude に渡すプロンプト本文（{today_jst} などを含む）


@dataclass
class GenreReport:
    """1 ジャンル分のレポート（ジャンル設定 + 収集結果）。"""

    config: GenreConfig
    items: List[NewsItem]
