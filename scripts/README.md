# スクレイパースクリプト

このディレクトリには、ビールデータの収集とエンリッチメントを段階的に実行するためのスクリプトが含まれています。

## 📋 スクリプト一覧

### 1. `scrape_only.py` - スクレイピングのみ
基本的なビール情報（名前、価格、在庫状況など）をショップからスクレイピングします。
Gemini APIやUntappdは使用しません。

```bash
# 全ショップをスクレイピング
python scripts/scrape_only.py

# テスト用（各ショップ5件まで）
python scripts/scrape_only.py --limit 5
```

**出力**: `data/beers.json` に基本情報のみを保存

---

### 2. `enrich_gemini.py` - Geminiエンリッチメント
既存の `beers.json` に対して、Gemini APIでビール名とブルワリー名を抽出します。

```bash
# 未処理のビールのみエンリッチ（推奨）
python scripts/enrich_gemini.py

# 全ビールを再エンリッチ
python scripts/enrich_gemini.py --all

# テスト用（10件まで）
python scripts/enrich_gemini.py --limit 10
```

**注意**: 
- Gemini APIのレート制限: 15 RPM（4秒/リクエスト）
- 100件のビールで約7分かかります

---

### 3. `enrich_untappd.py` - Untappdエンリッチメント
既存の `beers.json` に対して、Untappd情報（URL、評価、ABV、IBUなど）を追加します。

```bash
# 未処理のビールのみエンリッチ（推奨）
python scripts/enrich_untappd.py

# 全ビールを再エンリッチ
python scripts/enrich_untappd.py --all

# テスト用（10件まで）
python scripts/enrich_untappd.py --limit 10
```

**注意**: 
- Untappdスクレイピングのレート制限: 2-3秒/リクエスト
- 100件のビールで約5-8分かかります

---

## 🔄 推奨ワークフロー

### 日次更新（Gemini API制限を考慮）

```bash
# 1. 毎日: スクレイピングのみ実行（API制限なし）
python scripts/scrape_only.py

# 2. 週1回: Geminiエンリッチメント（新規ビールのみ）
python scripts/enrich_gemini.py

# 3. 週1回: Untappdエンリッチメント（新規ビールのみ）
python scripts/enrich_untappd.py
```

### crontab設定例

```bash
# 毎日午前2時: スクレイピング
0 2 * * * cd /path/to/beer_info && python scripts/scrape_only.py >> logs/scrape.log 2>&1

# 毎週日曜午前3時: Geminiエンリッチメント
0 3 * * 0 cd /path/to/beer_info && python scripts/enrich_gemini.py >> logs/gemini.log 2>&1

# 毎週日曜午前4時: Untappdエンリッチメント
0 4 * * 0 cd /path/to/beer_info && python scripts/enrich_untappd.py >> logs/untappd.log 2>&1
```

---

## 📊 データフロー

```
┌─────────────────────┐
│  scrape_only.py     │  ← 毎日実行（API制限なし）
│  基本情報収集       │
└──────────┬──────────┘
           │
           ▼
    data/beers.json
    (name, price, stock, etc.)
           │
           ▼
┌─────────────────────┐
│  enrich_gemini.py   │  ← 週1回実行（Gemini API制限あり）
│  ビール名抽出       │
└──────────┬──────────┘
           │
           ▼
    data/beers.json
    (+ brewery_name, beer_name)
           │
           ▼
┌─────────────────────┐
│  enrich_untappd.py  │  ← 週1回実行（スクレイピング制限あり）
│  Untappd情報追加    │
└──────────┬──────────┘
           │
           ▼
    data/beers.json
    (+ untappd_url, rating, ABV, IBU, etc.)
```

---

## 🎯 使い分けのポイント

### スクレイピングのみ実行する場合
- 価格や在庫状況の更新だけが必要
- Gemini APIの制限に達している
- 新規ビールが少ない日

### Geminiエンリッチメントを実行する場合
- 新規ビールが追加された
- ビール名/ブルワリー名の抽出精度を改善したい
- 週1回程度の実行を推奨

### Untappdエンリッチメントを実行する場合
- Geminiエンリッチメント後
- Untappd情報（評価、ABV、IBUなど）が必要
- 週1回程度の実行を推奨

---

## ⚠️ 注意事項

1. **Gemini API制限**
   - 無料枠: 15 RPM (Requests Per Minute)
   - スクリプトは自動的に4秒/リクエストで制限
   - 大量のビールを処理する場合は時間がかかります

2. **Untappdスクレイピング**
   - 過度なリクエストはIPブロックの原因になります
   - レート制限を守って実行してください

3. **データの整合性**
   - 各スクリプトは既存データを保持します
   - `--all` オプション使用時は注意してください

---

## 🐛 トラブルシューティング

### Gemini APIエラー
```bash
❌ Error: Gemini API key not configured
```
→ `.env` ファイルに `GEMINI_API_KEY` を設定してください

### beers.json が見つからない
```bash
❌ Error: data/beers.json not found
```
→ まず `scrape_only.py` を実行してください

### レート制限エラー
→ `--limit` オプションで少量ずつテストしてください
