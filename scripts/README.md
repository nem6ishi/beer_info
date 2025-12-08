# スクレイパースクリプト（Supabase版）

このディレクトリには、ビールデータの収集とエンリッチメントをSupabaseデータベースに対して実行するためのスクリプトが含まれています。

## 📋 スクリプト一覧

### 1. `scrape.py` - スクレイピング（Supabase）
基本的なビール情報（名前、価格、在庫状況など）をショップからスクレイピングし、Supabaseに保存します。

```bash
# 全ショップをスクレイピング
python -m app.cli scrape

# テスト用（各ショップ10件まで）
python -m app.cli scrape --limit 10
```

**処理内容**:
- 3つのショップから並列スクレイピング
- Supabaseの既存データと照合
- 新規ビール・更新・再入荷を自動検出
- `beers`テーブルに直接保存

**環境変数**:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`

---

### 2. `enrich_gemini.py` - Geminiエンリッチメント（Supabase）
Supabase内のビールデータに対して、Gemini APIでブルワリー名とビール名を抽出します。

```bash
# Gemini enrichmentが未処理のビールを処理
python -m app.cli enrich-gemini --limit 50
```

**処理内容**:
- `brewery_name_en/jp`がnullのビールを自動抽出
- 既知のブルワリーデータベースをヒントとして使用
- Gemini APIでブルワリー名・ビール名を抽出
- Supabaseに直接保存

**環境変数**:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `GEMINI_API_KEY`

**レート制限**: 15-20 RPM（自動調整）

---

### 3. `enrich_untappd.py` - Untappdエンリッチメント（Supabase）
Gemini enrichmentが完了したビールに対して、Untappd情報を追加します。

```bash
# Geminiデータはあるがuntappd_urlがないビールを処理
python -m app.cli enrich-untappd --limit 50
```

**処理内容**:
- `brewery_name_en/jp`があり、`untappd_url`がnullのビールを自動抽出
- Untappd URLを検索
- ビールの詳細情報（評価、ABV、IBU、スタイルなど）をスクレイピング
- `untappd_fetched_at`タイムスタンプを記録

**環境変数**:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`

**レート制限**: 2-3秒/リクエスト

---

### 4. `enrich.py` - フルエンリッチメント（後方互換性）
GeminiとUntappdの両方を一度に実行します（後方互換性のため）。

```bash
python -m app.cli enrich --limit 50
```

---

## 🔄 GitHub Actions ワークフロー

### 自動実行スケジュール

1. **scrape.yml** - 毎時実行
   ```
   - 3ショップから全ビール情報をスクレイピング
   - 完了後 → enrich_gemini.yml をトリガー
   ```

2. **enrich_gemini.yml** - scrape完了後 + 4x/日 (0:00, 6:00, 12:00, 18:00 JST)
   ```
   - Gemini未処理のビール15件を処理
   - 完了後 → enrich_untappd.yml をトリガー
   ```

3. **enrich_untappd.yml** - gemini完了後 + 2x/日 (0:30, 12:30 JST)
   ```
   - Untappd未処理のビール30件を処理
   ```

### 手動実行

GitHub Actionsの"Actions"タブから各ワークフローを手動でトリガーできます。

---

## 📊 データフロー

```
┌─────────────────────┐
│  scrape.py          │  ← 毎時実行
│  基本情報収集       │     (GitHub Actions)
└──────────┬──────────┘
           │
           ▼
    Supabase beers table
    (name, price, stock, shop, etc.)
           │
           ▼
┌─────────────────────┐
│  enrich_gemini.py   │  ← scrape完了後 + 4x/日
│  ブルワリー/ビール  │     (GitHub Actions)
│  名抽出 (Gemini)    │
└──────────┬──────────┘
           │
           ▼
    Supabase beers table
    (+ brewery_name_en/jp, beer_name_en/jp)
           │
           ▼
┌─────────────────────┐
│  enrich_untappd.py  │  ← gemini完了後 + 2x/日
│  Untappd情報追加    │     (GitHub Actions)
└──────────┬──────────┘
           │
           ▼
    Supabase beers table
    (+ untappd_url, rating, ABV, IBU, style, etc.)
           │
           ▼
    Vercel Frontend (Next.js)
```

---

## 🎯 ローカル開発・テスト

### 環境変数の設定

`.env`ファイルを作成：
```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-key
GEMINI_API_KEY=your-gemini-key
```

### テスト実行

```bash
# 少量のデータでテスト
python -m app.cli scrape --limit 5
python -m app.cli enrich-gemini --limit 2
python -m app.cli enrich-untappd --limit 2
```

---

## ⚠️ 注意事項

1. **Gemini API制限**
   - 無料枠: 15-20 RPM (Requests Per Minute)
   - スクリプトは自動的にレート制限を監視・調整
   - 1次モデル(`gemini-2.5-flash-lite`)でレート制限時、自動的に2次モデル(`gemini-2.5-flash`)にフォールバック

2. **Untappdスクレイピング**
   - 過度なリクエストはIPブロックの原因になります
   - 2-3秒/リクエストのレート制限を遵守

3. **Supabase接続**
   - `SUPABASE_SERVICE_KEY`（service_role key）が必要
   - anon keyでは書き込み権限がありません

---

## 🐛 トラブルシューティング

### Gemini APIエラー
```bash
❌ Error: GEMINI_API_KEY must be set
```
→ `.env` ファイルに `GEMINI_API_KEY` を設定してください

### Supabase接続エラー
```bash
❌ Error: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set
```
→ `.env` ファイルにSupabase認証情報を設定してください

### "No beers need enrichment"
```bash
✨ No beers need Gemini enrichment!
```
→ すべてのビールが既に処理済みです。正常な状態です。
