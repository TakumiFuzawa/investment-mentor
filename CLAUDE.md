# AI投資メンター（Investment Mentor） - プロジェクト設計書

## プロジェクト概要

投資・経済・市場を体系的に学ぶための、ローカル動作のAI家庭教師Webアプリ。
「四季報を読む時間がない会社員が、スキマ時間30分で投資知識を積み上げる」ことを目的とする。

---

## ユーザー情報

- 年齢：27歳・会社員
- 投資知識：ほぼゼロ（PER・PBRも曖昧）
- 利用時間：スキマ時間に合計30分/日
- 動作環境：Windows・ローカル・非公開
- 目的：投資実行ツールではなく「学習・理解」が主目的

---

## 技術スタック

| カテゴリ | 採用技術 | バージョン |
|---------|---------|---------|
| 言語 | Python | 3.11以上 |
| UI | Streamlit | 最新安定版 |
| AIエンジン | Claude API (claude-sonnet-4-20250514) | - |
| 株価・指数データ | yfinance | 最新安定版 |
| ニュース取得 | NewsAPI | v2 |
| データ保存 | SQLite + JSON | - |
| 環境変数管理 | python-dotenv | - |
| ロギング | loguru | - |
| テスト | pytest | - |
| パッケージ管理 | uv | - |

---

## フォルダ構成

```
investment-mentor/
├── CLAUDE.md                  # 本設計書（Claude Codeへの指示書）
├── .env                       # APIキー（Gitに含めない）
├── .env.example               # APIキーのサンプル（Gitに含める）
├── .gitignore
├── requirements.txt
├── README.md
│
├── app.py                     # Streamlitメインエントリーポイント
│
├── pages/                     # Streamlit マルチページ
│   ├── 1_briefing.py          # 今日のブリーフィング
│   ├── 2_chat.py              # メンターチャット
│   ├── 3_roadmap.py           # 学習ロードマップ
│   └── 4_notes.py             # 学習ノート
│
├── core/                      # ビジネスロジック層
│   ├── __init__.py
│   ├── claude_client.py       # Claude API wrapper
│   ├── market_data.py         # yfinance wrapper + バリデーション
│   ├── news_client.py         # ニュース取得 + フィルタリング
│   └── prompts.py             # システムプロンプト定義
│
├── db/                        # データ永続化層
│   ├── __init__.py
│   ├── database.py            # SQLite接続・初期化
│   ├── chat_repository.py     # 会話履歴CRUD
│   ├── progress_repository.py # 学習進捗CRUD
│   └── notes_repository.py    # 学習ノートCRUD
│
├── curriculum/                # カリキュラム定義
│   └── stages.json            # 学習ステージ・クイズデータ
│
├── data/                      # SQLiteファイル保存場所
│   └── mentor.db              # メインDB（Gitに含めない）
│
├── logs/                      # ログ出力先
│   └── app.log                # アプリログ（Gitに含めない）
│
└── tests/                     # テストコード
    ├── __init__.py
    ├── test_market_data.py
    ├── test_news_client.py
    ├── test_claude_client.py
    └── test_database.py
```

---

## 機能仕様

### 1. 今日のブリーフィング（pages/1_briefing.py）

**目的：** 朝5〜10分で市場の状況と今日の学習テーマを把握する

**表示内容：**
- 主要指数の前日終値と変動率
  - 日経平均（^N225）
  - S&P500（^GSPC）
  - ドル円（USDJPY=X）
  - NASDAQ（^IXIC）
- 経済ニュース3本（信頼ソース限定・AI要約付き）
- 「今日の学習テーマ」AIからの提案（学習進捗連動）
- 市場データ取得日時・免責表示

**データ取得ルール：**
- 数値データはyfinanceから取得（AIに生成させない）
- ニュース要約のみClaudeを使用
- データ取得失敗時はエラーメッセージ表示（フォールバック必須）

---

### 2. メンターチャット（pages/2_chat.py）

**目的：** 投資・経済・市場についてなんでも質問できるAI家庭教師

**機能：**
- チャット形式の対話UI
- 会話履歴をSQLiteに保存（セッションをまたいで継続）
- ユーザーの学習レベル・進捗を会話に反映
- 免責表示を会話UI内に常時表示

**Claudeへの制約（システムプロンプトで制御）：**
- 投資アドバイス・具体的な銘柄推奨は行わない
- 「これは学習目的の解説です」を明示する
- 初心者向けに専門用語は必ず平易な言葉で補足
- 回答の最後に「次に学ぶべきこと」を提案する
- 数値・データは「yfinanceで確認してください」と誘導する

---

### 3. 学習ロードマップ（pages/3_roadmap.py）

**目的：** 体系的な学習カリキュラムと進捗管理

**カリキュラム構成（curriculum/stages.json）：**

```
STAGE 1: 投資の基礎（目安：2週間）
  1-1. お金と投資の違い
  1-2. 株式とは何か
  1-3. 債券・投資信託・ETFの違い
  1-4. PER・PBR・配当利回りとは
  1-5. 財務諸表の基本（BS・PL・CF）
  ※各テーマにミニクイズ3問付き

STAGE 2: 市場を知る（目安：2週間）
  2-1. 日本市場の構造（東証・プライム・スタンダード）
  2-2. 米国市場との違い（NYSE・NASDAQ）
  2-3. 主要経済指標（GDP・CPI・雇用統計）
  2-4. 金利と株価の関係
  2-5. 為替と株価の関係

STAGE 3: 企業分析の基本（目安：3週間）
  3-1. 四季報の読み方
  3-2. 業績・売上・利益の見方
  3-3. セクター分析
  3-4. 競合比較の方法
  3-5. 割安・割高の判断基準

STAGE 4: マクロ経済（目安：3週間）
  4-1. 金融政策（日銀・FRB）
  4-2. 財政政策と市場への影響
  4-3. 景気サイクルと投資戦略
  4-4. インフレ・デフレと資産運用
  4-5. グローバル経済の連動性

STAGE 5: 投資戦略の基礎（目安：2週間）
  5-1. 長期投資 vs 短期投資
  5-2. 分散投資の考え方
  5-3. ポートフォリオ構築の基本
  5-4. リスク管理の基本
  5-5. インデックス投資 vs 個別株
```

**進捗管理：**
- 各テーマの完了チェック
- ミニクイズの正答率記録
- 現在のステージ・達成率をプログレスバーで表示
- 「次に取り組むべきテーマ」の自動サジェスト

---

### 4. 学習ノート（pages/4_notes.py）

**目的：** チャットで学んだことの自動記録と振り返り

**機能：**
- チャットの重要なやり取りを自動でノート化
- 手動でメモを追加できる
- 週次・月次の学習サマリー表示
- キーワード検索

---

## データベース設計

### テーブル定義

```sql
-- 会話履歴
CREATE TABLE chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,           -- 'user' or 'assistant'
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 学習進捗
CREATE TABLE learning_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stage_id TEXT NOT NULL,       -- 例: '1-1', '1-2'
    status TEXT NOT NULL,         -- 'not_started', 'in_progress', 'completed'
    quiz_score INTEGER,           -- クイズ正答数
    quiz_total INTEGER,           -- クイズ総問数
    completed_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 学習ノート
CREATE TABLE notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT,                  -- 'chat' or 'manual'
    tags TEXT,                    -- JSON配列形式
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 市場データキャッシュ（API節約用）
CREATE TABLE market_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    data TEXT NOT NULL,           -- JSON形式
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## APIキー・環境変数

### .env.example（このファイルはGitに含める）

```
# Anthropic API Key
# 取得先: https://console.anthropic.com
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# NewsAPI Key
# 取得先: https://newsapi.org
# 無料枠: 100リクエスト/日
NEWS_API_KEY=your_newsapi_key_here

# アプリ設定
APP_ENV=development              # development / production
LOG_LEVEL=INFO
CACHE_EXPIRE_MINUTES=30          # 市場データキャッシュ有効期限
```

---

## データ品質・バリデーション方針

### 大原則

```
数値データ → yfinanceから取得（AIに絶対に生成させない）
解説・要約 → Claude（「学習目的」の免責付き）
ニュース   → 信頼ソース限定（下記リスト）
```

### 信頼できるニュースソース

```python
TRUSTED_NEWS_SOURCES = [
    "reuters.com",
    "bloomberg.com",
    "nikkei.com",
    "boj.or.jp",       # 日本銀行
    "mof.go.jp",       # 財務省
    "federalreserve.gov",  # FRB
]
```

### バリデーションルール

```python
# 株価データ
- データがNoneまたは空 → エラー表示・再取得促す
- 価格が0以下          → 異常値フラグ
- 前日比±30%超        → 「異常な変動」警告表示
- キャッシュ30分超     → 再取得

# ニュース
- 信頼ソース外のドメイン → 除外
- 取得失敗              → 「ニュース取得できませんでした」表示

# Claude API
- タイムアウト（30秒）  → リトライ×2回 → エラー表示
- レスポンスが空        → エラー表示
```

---

## エラーハンドリング方針

- すべてのAPI呼び出しはtry-exceptで囲む
- エラーはloguru でログ記録（logs/app.log）
- UIには技術的なエラー詳細を表示しない（「データを取得できませんでした」等）
- アプリ全体がクラッシュしないこと（部分的な失敗は許容）

---

## セキュリティ方針

- APIキーは.envファイルのみで管理・コードに直書き禁止
- .env・data/・logs/ は.gitignoreに追加
- WebDAVアクセス禁止（Windows環境）
- ユーザー入力はそのままClaudeに渡す前にサニタイズ（最大2000文字制限）

---

## UI・デザイン方針

- フレームワーク：Streamlit（ローカル動作）
- テーマ：ダークモード推奨（金融ダッシュボードらしい見た目）
- 免責表示：全ページのフッターに常時表示
  ```
  ⚠️ このアプリは学習目的のみです。投資判断は自己責任で行ってください。
  ```
- エラー・警告はst.warningで目立つように表示
- データの取得日時を必ず表示（情報の鮮度を明示）

---

## 実装フェーズ（開発順序）

Claude Codeへの指示は以下の順番で行うこと：

```
Phase 2-1: 環境構築
  - フォルダ構成作成
  - requirements.txt作成
  - .env.example作成
  - .gitignore作成
  - loguru初期設定

Phase 2-2: データ取得層（最重要・最初に完成させる）
  - core/market_data.py（yfinance + バリデーション）
  - core/news_client.py（NewsAPI + フィルタリング）
  - tests/test_market_data.py
  - tests/test_news_client.py

Phase 2-3: データベース層
  - db/database.py（SQLite初期化・マイグレーション）
  - db/chat_repository.py
  - db/progress_repository.py
  - db/notes_repository.py
  - tests/test_database.py

Phase 2-4: Claude連携層
  - core/prompts.py（システムプロンプト定義）
  - core/claude_client.py（API wrapper）
  - tests/test_claude_client.py

Phase 2-5: カリキュラムデータ
  - curriculum/stages.json（全ステージ・クイズデータ）

Phase 2-6: 画面実装
  - app.py（メインエントリー・サイドバー）
  - pages/1_briefing.py
  - pages/2_chat.py
  - pages/3_roadmap.py
  - pages/4_notes.py

Phase 3: テスト・品質確認
  - pytest 全テスト実行
  - データ品質チェック（異常値・空データ）
  - UI動作確認チェックリスト

Phase 4: 試験運用
  - 1週間使ってみてフィードバック収集
  - バグ・改善点をISSUE形式でメモ
```

---

## Claude Codeへの指示テンプレート

### Phase開始時

```
CLAUDE.mdを読んでください。
[Phase X-X]の実装を開始してください。
- 設計書の方針を厳守してください
- エラーハンドリングとバリデーションを必ず含めてください
- テストコードも同時に作成してください
- 実装が完了したら次のPhaseを提案してください
```

### エラー発生時

```
以下のエラーが発生しました。CLAUDE.mdの設計方針を守りながら修正してください。

[エラー内容をここに貼り付け]

修正後、同様のエラーが他の箇所で起きないか確認してください。
```

### レビュー依頼時

```
[ファイル名]のコードレビューをしてください。
確認項目：
1. CLAUDE.mdの設計方針と一致しているか
2. セキュリティ上の問題がないか
3. エラーハンドリングが適切か
4. バリデーションが漏れていないか
```

---

## 免責・注意事項（アプリ内表示用）

```
【重要】このアプリについて
・本アプリは投資教育・学習を目的としています
・AIの解説は学習補助であり、投資アドバイスではありません
・表示される市場データは最大15〜30分の遅延があります
・投資判断は必ずご自身の責任で行ってください
・データの正確性を保証するものではありません
```

---

*最終更新：プロジェクト開始時*
*設計者：本人 + Claude*
