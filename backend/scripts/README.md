# Scripts Directory

このディレクトリには、beer_info バックエンドの補助スクリプトが含まれています。

## メインの操作は CLI から

通常の運用はプロジェクトルートから `cli.py` を使ってください：

```bash
# スクレイプ
uv run python -m backend.src.cli scrape

# Gemini エンリッチ
uv run python -m backend.src.cli enrich-gemini --limit 100

# Untappd エンリッチ
uv run python -m backend.src.cli enrich-untappd --limit 50

# ブルワリー情報更新
uv run python -m backend.src.cli enrich-breweries
```

## run_migration.py

Supabase に SQL マイグレーションを適用する手順を表示します。

```bash
uv run python -m backend.scripts.run_migration database/migrations/005_add_search_hint_fields.sql
```

## utils/ ディレクトリ（手動操作ツール）

| スクリプト | 用途 |
|---|---|
| `enrich_specific_url.py` | 特定の商品URLをGemini+Untappdでエンリッチ |
| `scrape_untappd_details.py` | 特定のUntappd URLから詳細をスクレイプ・保存 |
| `show_missing_untappd.py` | Untappd未リンクの商品一覧を表示 |
| `count_untappd_failures.py` | Untappd検索失敗の集計 |
| `view_data.py` | DB内データの確認 |
| `test_brewery_validation.py` | ブルワリー名バリデーションのデバッグ |
| `test_arome_detail.py` | Arome詳細スクレイプのデバッグ |
| `test_scrapers.py` | 各スクレイパーの動作確認 |
| `verify_priority.py` | Untappd検索優先度の検証 |
