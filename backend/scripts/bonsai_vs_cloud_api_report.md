# 🍻 Bonsai 27B (Local MLX) vs Gemma 4 31B (Cloud API) LLM API 代用可否ベンチマーク

## 概要
- **ローカルモデル**: `prism-ml/Ternary-Bonsai-27B-mlx-2bit` (Apple Silicon MLX, 2bit)
- **クラウドAPI**: `Gemma-4-31B-it` (Google Gemini API Structured JSON)
- **テスト件数**: 難易度・バリエーション別 8サンプル

## 比較サマリー表

| ID | サンプル概要 | Cloud API 判定 | Local Bonsai 判定 | Cloud 時間 | Local 時間 | Local 速度 |
|---|---|---|---|---|---|---|
| #1 | 標準バイリンガル表記 | `beer` | `beer` | 3.37s | 36.55s | 2.5 tok/s |
| #2 | 実在コラボ / 複数ブルワリー表記 | `beer` | `beer` | 3.17s | 39.88s | 2.5 tok/s |
| #3 | カタカナ＆長文英語ビール名 | `beer` | `beer` | 4.26s | 36.90s | 2.9 tok/s |
| #4 | ノイズ多数・購入制限＆クール便表記 | `beer` | `beer` | 4.88s | 38.85s | 3.2 tok/s |
| #5 | 限定品・数字ネーミング | `beer` | `beer` | 4.05s | 36.87s | 2.8 tok/s |
| #6 | 略称(WCB) ＋ 英語ビールタイトル | `beer` | `beer` | 3.68s | 41.10s | 2.5 tok/s |
| #7 | セット商品判定 (is_set=True) | `set` | `set` | 3.58s | 42.05s | 2.6 tok/s |
| #8 | 完全英語タイトル ＋ スタイル括弧表記 | `beer` | `beer` | 3.27s | 40.48s | 2.3 tok/s |

- **パース成功率**: Cloud API: 8/8, Local Bonsai: 8/8

## 詳細結果

### テスト #1: うちゅうブルーイング / Uchu Brewing マーズ / MARS (標準バイリンガル表記)

#### ☁️ Cloud API (Gemma 4 31B)
```json
{
  "brewery_name_jp": "うちゅうブルーイング",
  "brewery_name_en": "Uchu Brewing",
  "beer_name_jp": "マーズ",
  "beer_name_en": "MARS",
  "beer_name_core": "MARS",
  "search_hint": "MARS Uchu Brewing",
  "product_type": "beer",
  "is_set": false
}
```

#### 🌿 Local Bonsai 27B
```json
{
  "brewery_name_jp": "うちゅうブルーイング",
  "brewery_name_en": "Uchu Brewing",
  "beer_name_jp": "マーズ",
  "beer_name_en": "MARS",
  "beer_name_core": "MARS",
  "search_hint": "MARS Uchu Brewing",
  "product_type": "beer",
  "is_set": false
}
```
---
### テスト #2: Societe Best Friends Forever (Fremont collab) (473ml) / ベストフレンドフォエバー (実在コラボ / 複数ブルワリー表記)

#### ☁️ Cloud API (Gemma 4 31B)
```json
{
  "brewery_name_jp": null,
  "brewery_name_en": "Societe Brewing Company",
  "beer_name_jp": "ベストフレンドフォエバー",
  "beer_name_en": "Best Friends Forever",
  "beer_name_core": "Best Friends Forever",
  "search_hint": "Best Friends Forever Societe",
  "product_type": "beer",
  "is_set": false
}
```

#### 🌿 Local Bonsai 27B
```json
{
  "brewery_name_jp": "Societe Brewing Company",
  "brewery_name_en": "Societe Brewing Company",
  "beer_name_jp": "Best Friends Forever",
  "beer_name_en": "Best Friends Forever",
  "beer_name_core": "Best Friends Forever",
  "search_hint": "Best Friends Forever Societe",
  "product_type": "beer",
  "is_set": false
}
```
---
### テスト #3: ジャイガンティック サンシャインスーパースター / Gigantic Sunshine Superstar (カタカナ＆長文英語ビール名)

#### ☁️ Cloud API (Gemma 4 31B)
```json
{
  "brewery_name_jp": "ジャイガンティック ブルーイング カンパニー",
  "brewery_name_en": "Gigantic Brewing Company",
  "beer_name_jp": "サンシャインスーパースター",
  "beer_name_en": "Sunshine Superstar",
  "beer_name_core": "Sunshine Superstar",
  "search_hint": "Sunshine Superstar Gigantic Brewing Company",
  "product_type": "beer",
  "is_set": false
}
```

#### 🌿 Local Bonsai 27B
```json
{
  "brewery_name_jp": "ジャイガンティック",
  "brewery_name_en": "Gigantic Brewing Company",
  "beer_name_jp": "サンシャインスーパースター",
  "beer_name_en": "Sunshine Superstar",
  "beer_name_core": "Sunshine Superstar",
  "search_hint": "Sunshine Superstar Gigantic Brewing Company",
  "product_type": "beer",
  "is_set": false
}
```
---
### テスト #4: 【おひとり様2本限定・クール便必須】鬼伝説 金鬼ペールエール 330ml缶 (ノイズ多数・購入制限＆クール便表記)

#### ☁️ Cloud API (Gemma 4 31B)
```json
{
  "brewery_name_jp": "わかさいも本舗",
  "brewery_name_en": "Wakasaimo Honpo",
  "beer_name_jp": "鬼伝説 金鬼ペールエール",
  "beer_name_en": "Oni Densetsu Kin-oni Pale Ale",
  "beer_name_core": "Kin-oni",
  "search_hint": "Kin-oni Oni Densetsu Wakasaimo",
  "product_type": "beer",
  "is_set": false
}
```

#### 🌿 Local Bonsai 27B
```json
{
  "brewery_name_jp": "わかさいも本舗",
  "brewery_name_en": "Wakasaimo Honpo",
  "beer_name_jp": "鬼伝説 金鬼ペールエール",
  "beer_name_en": "Oni Densetsu Kinoni Pale Ale",
  "beer_name_core": "Oni Densetsu Kinoni",
  "search_hint": "Oni Densetsu Kinoni Wakasaimo",
  "product_type": "beer",
  "is_set": false
}
```
---
### テスト #5: 【限定商品】志賀高原ビール / 其の十 / No.10 - 330ml (限定品・数字ネーミング)

#### ☁️ Cloud API (Gemma 4 31B)
```json
{
  "brewery_name_jp": "志賀高原ビール",
  "brewery_name_en": "Shiga Kogen Beer",
  "beer_name_jp": "其の十",
  "beer_name_en": "Sono Ju",
  "beer_name_core": "Sono Ju",
  "search_hint": "Sono Ju Shiga Kogen Beer",
  "product_type": "beer",
  "is_set": false
}
```

#### 🌿 Local Bonsai 27B
```json
{
  "brewery_name_jp": "志賀高原ビール",
  "brewery_name_en": "Shiga Kogen Beer",
  "beer_name_jp": "其の十",
  "beer_name_en": "Sono 10",
  "beer_name_core": "Sono 10",
  "search_hint": "Sono 10 Shiga Kogen Beer",
  "product_type": "beer",
  "is_set": false
}
```
---
### テスト #6: WCB / West Coast Brewing Starwatcher IPA (略称(WCB) ＋ 英語ビールタイトル)

#### ☁️ Cloud API (Gemma 4 31B)
```json
{
  "brewery_name_jp": null,
  "brewery_name_en": "West Coast Brewing",
  "beer_name_jp": null,
  "beer_name_en": "Starwatcher IPA",
  "beer_name_core": "Starwatcher",
  "search_hint": "Starwatcher West Coast Brewing",
  "product_type": "beer",
  "is_set": false
}
```

#### 🌿 Local Bonsai 27B
```json
{
  "brewery_name_jp": "ウェストコストブリーリング",
  "brewery_name_en": "West Coast Brewing",
  "beer_name_jp": "スターウォッチャーIPA",
  "beer_name_en": "Starwatcher IPA",
  "beer_name_core": "Starwatcher",
  "search_hint": "Starwatcher West Coast Brewing",
  "product_type": "beer",
  "is_set": false
}
```
---
### テスト #7: ヨロッコビール / 逗子＆鎌倉４本セット (セット商品判定 (is_set=True))

#### ☁️ Cloud API (Gemma 4 31B)
```json
{
  "brewery_name_jp": "ヨロッコビール",
  "brewery_name_en": "Yorocco Beer",
  "beer_name_jp": "逗子＆鎌倉４本セット",
  "beer_name_en": "Zushi & Kamakura 4-bottle Set",
  "beer_name_core": null,
  "search_hint": null,
  "product_type": "set",
  "is_set": true
}
```

#### 🌿 Local Bonsai 27B
```json
{
  "brewery_name_jp": "ヨロッコビール",
  "brewery_name_en": "Yorocco Beer",
  "beer_name_jp": "逗子＆鎌倉",
  "beer_name_en": "Koma & Kamakura",
  "beer_name_core": "Koma & Kamakura",
  "search_hint": "Koma & Kamakura Yorocco Beer",
  "product_type": "set",
  "is_set": true
}
```
---
### テスト #8: Finback Brewery / Whale Watching (TIPA) (完全英語タイトル ＋ スタイル括弧表記)

#### ☁️ Cloud API (Gemma 4 31B)
```json
{
  "brewery_name_jp": null,
  "brewery_name_en": "Finback Brewery",
  "beer_name_jp": null,
  "beer_name_en": "Whale Watching",
  "beer_name_core": "Whale Watching",
  "search_hint": "Whale Watching Finback Brewery",
  "product_type": "beer",
  "is_set": false
}
```

#### 🌿 Local Bonsai 27B
```json
{
  "brewery_name_jp": "Finback Brewery",
  "brewery_name_en": "Finback Brewery",
  "beer_name_jp": "Whale Watching",
  "beer_name_en": "Whale Watching",
  "beer_name_core": "Whale Watching",
  "search_hint": "Whale Watching Finback",
  "product_type": "beer",
  "is_set": false
}
```
---
