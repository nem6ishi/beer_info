# Craft Beer Watch Japan - 設計・要件定義書

本ドキュメントは、「Craft Beer Watch Japan (Cloud Edition)」の要件定義およびシステム設計についてまとめたものです。

---

## 1. プロジェクト概要

「Craft Beer Watch Japan」は、日本の主要なクラフトビール専門ECサイトから在庫情報を自動収集（スクレイピング）し、AI（LLM）による表記揺れ吸収やメタデータ抽出を行い、ビール評価プラットフォーム（Untappd）の情報と紐付けることで、ユーザーが横断的にクラフトビールの在庫状況やレーティング、詳細情報を確認・比較できるサービスです。

- **フロントエンド & API**: Next.js (Vercel にデプロイ)
- **データベース**: Supabase (PostgreSQL)
- **バックエンド・バッチ処理**: Python (uv でパッケージ管理、GitHub Actions で自動実行)

---

## 2. 要件定義

### 2.1. 機能要件

#### A. データ収集・スクレイピング
- **対象ECサイト**: 下記のクラフトビール専門店から定期的に商品情報（URL、商品名、価格、画像、在庫状況など）を収集する。
  - Arome (アローム)
  - Beer Volta (ビールボルタ)
  - Chouseiya (ちょうせいや)
  - Ichigo Ichie (一期一会)
- **データ更新**: 既存データの価格変更や在庫状況（販売中 / 売り切れ）を反映し、新規商品を検知する。

#### B. AIメタデータ抽出 (LLM Enrichment)
- **生タイトルのクレンジング**: LLMに送信する前に、不要な注意事項（「【予定】」「【クール便】」「【空輸】」「【限定品】」など）を正規表現で自動クレンジングし、LLMのトークン節約と抽出精度の向上を図る。
- **ショップ個別パース規則 (Shop-Specific Rules)**: 各ショップ（販売店）特有の商品名フォーマットの規則（例：ちょうせいやの「【ビール名/ブルワリー名】」、アロームの「[...]」英語表記など）を `shop_rules.json` で定義し、LLMのコンテキストに注入して解析させることで、誤認識を極限まで低減させる。
- **メタデータ抽出項目**: クレンジングされた商品タイトルから、以下の項目をLLMを用いて抽出する。
  - ブルワリー名（英語 / 日本語）
  - ビール名（英語 / 日本語）
  - ビールのコア名（バージョンや年度、スタイルサフィックスを除外した検索用文字列）
  - Untappd検索用ヒントクエリ（英語）
  - 商品タイプ（ビール / セット商品 / グラス / その他）およびセット商品判定（`is_set`）

#### C. Untappd 連携 (Untappd Enrichment)
- メタデータから Untappd 上の該当ビールを検索・紐付ける。
- **紐付け検索戦略 (Multi-stage Search Strategy)**:
  1. **ブルワリー別検索**: 抽出したブルワリー名の英名（またはエイリアス）からまずUntappd上のブルワリーページを特定し、そのブルワリー配下の商品からビール名を検索・照合する。
  2. **Year-fallback (西暦フォールバック)**: 商品名に西暦（20XX）が含まれる場合、まずは西暦付きで検索し、ヒットしない場合は西暦を取り除いたコア名で再検索を行う。
  3. **DuckDuckGo検索フォールバック**: 上記でヒットしない場合、`ddgs` (DuckDuckGo Search) を利用して「untappd [検索ヒント]」のクエリでWeb検索を行い、ヒットしたUntappdページをスクレイピングして検証する。
- **表記揺れ吸収 (Brewery Aliases)**: `aliases.json` を使用し、英語名・日本語名・別名（略称など）をマッピングして、バリデーション段階でのマッチング判定で許容する。
- **検索失敗の記録**: 検索が失敗した場合は `untappd_search_failures` にエラー理由と共に記録し、次回以降の無駄なAPI呼び出しをバックオフ（再試行猶予期間の適用）により防ぐ。
- **データリフレッシュ**: 在庫があるビールについては、情報の陳腐化を防ぐため、前回の取得から **5日以上** 経過したデータを最新情報に自動更新する。

#### D. フロントエンド画面とAPI
- **ビール一覧表示**: 収集したビールのカード型一覧。検索、フィルタ（ショップ、アルコール度数(ABV)、苦味(IBU)、評価、スタイル、ブルワリー）、ソート（最新順、価格順、評価順など）が可能。
- **グループ表示 (`/grouped`)**: 同一のビール（同じUntappd URL）が異なるショップで販売されている場合、最安値・最高値および販売店リストをまとめて比較できる機能。
- **高速応答**: 大量のJOINやフィルタによる遅延を防ぐため、Supabase側のマテリアライズドビューを参照する。

---

## 3. システム設計

### 3.1. システム構成・アーキテクチャ

システム全体の構成およびデータの流れは以下の通りです。

```mermaid
graph TD
    subgraph GitHub_Actions [GitHub Actions (バッチ処理)]
        ScrapeCmd[1. スクレイプコマンド]
        GeminiCmd[2. Geminiエンリッチ]
        UntappdCmd[3. Untappdエンリッチ]
        BreweryCmd[4. ブルワリーエンリッチ]
    end

    subgraph External_APIs [外部API / Web]
        Shops[(ECサイト 4店舗)]
        GeminiAPI[Google Gemini API]
        UntappdAPI[Untappd Web]
        DDGSearch[DuckDuckGo Search]
    end

    subgraph Supabase [Supabase Database]
        TS[scraped_beers (生データ)]
        TG[gemini_data (AI抽出)]
        TU[untappd_data (ビール詳細)]
        TB[breweries (ブルワリー)]
        TF[untappd_search_failures (エラーログ)]
        TUsage[api_usage_tracking (API使用量)]
        
        MV[beer_info_view (マテリアライズドビュー)]
        VGroup[beer_groups_view (グループ化ビュー)]
    end

    subgraph Frontend_Vercel [Next.js (Vercel)]
        UI[Web UI (React)]
        API[API Endpoints (/api/beers, etc.)]
    end

    %% データフローの接続
    ScrapeCmd -->|スクレイプ| Shops
    ScrapeCmd -->|データ保存| TS
    
    GeminiCmd -->|未解析データの抽出依頼| GeminiAPI
    GeminiCmd -->|データ保存| TG
    GeminiCmd -->|API使用量インクリメント| TUsage
    
    UntappdCmd -->|検索 & スクレイプ| UntappdAPI
    UntappdCmd -->|Web検索フォールバック| DDGSearch
    UntappdCmd -->|データ保存| TU
    UntappdCmd -->|失敗ログ記録| TF
    
    BreweryCmd -->|ブルワリー情報取得| UntappdAPI
    BreweryCmd -->|データ保存| TB

    %% ビューの構築
    TS --> MV
    TG --> MV
    TU --> MV
    TB --> MV
    MV --> VGroup

    %% フロントエンドとの接続
    API -->|クエリ| MV
    API -->|クエリ| VGroup
    UI -->|リクエスト| API
```

---

### 3.2. データベース設計 (DB Schema)

#### A. 主要テーブル

| テーブル名 | 用途 | キー項目 | 主なカラム |
|---|---|---|---|
| `scraped_beers` | ECサイトからスクレイピングした生データ | `url` (PK) | `name`, `price`, `price_num`, `image`, `stock_status`, `shop`, `first_seen`, `last_seen`, `untappd_url` |
| `gemini_data` | Gemini APIによりパースされたビールのメタデータ | `url` (PK) | `brewery_name_en`, `brewery_name_jp`, `beer_name_en`, `beer_name_jp`, `product_type`, `is_set`, `payload` (raw JSON) |
| `untappd_data` | Untappdからスクレイピングしたビールの詳細・評価データ | `untappd_url` (PK) | `beer_name`, `brewery_name`, `style`, `abv_num`, `ibu_num`, `rating_num`, `rating_count_num`, `image_url`, `untappd_brewery_url` |
| `breweries` | ブルワリー（醸造所）のマスタデータ | `id` (PK, UUID) | `name_en`, `name_jp`, `aliases`, `untappd_url` (Unique), `location`, `brewery_type`, `website`, `stats`, `logo_url` |
| `untappd_search_failures` | Untappd検索に失敗した履歴と再試行制御用 | `id` (PK, UUID) | `product_url`, `brewery_name`, `beer_name`, `failure_reason`, `search_attempts`, `last_error_message`, `resolved` |
| `api_usage_tracking` | API (Gemini等) の日ごとの使用回数記録 | `(service_name, date)` (PK) | `request_count`, `updated_at` |

#### B. セキュリティポリシー (RLS Policies)
- データベース全体の安全を確保するため、すべての主要テーブルで **行レベルセキュリティ (RLS)** を有効化している。
- **一般ユーザー (anon ロール)**: 読み取り専用アクセス (`SELECT`) のみを許可。
- **バッチ処理スクリプト (authenticated ロール)**: GitHub Actions で `SUPABASE_SERVICE_KEY` を用いて認証を行い、すべての書き込み・変更処理 (`ALL`) を許可。

#### C. 高速表示のためのビュー

1. **`beer_info_view` (マテリアライズドビュー)**
   - `scraped_beers` に `gemini_data`、`untappd_data`、`breweries` を LEFT JOIN で結合したフラットなビュー。
   - `url`, `first_seen`, `price_value`, `abv`, `rating` などのカラムにユニークインデックスおよび通常インデックスを付与し、APIからの検索・フィルタリングをミリ秒単位で高速実行可能にしている。
   - 更新用ストアドファンクション `refresh_beer_info_view()` により、バッチ処理完了後に `REFRESH MATERIALIZED VIEW CONCURRENTLY` でゼロダウンタイム更新される。

2. **`beer_groups_view` (ビュー)**
   - `beer_info_view` を `untappd_url` で `GROUP BY` し、同一ビールの複数ショップにまたがる価格情報（最安値、最高値）や販売店リストを JSONB 配列 (`items`) として集約したビュー。

---

### 3.3. バックエンド処理フローと自動化スケジュール

GitHub Actionsにより、以下のタスクが自動スケジュール実行されます。

| タスク名 | 実行コマンド | 実行スケジュール (JST) | 処理内容 |
|---|---|---|---|
| **スクレイピング** | `uv run cli.py scrape --limit 100 --new` | 毎時間 (毎時 0分) | 新着ビールの検知と在庫状況・価格の更新。 |
| **Gemini 解析** | `uv run cli.py enrich gemini --limit 50 --offline` | スクレイプ完了後 + 1日4回 (0:00, 6:00, 12:00, 18:00) | 未解析ビールの名前・ブランド抽出。 |
| **Untappd 連携** | `uv run cli.py enrich untappd --limit 50 --mode missing` | Gemini完了後 + 1日2回 (0:30, 12:30) | 未紐付けビールの検索・スペックの取得。 |
| **ブルワリー拡張** | `uv run cli.py enrich breweries --limit 50` | (適宜パイプライン内) | 新規ブルワリー情報の収集とマスタ登録。 |

---

### 3.4. API レートリミット最適化（AI API 対策）

Gemini API の利用上限（または将来的な有料枠移行）を考慮し、無駄なリクエストの最小化と自動エラーハンドリングを適用しています。

- **アトミックな使用量トラッキング (Atomic Usage Tracking)**
  - API呼び出しの直前に Supabase のストアドファンクション `increment_api_usage` を呼び出し、その日の利用実績数をアトミックに加算する。
  - 実績数が設定した安全上限（`global_daily_limit` = 1,450 RPD）を超過している場合は、自動的にAPIリクエストをスキップして無料枠超過を防ぐ。
- **自動フォールバック戦略 (Model Switching)**
  - プライマリモデルとして `gemma-4-31b-it` を使用。
  - レートリミットエラー（`429 RESOURCE_EXHAUSTED` 等）や一時的エラーが発生した場合、自動的にフォールバックモデルである `gemma-4-26b-a4b-it` に切り替えて即座に再試行する。
- **流量制御 (Throttling)**
  - APIへの急激なアクセスを防ぐため、リクエスト間に最低 4.5 秒（約 13.3 RPM 相当）の間隔を空ける `request_interval` 制御を実装。
- **検索失敗のバックオフ (Failure Backoff)**
  - 何度も検索に失敗する（Untappdに存在しないなど）ビールに対して、毎バッチで検索APIやスクレイピングが走るのを防ぐため、`untappd_search_failures` に記録し、一定期間（例: 24時間）は再検索をスキップする。
