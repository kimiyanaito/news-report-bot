"""GitHub Pages に HTML レポートを公開する。

GitHub Contents API を使って gh-pages ブランチの index.html を更新する。
更新後、https://<owner>.github.io/<repo>/ でレポートが閲覧できる。
"""

from __future__ import annotations

import base64
import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime

import pytz

from .config import timezone_name

log = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


def _github_token() -> str:
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise RuntimeError("環境変数 GITHUB_TOKEN が設定されていません")
    return token


def _github_repo() -> str:
    repo = os.environ.get("GITHUB_REPO", "")
    if not repo:
        raise RuntimeError("環境変数 GITHUB_REPO が設定されていません（例: kimiyanaito/news-report-bot）")
    return repo


def _api_request(method: str, path: str, body: dict | None = None) -> dict:
    """GitHub API にリクエストを送り、レスポンス JSON を返す。"""
    url = f"{GITHUB_API}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {_github_token()}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise RuntimeError(
            f"GitHub API エラー: status={e.code}, path={path}, body={error_body}"
        ) from e


def _get_file_sha(repo: str, path: str, branch: str) -> str | None:
    """ファイルの SHA を取得する。ファイルが存在しない場合は None を返す。"""
    try:
        result = _api_request("GET", f"/repos/{repo}/contents/{path}?ref={branch}")
        return result.get("sha")
    except RuntimeError as e:
        if "status=404" in str(e):
            return None
        raise


def _ensure_branch_exists(repo: str, branch: str) -> None:
    """ブランチが存在しなければ main/master から作成する。"""
    # ブランチ一覧を取得
    try:
        _api_request("GET", f"/repos/{repo}/git/ref/heads/{branch}")
        return  # 既に存在する
    except RuntimeError as e:
        if "status=404" not in str(e):
            raise

    # main ブランチの最新コミット SHA を取得
    for base in ("main", "master"):
        try:
            ref_data = _api_request("GET", f"/repos/{repo}/git/ref/heads/{base}")
            base_sha = ref_data["object"]["sha"]
            break
        except RuntimeError:
            continue
    else:
        raise RuntimeError("main または master ブランチが見つかりません")

    # 新しいブランチを作成
    _api_request("POST", f"/repos/{repo}/git/refs", {
        "ref": f"refs/heads/{branch}",
        "sha": base_sha,
    })
    log.info("ブランチ %s を作成しました", branch)


def publish(html: str) -> str:
    """HTML を GitHub Pages に公開し、閲覧用 URL を返す。"""
    repo = _github_repo()
    branch = "gh-pages"
    file_path = "index.html"

    _ensure_branch_exists(repo, branch)

    # 既存ファイルの SHA を取得（更新時に必要）
    sha = _get_file_sha(repo, file_path, branch)

    tz = pytz.timezone(timezone_name())
    now_str = datetime.now(tz).strftime("%Y-%m-%d %H:%M JST")

    # HTML を Base64 エンコード
    content_b64 = base64.b64encode(html.encode("utf-8")).decode("ascii")

    body: dict = {
        "message": f"Update news report ({now_str})",
        "content": content_b64,
        "branch": branch,
    }
    if sha:
        body["sha"] = sha  # ファイル更新時は既存 SHA が必要

    _api_request("PUT", f"/repos/{repo}/contents/{file_path}", body)

    # GitHub Pages URL を生成
    owner, repo_name = repo.split("/", 1)
    url = f"https://{owner}.github.io/{repo_name}/"
    log.info("GitHub Pages に公開しました: %s", url)
    return url
