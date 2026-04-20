"""Claude Messages API の web_search ツールでニュースを収集する。"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any, List

import pytz
from anthropic import Anthropic

from .config import anthropic_api_key, claude_model, timezone_name
from .models import GenreConfig, NewsItem, Source

log = logging.getLogger(__name__)

# Claude ビルトインの web_search ツール
# https://docs.anthropic.com/en/docs/build-with-claude/tool-use/web-search
WEB_SEARCH_TOOL: dict[str, Any] = {
    "type": "web_search_20250305",
    "name": "web_search",
    "max_uses": 5,  # レートリミット対策（30k input tokens/分）
    "user_location": {
        "type": "approximate",
        "country": "JP",
        "timezone": "Asia/Tokyo",
    },
}

# ```json ... ``` のコードフェンスを抽出する正規表現
_JSON_FENCE_RE = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL)


def _today_jst_str() -> str:
    tz = pytz.timezone(timezone_name())
    return datetime.now(tz).strftime("%Y-%m-%d (%a)")


def _format_prompt(template: str) -> str:
    """prompts.yaml 内の {today_jst} プレースホルダを置換する。

    JSON 例に波括弧が多数含まれるため、`str.format` ではなく
    プレーンな `replace` で対応する。
    """
    return template.replace("{today_jst}", _today_jst_str())


def _collect_text(response: Any) -> str:
    """Claude レスポンスから JSON 配列を含む text ブロックを返す。

    web_search 使用時の content 構造:
      [text(前置き)?, server_tool_use, web_search_tool_result, ...繰り返し, text(最終回答)]

    ただし最後の text ブロックが短い散文（JSON なし）で終わることがある。
    そのため:
      1. ```json フェンスを含む text ブロックを優先して返す
      2. なければ "[" を含む text ブロックのうち最も長いものを返す
      3. それもなければ全 text ブロックを結合して返す（フォールバック）
    """
    texts: list[str] = []
    for block in getattr(response, "content", []):
        if getattr(block, "type", None) == "text":
            t = getattr(block, "text", "")
            if t:
                texts.append(t)

    if not texts:
        return ""

    # 優先1: ```json フェンスを含むブロック（後ろから探す）
    for t in reversed(texts):
        if "```json" in t:
            log.debug("JSON フェンスを含む text ブロックを使用 (len=%d)", len(t))
            return t

    # 優先2: "[" を含む最長のブロック
    candidates = [t for t in texts if "[" in t and "]" in t]
    if candidates:
        best = max(candidates, key=len)
        log.debug("JSON 配列候補の最長 text ブロックを使用 (len=%d)", len(best))
        return best

    # フォールバック: 全 text ブロックを結合
    joined = "\n\n".join(texts)
    log.debug("全 text ブロックを結合して使用 (len=%d)", len(joined))
    return joined


def _web_search_was_used(response: Any) -> bool:
    """web_search ツールが実際に呼び出されたか判定する。

    サーバーサイドツール実行時のブロック型:
      - server_tool_use      : Claude がツール呼び出しを発行したブロック
      - web_search_tool_result: 検索結果が返ってきたブロック
    これらが 1 つでもあれば検索済みと判定する。
    """
    for block in getattr(response, "content", []):
        block_type = getattr(block, "type", None)
        if block_type in ("server_tool_use", "web_search_tool_result"):
            return True
    return False


def _extract_json_array(text: str) -> list[dict]:
    """レスポンステキストから JSON 配列を抽出してパースする。

    優先順位:
        1. ```json ... ``` フェンス内の内容
        2. テキスト全体から最初の JSON 配列らしき部分
    """
    # 1. フェンス内を優先
    m = _JSON_FENCE_RE.search(text)
    if m:
        payload = m.group(1).strip()
        try:
            data = json.loads(payload)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError as e:
            log.warning("フェンス内 JSON のパースに失敗: %s", e)

    # 2. フォールバック: 最初の '[' から対応する ']' までを取り出して試す
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        try:
            data = json.loads(candidate)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError as e:
            log.warning("フォールバック JSON のパースに失敗: %s", e)

    raise ValueError("Claude レスポンスから JSON 配列を抽出できませんでした")


def _to_news_item(raw: dict) -> NewsItem | None:
    """1 要素 dict を NewsItem に変換。欠損時は None を返しスキップ。"""
    title = str(raw.get("title", "")).strip()
    summary = str(raw.get("summary", "")).strip()
    if not title or not summary:
        log.warning("title/summary が空の要素をスキップ: %s", raw)
        return None

    sources_raw = raw.get("sources") or []
    sources: list[Source] = []
    for s in sources_raw:
        if not isinstance(s, dict):
            continue
        name = str(s.get("name", "")).strip()
        url = str(s.get("url", "")).strip()
        if not name or not url:
            continue
        sources.append(Source(name=name, url=url))

    if not sources:
        log.warning("sources が空のニュースをスキップ: %s", title)
        return None

    return NewsItem(title=title, summary=summary, sources=sources)


_RETRY_SUFFIX = (
    "\n\n**追加指示（必読）**: あなたのトレーニングデータは古い可能性があります。"
    "必ず web_search ツールを複数回使って本日のニュースを実際に検索し、"
    "実在する URL を取得してから回答してください。"
    "検索なしに学習データだけで回答することは厳禁です。"
)


def _call_claude(
    client: Anthropic,
    genre_key: str,
    prompt: str,
    *,
    force_tool: bool = False,
) -> Any:
    """Claude API を呼び出して response を返す。"""
    kwargs: dict[str, Any] = dict(
        model=claude_model(),
        max_tokens=16000,
        tools=[WEB_SEARCH_TOOL],
        messages=[{"role": "user", "content": prompt}],
    )
    if force_tool:
        # tool_choice=any で web_search の使用を強制
        kwargs["tool_choice"] = {"type": "any"}

    log.info(
        "[%s] Claude API 呼び出し開始 (model=%s, force_tool=%s)",
        genre_key,
        claude_model(),
        force_tool,
    )
    return client.messages.create(**kwargs)


def research_genre(genre: GenreConfig) -> List[NewsItem]:
    """1 ジャンル分のニュースを Claude で収集する。"""
    client = Anthropic(api_key=anthropic_api_key())
    prompt = _format_prompt(genre.prompt)

    # 1st attempt（tool_choice は auto = デフォルト）
    response = _call_claude(client, genre.key, prompt, force_tool=False)
    log.info(
        "[%s] Claude API 応答 (stop_reason=%s, content blocks=%d)",
        genre.key,
        getattr(response, "stop_reason", "?"),
        len(getattr(response, "content", []) or []),
    )

    # web_search が使われなかった場合はリトライ
    if not _web_search_was_used(response):
        log.warning(
            "[%s] web_search が使われませんでした（学習データで回答した可能性）。"
            "tool_choice=any + 強化プロンプトでリトライします。",
            genre.key,
        )
        response = _call_claude(
            client,
            genre.key,
            prompt + _RETRY_SUFFIX,
            force_tool=True,
        )
        log.info(
            "[%s] リトライ応答 (stop_reason=%s, content blocks=%d)",
            genre.key,
            getattr(response, "stop_reason", "?"),
            len(getattr(response, "content", []) or []),
        )
        if not _web_search_was_used(response):
            log.warning("[%s] リトライ後も web_search が使われませんでした。", genre.key)

    text = _collect_text(response)
    if not text:
        raise RuntimeError(f"[{genre.key}] Claude からテキストが返ってきませんでした")

    raw_items = _extract_json_array(text)
    log.info("[%s] JSON パース成功: %d 件", genre.key, len(raw_items))

    items: list[NewsItem] = []
    for raw in raw_items:
        item = _to_news_item(raw) if isinstance(raw, dict) else None
        if item is not None:
            items.append(item)

    if not items:
        raise RuntimeError(f"[{genre.key}] 有効なニュース記事が 1 件も抽出できませんでした")

    log.info("[%s] 収集完了: %d 件", genre.key, len(items))
    for i, it in enumerate(items, 1):
        source_str = " | ".join(f"{s.name}" for s in it.sources)
        log.info("  %2d. %s  [%s]", i, it.title, source_str)

    return items
