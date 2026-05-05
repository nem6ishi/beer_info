# Untappd エンリッチメント (enrich-untappd) の使用方法

`enrich-untappd` は、データベース上のビール情報に対して Untappd からのデータを取得・紐付け（エンリッチメント）するための CLI コマンドです。

## 概要
主な機能として、まだ Untappd の URL が紐付いていないビールに対して検索を行う **`missing` モード** と、既に URL が紐付いているビールのレーティングや ABV などの詳細情報を再取得する **`refresh` モード** の2つが提供されています。

## 基本的な実行コマンド

プロジェクトルートディレクトリから `uv run` を使用して実行します。

```bash
# 基本的な実行（デフォルトでは limit=50, mode=missing）
uv run python -m backend.src.cli enrich-untappd

# モードやリミットを指定して実行
uv run python -m backend.src.cli enrich-untappd --mode missing --limit 100

# リフレッシュモードでの実行
uv run python -m backend.src.cli enrich-untappd --mode refresh
```

## オプション引数

| 引数 | 型 | デフォルト | 説明 |
|---|---|---|---|
| `--limit` | `int` | `50` | 1回の実行で処理するビールの最大件数。APIレートリミットを考慮して調整します。 |
| `--mode` | `str` | `missing` | 実行モード。`missing` (未紐付けデータの検索) または `refresh` (既存データ情報の更新) を指定します。 |
| `--shop` | `str` | `None` | 特定のショップ（販売店）に絞り込んで処理を実行します。 |
| `--name_filter` | `str` | `None` | ビール名（部分一致）で絞り込んで処理を実行します。デバッグ時などに便利です。 |

### 実行例

**特定のショップの未リンクビールを 20 件だけ処理する:**
```bash
uv run python -m backend.src.cli enrich-untappd --mode missing --shop "ちょうせいや" --limit 20
```

**名前に "IPA" が含まれる既存ビールの情報を更新する:**
```bash
uv run python -m backend.src.cli enrich-untappd --mode refresh --name_filter "IPA"
```

## 動作の詳細 (モード別)

### 1. `missing` モード
Untappd URL が紐付いていない（または `search?` を含むダミーURL）データに対して Untappd を検索し、リンクを行います。

- **処理フロー:**
  1. `gemini_data` テーブルにキャッシュされた URL がないか確認。
  2. Untappd サイトでの直接検索を実行。
  3. 検索失敗(`no_results`)の場合は、Gemini API を使用して検索クエリの代替案（Two-pass retry）を生成し、再検索を実行。
  4. 検索結果が得られた場合、詳細情報をスクレイピングし、`untappd_data`, `gemini_data`, `scraped_beers` を更新。
  5. 失敗した場合はエラーログ(`untappd_search_failures`)に記録されます（連続失敗の場合は一定期間スキップされるバックオフ制御あり）。

### 2. `refresh` モード
既に正しい Untappd URL が紐付いているデータについて、情報の更新（レーティング、ABVなど）を行います。

- **対象データ:**
  - `stock_status` が "Sold Out" でない。
  - 前回の取得 (`untappd_fetched_at`) から **5日以上** 経過しているもの。
- 該当する URL へ直接アクセスしてスクレイピングを行い、`untappd_data` を最新の状態に書き換えます。

## 関連コマンド

単体で `enrich-untappd` を実行するほかに、統合エンリッチメントコマンドを使用することで、Gemini解析 → Untappd検索 → ブルワリー情報取得 のパイプラインを一括で実行できます。

```bash
# 全パイプラインの実行
uv run python -m backend.src.cli enrich --limit 50
```
