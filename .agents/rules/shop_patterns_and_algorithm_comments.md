# Shop Patterns & Algorithm Comments Guidelines

1. **ショップごとの表記パターンのコード内記録**:
   - クラフトビールECショップ（Antenna America, BEER VOLTA, アローム, マルホ酒店, ちょうせいや, 一期一会～る 等）のタイトル表記構造や固有ルールを発見・修正した場合、必ず `backend/src/services/llm/prompt_builder.py` や `shop_rules.json` などの関連コード内に詳細な解説コメントを残す。

2. **アルゴリズム・設計の工夫のコード内記録**:
   - タイトルのクレンジング（ノイズ除去 regex）、2-pass 検索フォバリデーション、ブルワリー名や容量表記の除外処理などのアルゴリズム的な工夫・意図（Why / How）を、コードブロック冒頭や関数ドキュメント（docstring）に明確に記録・維持する。
