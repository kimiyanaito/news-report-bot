# news-report-bot — Claude Code 引き継ぎドキュメント

## プロジェクト概要

Claude API のビルトイン Web 検索ツールを使って「国内外の金融・マクロ経済」と「国際政治」の重要ニュースを毎朝 06:00 JST に収集し、
HTML メールを Gmail SMTP で `n-kimiya@keio.jp` に配信する Bot。
Railway の Cron 機能で 1 日 1 回だけ起動 → 完了したら自動停止。

## リポジトリ

- **ローカルパス**: `/Users/kimiya/Claude/news-report-bot`
- **GitHub**: `kimiyanaito/news-report-bot`（要新規作成, private）
- **デプロイ先**: Railway（`main` ブランチへの push で自動デプロイ）

---

## システム構成

### 処理フロー

```
[Railway Cron: 毎日 21:00 UTC = 06:00 JST]
  ├─ src/main.py 起動
  ├─ config/prompts.yaml から 2 ジャンルを読み込み
  ├─ 2 ジャンル並列で Claude API を呼び出し
  │   ├─ model = claude-sonnet-4-5（環境変数で上書き可）
  │   ├─ tool  = web_search_20250305（max_uses=15, country=JP）
  │   └─ レスポンス末尾の ```json フェンスを抽出 → NewsItem にパース
  ├─ Jinja2 で HTML メール本文を生成
  ├─ Gmail SMTP (smtp.gmail.com:465 SSL) で送信
  └─ exit 0
```

### ファイル構成

| ファイル | 役割 |
|---|---|
| `src/main.py` | エントリーポイント（1 回実行で exit, エラー時はエラーメール通知） |
| `src/config.py` | 環境変数 / `config/prompts.yaml` 読み込み |
| `src/researcher.py` | Claude API + web_search ツール呼び出し・JSON 抽出 |
| `src/renderer.py` | Jinja2 で HTML メール生成, 件名生成 |
| `src/email_sender.py` | Gmail SMTP_SSL で送信 |
| `src/models.py` | `Source` / `NewsItem` / `GenreConfig` / `GenreReport` dataclass |
| `config/prompts.yaml` | 2 ジャンルのリサーチプロンプト（`{today_jst}` プレースホルダあり） |
| `templates/news_email.html.j2` | HTML メールテンプレ（Gmail 対応インライン CSS） |
| `Dockerfile` | `python:3.12-slim` ベース（Playwright 不要） |
| `Procfile` | `worker: python -m src.main` |
| `railway.json` | Railway Cron schedule（`0 21 * * *` = 06:00 JST） |
| `requirements.txt` | anthropic / pyyaml / jinja2 / pytz / python-dateutil |
| `.env.example` | 必須環境変数のサンプル |

---

## 環境変数（Railway Variables）

| 変数名 | 必須 | 内容 |
|---|---|---|
| `ANTHROPIC_API_KEY` | ○ | https://console.anthropic.com/ で発行 |
| `GMAIL_ADDRESS` | ○ | 送信元 Gmail アドレス |
| `GMAIL_APP_PASSWORD` | ○ | https://myaccount.google.com/apppasswords で発行した 16 桁 |
| `RECIPIENT_EMAIL` | ○ | `n-kimiya@keio.jp` |
| `CLAUDE_MODEL` | | 既定 `claude-sonnet-4-5` |
| `TIMEZONE` | | 既定 `Asia/Tokyo` |
| `DRY_RUN` | | `true` でメール送信せずログのみ |
| `WRITE_PREVIEW` | | `true` で `out/preview.html` にプレビューを書き出し（ローカル検証用） |

---

## 初回セットアップ手順

### 1. Gmail アプリパスワード発行

1. Google アカウント → **セキュリティ** → **2 段階認証プロセス** を有効化
2. 同ページ下部 or https://myaccount.google.com/apppasswords から
   「アプリ パスワード」を発行（アプリ名は任意で「news-report-bot」等）
3. 16 桁の文字列が表示されるので `GMAIL_APP_PASSWORD` に設定

### 2. Anthropic API キー発行

1. https://console.anthropic.com/ → **API Keys** → Create Key
2. `ANTHROPIC_API_KEY` に設定

### 3. ローカル dry-run（Claude 呼び出しまで、メール送信なし）

```bash
cd /Users/kimiya/Claude/news-report-bot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export ANTHROPIC_API_KEY="sk-ant-..."
export GMAIL_ADDRESS="dummy@example.com"       # DRY_RUN 時も env 必須
export GMAIL_APP_PASSWORD="dummy"
export RECIPIENT_EMAIL="n-kimiya@keio.jp"
export DRY_RUN=true
export WRITE_PREVIEW=true

python -m src.main
open out/preview.html   # 生成された HTML を Safari 等で確認
```

ログに 2 ジャンル × 5〜10 本のニュースタイトルが出れば OK。

### 4. ローカル本送信テスト

```bash
export DRY_RUN=false
# GMAIL_ADDRESS / GMAIL_APP_PASSWORD に本物の値を入れる
python -m src.main
```

`n-kimiya@keio.jp` にメールが届けば OK。

### 5. GitHub リポ作成 & push

```bash
cd /Users/kimiya/Claude/news-report-bot
git init
git add .
git commit -m "init"
gh repo create kimiyanaito/news-report-bot --private --source=. --push
```

### 6. Railway デプロイ

1. https://railway.app/new → **Deploy from GitHub repo** → `kimiyanaito/news-report-bot`
2. 作成された service の **Variables** タブで上表の env を登録
3. **Settings** タブで Cron Schedule が `0 21 * * *` になっていることを確認
   （`railway.json` が自動反映される想定。されない場合は UI で直接設定）
4. Restart Policy: **Never**（cron で 1 回実行して停止するのが正）
5. 最初の build が成功したらデプロイ完了

### 7. Railway 上での動作確認

- Railway service の **Deployments** → 最新デプロイ → **Run Now** で 1 回手動実行
  （※ UI に「Run Now」が無い環境では、一旦 `railway.json` の `cronSchedule` を
  直近の時刻に変更 → push → 起動確認 → 元に戻す）
- ログで `Claude API 応答` → `メール送信完了` が流れていることを確認
- `n-kimiya@keio.jp` にメールが届くことを確認

### 8. 翌朝 06:00 JST の自動配信確認

- Railway ログで 21:00 UTC に起動 → 数分で正常終了していることを確認
- メール受信を確認

---

## 検証方法（エンドツーエンド）

| 検証項目 | 方法 |
|---|---|
| prompts.yaml 読み込み | `python -c "from src.config import load_genres; print([g.key for g in load_genres()])"` → `['finance', 'politics']` |
| テンプレレンダリング | `DRY_RUN=true WRITE_PREVIEW=true` でローカル実行 → `out/preview.html` を開く |
| Claude API 呼び出し | DRY_RUN ログに `[finance] 収集完了: N 件` / `[politics] 収集完了: N 件` |
| 複数ソース引用 | 生成 HTML 内に同じ記事で複数のソースバッジが付いているか目視 |
| Gmail SMTP 送信 | 本送信後、受信トレイで件名 `📰 朝のニュースレポート YYYY/MM/DD（曜）` を確認 |
| Railway Cron 発火 | Railway ログに日次で `=== news-report-bot start ===` が記録される |

---

## デプロイ

```bash
git add .
git commit -m "..."
git push origin main   # Railway が自動デプロイ
```

---

## よくあるエラーと対処

| エラー | 原因 | 対処 |
|---|---|---|
| `環境変数 XXX が設定されていません` | Railway Variables の登録漏れ | Railway UI で env を追加 → redeploy |
| `Claude レスポンスから JSON 配列を抽出できませんでした` | Claude が ```json フェンスを付けずに返した | `config/prompts.yaml` のフォーマット指示を強化、または `src/researcher.py::_extract_json_array` のフォールバックを拡張 |
| `sources が空のニュースをスキップ` | Claude がソース情報を落とした | プロンプトの「同じ事象は複数ソース併記、最低 1 つ」を強調 |
| `smtplib.SMTPAuthenticationError` | アプリパスワード誤り / 2 段階認証未有効 | 手順 1 をやり直す |
| `anthropic.RateLimitError` | API のレート上限 | `CLAUDE_MODEL` を下位モデルに変更 or Anthropic の上限引き上げ |
| Railway Cron が発火しない | `railway.json` の cronSchedule が読み込まれていない | Railway UI の Settings で手動設定（`0 21 * * *`） |

---

## 将来の拡張メモ

- **代替 UI**: 要件では「メール以外が難しい場合に代替を提案」とされていたが今回はメールのみ採用。
  将来 Slack / Discord / LINE に追加配信したくなった場合は、
  `src/email_sender.py` と同形式で `src/slack_notifier.py` 等を追加し、
  `src/main.py` の `run_once()` で順に呼び出すだけで対応可能。
- **ジャンル追加**: `config/prompts.yaml` に genre を足すだけで本数に制限なし。
- **過去ログ蓄積**: `out/` に JSON / HTML を書き出して GitHub リポに push するワークフローを
  足せば、過去のレポートを検索可能な形で蓄積できる。
