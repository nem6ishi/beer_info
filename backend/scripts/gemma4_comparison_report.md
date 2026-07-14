# Gemma 4 12B (Local MLX) vs Gemma 4 31B (Cloud API) 抽出＆Enrich結果比較レポート

- **測定日時**: 2026-07-14 23:15:31
- **ローカルモデル**: `mlx-community/gemma-4-12B-it-4bit` (初回ロード時間: 4.05秒)
- **クラウドモデル**: `gemma-4-31b-it`
- **平均処理速度**: Cloud `5.57秒/件` vs Local `31.12秒/件`

## 個別詳細テーブル

### #1. 標準バイリンガル表記
- **タイトル**: 「`うちゅうブルーイング / Uchu Brewing マーズ / MARS`」 (ショップ: `BEER VOLTA`)
- **処理時間**: Cloud `8.42秒` vs Local `28.87秒`

| 項目 | Cloud API (31B) | Local MLX (12B 4-bit) | 判定 |
| :--- | :--- | :--- | :--- |
| 英語ブルワリー名 (`brewery_name_en`) | `Uchu Brewing` | `Uchu Brewing` | ⭕ 一致 |
| 和名ブルワリー名 (`brewery_name_jp`) | `うちゅうブルーイング` | `うちゅうブルーイング` | ⭕ 一致 |
| ビールコア名 (`beer_name_core`) | `MARS` | `MARS` | ⭕ 一致 |
| 検索ヒント (`search_hint`) | `MARS Uchu Brewing` | `MARS Uchu Brewing` | ⭕ 一致 |
| 商品区分 (beer等) (`product_type`) | `beer` | `beer` | ⭕ 一致 |
| セット商品 (bool) (`is_set`) | `False` | `False` | ⭕ 一致 |
| **🍺 Untappd URL** | [https://untappd.com/b/uchu-brewing-mars/6508045](https://untappd.com/b/uchu-brewing-mars/6508045) | [https://untappd.com/b/uchu-brewing-mars/6508045](https://untappd.com/b/uchu-brewing-mars/6508045) | **⭕ 一致** |
| *(マッチアイテム)* | `Found` | `Found` | -

### #2. コラボ / 複数ブルワリー表記
- **タイトル**: 「`【ROOTS ROCK/ヨロッコ】(VERTERE Casimiroa NE IPA)`」 (ショップ: `BEER VOLTA`)
- **処理時間**: Cloud `4.31秒` vs Local `31.12秒`

| 項目 | Cloud API (31B) | Local MLX (12B 4-bit) | 判定 |
| :--- | :--- | :--- | :--- |
| 英語ブルワリー名 (`brewery_name_en`) | `Yorocco Beer` | `ROOTS ROCK` | ⚠️ 差異 |
| 和名ブルワリー名 (`brewery_name_jp`) | `ヨロッコ` | `ヨロッコ` | ⭕ 一致 |
| ビールコア名 (`beer_name_core`) | `Casimiroa` | `VERTERE Casimiroa` | ⚠️ 差異 |
| 検索ヒント (`search_hint`) | `Casimiroa Yorocco Beer` | `VERTERE Casimiroa ROOTS ROCK` | ⚠️ 差異 |
| 商品区分 (beer等) (`product_type`) | `beer` | `beer` | ⭕ 一致 |
| セット商品 (bool) (`is_set`) | `False` | `False` | ⭕ 一致 |
| **🍺 Untappd URL** | [https://untappd.com/b/yorocco-beer-ginger-saison/5206483](https://untappd.com/b/yorocco-beer-ginger-saison/5206483) | `NotFound (no_results)` | **⚠️ 差異** |
| *(マッチアイテム)* | `Found` | `N/A` | -

### #3. カタカナ＆長文英語ビール名
- **タイトル**: 「`ジャイガンティック サンシャインスーパースター / Gigantic Sunshine Superstar`」 (ショップ: `BEER VOLTA`)
- **処理時間**: Cloud `5.67秒` vs Local `31.01秒`

| 項目 | Cloud API (31B) | Local MLX (12B 4-bit) | 判定 |
| :--- | :--- | :--- | :--- |
| 英語ブルワリー名 (`brewery_name_en`) | `Gigantic Brewing Company` | `Gigantic Brewing Company` | ⭕ 一致 |
| 和名ブルワリー名 (`brewery_name_jp`) | `ジャイガンティック` | `Gigantic Brewing Company` | ⚠️ 差異 |
| ビールコア名 (`beer_name_core`) | `Sunshine Superstar` | `Gigantic Sunshine Superstar` | ⚠️ 差異 |
| 検索ヒント (`search_hint`) | `Sunshine Superstar Gigantic Brewing Company` | `Gigantic Sunshine Superstar Gigantic Brewing Company` | ⚠️ 差異 |
| 商品区分 (beer等) (`product_type`) | `beer` | `beer` | ⭕ 一致 |
| セット商品 (bool) (`is_set`) | `False` | `False` | ⭕ 一致 |
| **🍺 Untappd URL** | [https://untappd.com/b/gigantic-brewing-company-sunshine-superstar/6308232](https://untappd.com/b/gigantic-brewing-company-sunshine-superstar/6308232) | [https://untappd.com/b/gigantic-brewing-company-sunshine-superstar/6308232](https://untappd.com/b/gigantic-brewing-company-sunshine-superstar/6308232) | **⭕ 一致** |
| *(マッチアイテム)* | `Found` | `Found` | -

### #4. ノイズ多数・購入制限＆クール便表記
- **タイトル**: 「`【おひとり様2本限定・クール便必須】鬼伝説 金鬼ペールエール 330ml缶`」 (ショップ: `ちょうせいや`)
- **処理時間**: Cloud `7.93秒` vs Local `31.59秒`

| 項目 | Cloud API (31B) | Local MLX (12B 4-bit) | 判定 |
| :--- | :--- | :--- | :--- |
| 英語ブルワリー名 (`brewery_name_en`) | `Wakasaimo Honpo` | `Wakasaimo` | ⚠️ 差異 |
| 和名ブルワリー名 (`brewery_name_jp`) | `わかさいも本舗` | `わかさいも本舗` | ⭕ 一致 |
| ビールコア名 (`beer_name_core`) | `金鬼` | `鬼伝説 金鬼` | ⚠️ 差異 |
| 検索ヒント (`search_hint`) | `Kinki Wakasaimo Honpo` | `鬼伝説 金鬼 わかさいも本舗` | ⚠️ 差異 |
| 商品区分 (beer等) (`product_type`) | `beer` | `beer` | ⭕ 一致 |
| セット商品 (bool) (`is_set`) | `False` | `False` | ⭕ 一致 |
| **🍺 Untappd URL** | `NotFound (no_results)` | `NotFound (no_results)` | **❌** |

### #5. 限定品・数字ネーミング
- **タイトル**: 「`【限定商品】志賀高原ビール / 其の十 / No.10 - 330ml`」 (ショップ: `BEER VOLTA`)
- **処理時間**: Cloud `4.95秒` vs Local `29.67秒`

| 項目 | Cloud API (31B) | Local MLX (12B 4-bit) | 判定 |
| :--- | :--- | :--- | :--- |
| 英語ブルワリー名 (`brewery_name_en`) | `Tamamura Honten` | `Tamamuro` | ⚠️ 差異 |
| 和名ブルワリー名 (`brewery_name_jp`) | `玉村本店` | `玉村本店` | ⭕ 一致 |
| ビールコア名 (`beer_name_core`) | `No.10` | `No.10` | ⭕ 一致 |
| 検索ヒント (`search_hint`) | `No.10 Tamamura Honten` | `No.10 Tamamuro` | ⚠️ 差異 |
| 商品区分 (beer等) (`product_type`) | `beer` | `beer` | ⭕ 一致 |
| セット商品 (bool) (`is_set`) | `False` | `False` | ⭕ 一致 |
| **🍺 Untappd URL** | [https://untappd.com/b/tamamura-honten-co-shiga-kogen-sono-10-no-10-anniversary-ipa/850141](https://untappd.com/b/tamamura-honten-co-shiga-kogen-sono-10-no-10-anniversary-ipa/850141) | `NotFound (no_results)` | **⚠️ 差異** |
| *(マッチアイテム)* | `Found` | `N/A` | -

### #6. 略称(WCB) ＋ 英語ビールタイトル
- **タイトル**: 「`WCB / West Coast Brewing Starwatcher IPA`」 (ショップ: `Antenna America`)
- **処理時間**: Cloud `3.22秒` vs Local `31.33秒`

| 項目 | Cloud API (31B) | Local MLX (12B 4-bit) | 判定 |
| :--- | :--- | :--- | :--- |
| 英語ブルワリー名 (`brewery_name_en`) | `West Coast Brewing` | `West Coast Brewing` | ⭕ 一致 |
| 和名ブルワリー名 (`brewery_name_jp`) | `None` | `West Coast Brewing` | ⚠️ 差異 |
| ビールコア名 (`beer_name_core`) | `Starwatcher` | `Starwatcher` | ⭕ 一致 |
| 検索ヒント (`search_hint`) | `Starwatcher West Coast Brewing` | `Starwatcher West Coast Brewing` | ⭕ 一致 |
| 商品区分 (beer等) (`product_type`) | `beer` | `beer` | ⭕ 一致 |
| セット商品 (bool) (`is_set`) | `False` | `False` | ⭕ 一致 |
| **🍺 Untappd URL** | [https://untappd.com/b/west-coast-brewing-starwatcher/3314985](https://untappd.com/b/west-coast-brewing-starwatcher/3314985) | [https://untappd.com/b/west-coast-brewing-starwatcher/3314985](https://untappd.com/b/west-coast-brewing-starwatcher/3314985) | **⭕ 一致** |
| *(マッチアイテム)* | `Found` | `Found` | -

### #7. セット商品判定 (is_set=True)
- **タイトル**: 「`ヨロッコビール / 逗子＆鎌倉４本セット`」 (ショップ: `MARUHO`)
- **処理時間**: Cloud `5.37秒` vs Local `33.97秒`

| 項目 | Cloud API (31B) | Local MLX (12B 4-bit) | 判定 |
| :--- | :--- | :--- | :--- |
| 英語ブルワリー名 (`brewery_name_en`) | `Yorocco Beer` | `Yorocco Beer` | ⭕ 一致 |
| 和名ブルワリー名 (`brewery_name_jp`) | `ヨロッコビール` | `ヨロッコ` | ⚠️ 差異 |
| ビールコア名 (`beer_name_core`) | `Zushi & Kamakura` | `Yorocco Beer` | ⚠️ 差異 |
| 検索ヒント (`search_hint`) | `Zushi Kamakura Yorocco Beer` | `Yorocco Beer` | ⚠️ 差異 |
| 商品区分 (beer等) (`product_type`) | `set` | `set` | ⭕ 一致 |
| セット商品 (bool) (`is_set`) | `True` | `True` | ⭕ 一致 |
| **🍺 Untappd URL** | `N/A` | `N/A` | **❌** |

### #8. 完全英語タイトル ＋ スタイル括弧表記
- **タイトル**: 「`Finback Brewery / Whale Watching (TIPA)`」 (ショップ: `Antenna America`)
- **処理時間**: Cloud `4.67秒` vs Local `31.39秒`

| 項目 | Cloud API (31B) | Local MLX (12B 4-bit) | 判定 |
| :--- | :--- | :--- | :--- |
| 英語ブルワリー名 (`brewery_name_en`) | `Finback Brewery` | `Finback Brewery` | ⭕ 一致 |
| 和名ブルワリー名 (`brewery_name_jp`) | `None` | `Finback Brewery` | ⚠️ 差異 |
| ビールコア名 (`beer_name_core`) | `Whale Watching` | `Whale Watching` | ⭕ 一致 |
| 検索ヒント (`search_hint`) | `Whale Watching Finback Brewery` | `Whale Watching Finback Brewery` | ⭕ 一致 |
| 商品区分 (beer等) (`product_type`) | `beer` | `beer` | ⭕ 一致 |
| セット商品 (bool) (`is_set`) | `False` | `False` | ⭕ 一致 |
| **🍺 Untappd URL** | [https://untappd.com/b/finback-brewery-whale-watching/3731819](https://untappd.com/b/finback-brewery-whale-watching/3731819) | [https://untappd.com/b/finback-brewery-whale-watching/3731819](https://untappd.com/b/finback-brewery-whale-watching/3731819) | **⭕ 一致** |
| *(マッチアイテム)* | `Found` | `Found` | -

