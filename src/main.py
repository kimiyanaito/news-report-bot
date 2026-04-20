"""エントリーポイント。Railway cron から 1 回実行され、完了したら exit する。"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import List

from . import email_sender, renderer
from .config import OUT_DIR, dry_run, write_preview
from .config import load_genres
from .models import GenreConfig, GenreReport
from .researcher import research_genre


# --- logging ----------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("news-report-bot")


# --- helpers ----------------------------------------------------------------


_GENRE_INTERVAL_SEC = 90  # ジャンル間のウェイト（レートリミット対策）


def _fetch_sequential(genres: List[GenreConfig]) -> List[GenreReport]:
    """ジャンルを順次リサーチする。

    並列実行すると 2 リクエストが同時に走り 30,000 input tokens/分 の
    レートリミットを超えやすいため、順次実行 + ジャンル間にウェイトを設けた。
    1 日 1 回の朝 6 時実行なので所要時間の増加は問題なし。
    """
    import time

    reports: List[GenreReport] = []
    for idx, g in enumerate(genres):
        if idx > 0:
            log.info("レートリミット対策: %d 秒ウェイト中...", _GENRE_INTERVAL_SEC)
            time.sleep(_GENRE_INTERVAL_SEC)
        try:
            items = research_genre(g)
            reports.append(GenreReport(config=g, items=items))
        except Exception as e:
            log.exception("[%s] リサーチ失敗: %s", g.key, e)
            raise
    return reports


def _write_preview_file(html: str) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / "preview.html"
    path.write_text(html, encoding="utf-8")
    return path


# --- main -------------------------------------------------------------------


def run_once() -> int:
    log.info("=== news-report-bot start (dry_run=%s) ===", dry_run())
    try:
        genres = load_genres()
        log.info("対象ジャンル: %s", [g.key for g in genres])

        sections = _fetch_sequential(genres)

        subject = renderer.subject_line()
        html = renderer.render_email(sections, subject)
        log.info("HTML 生成完了: %d bytes", len(html))

        if write_preview():
            path = _write_preview_file(html)
            log.info("プレビュー HTML を書き出しました: %s", path)

        if dry_run():
            log.info("DRY_RUN=true のためメール送信はスキップします（subject=%s）", subject)
        else:
            email_sender.send(subject, html)

        log.info("=== news-report-bot done ===")
        return 0

    except Exception as e:
        log.exception("ジョブ失敗: %s", e)
        # エラー時もエラーメールで気づけるようにする（DRY_RUN と、SMTP 設定不備は除く）
        if not dry_run():
            try:
                err_html = (
                    f"<h3>news-report-bot ジョブ失敗</h3>"
                    f"<p>例外: <code>{type(e).__name__}</code></p>"
                    f"<pre style='white-space:pre-wrap'>{e}</pre>"
                )
                email_sender.send("⚠️ ニュースレポート生成失敗", err_html)
            except Exception as inner:  # noqa: BLE001
                log.exception("エラー通知メールの送信にも失敗: %s", inner)
        return 1


if __name__ == "__main__":
    sys.exit(run_once())
