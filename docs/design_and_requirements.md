# Craft Beer Watch Japan - 設計・要件定義書

本ドキュメントは、「Craft Beer Watch Japan (Cloud Edition)」の要件定義およびシステム設計についてまとめたものです。

---

## 1. プロジェクト概要

「Craft Beer Watch Japan」は、日本の主要なクラフトビール専門ECサイトから在庫情報を自動収集（スクレイピング）し、AI（Google Gemini）による表記揺れ吸収やメタデータ抽出を行い、ビール評価プラットフォーム（Untappd）の情報と紐付けることで、ユーザーが横断的にクラフトビールの在庫状況やレーティング、詳細情報を確認・比較できるサービスです。

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

#### B. AIメタデータ抽出 (Gemini Enrichment)
- 収集した生の商品名から、以下の項目をAI（Gemini API）を用いて抽出する。
  - ブルワリー名（英語 / 日本語）
  - ビール名（英語 / 日本語）
  - 商品タイプ（ビール / セット商品 / その他）
- 英語表記と日本語表記を抽出することで、Untappdでの検索ヒット率を高め、フロントエンドでの多言語検索をサポートする。

#### C. Untappd 連携 (Untappd Enrichment)
- メタデータから Untappd 上の該当ビールを検索・紐付ける。
- **検索の堅牢化 (Two-pass retry)**: 初回検索でヒットしない場合、Geminiを用いて代替の検索クエリ（表記揺れや余計な単語を削ったクエリ）を生成して再検索を行う。
- **情報の取得**: 紐付けに成功したビールの詳細スペック（スタイル、ABV、IBU、Untappdレーティング、評価数、画像など）を取得する。
- **検索失敗の記録**: 検索が失敗した場合は `untappd_search_failures` にエラー理由と共に記録し、次回以降の無駄なAPI呼び出しをバックオフ（再試行猶予期間の適用）により防ぐ。
- **データリフレッシュ**: 在庫があるビールについては、情報の陳腐化を防ぐため、5日以上経過したデータを最新情報に更新する。

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
    UntappdCmd -->|Fluxクエリ生成依頼| GeminiAPI
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

#### B. 高速表示のためのビュー

1. **`beer_info_view` (マテリアライズドビュー)**
   - `scraped_beers` に `gemini_data`、`untappd_data`、`breweries` を LEFT JOIN で結合したフラットなビュー。
   - `url`, `first_seen`, `price_value`, `abv`, `rating` などのカラムにユニークインデックスおよび通常インデックスを付与し、APIからの検索・フィルタリングをミリ秒単位で高速実行可能にしている。
   - 更新用ストアドファンクション `refresh_beer_info_view()` により、バッチ処理完了後に `REFRESH MATERIALIZED VIEW CONCURRENTLY` でゼロダウンタイム更新される。

2. **`beer_groups_view` (ビュー)**
   - `beer_info_view` を `untappd_url` で `GROUP BY` し、同一ビールの複数ショップにまたがる価格情報（最安値、最高値）や販売店リストを JSONB 配列 (`items`) として集約したビュー。

---

### 3.3. バックエンド処理フローとパイプライン

GitHub Actionsにより、以下のタスクがスケジュール実行されます。

1. **Scraping (`uv run cli.py scrape`)**
   - 4つのショップスクレイパーを並行実行し、最新の商品情報を `scraped_beers` テーブルへ `UPSERT`（存在しなければ挿入、存在すれば最終確認日時 `last_seen` と在庫状況を更新）。

2. **AI Enrichment (`uv run cli.py enrich gemini`)**
   - `scraped_beers` のうち、まだ `gemini_data` が存在しない新規レコードを処理対象にする。
   - Gemini API に商品名とショップのスクレイプ情報を渡し、英語・日本語のブルワリー名・ビール名および「セット商品か否か」を判別させて `gemini_data` に保存。

3. **Untappd Enrichment (`uv run cli.py enrich untappd`)**
   - `gemini_data` はあるが `scraped_beers.untappd_url` が空（未紐付け）のレコードを対象とする (`missing` モード)。
   - 抽出した英語・日本語名を使って Untappd を検索し、ヒットした場合は詳細情報を `untappd_data` に保存し、`scraped_beers.untappd_url` に紐付ける。
   - **Two-pass retry**: 検索で直接ヒットしなかった場合、再度 Gemini API を呼び出して不要語（容量表記やビールスタイル名など）を除去した最適化クエリを生成させ、再検索を行う。
   - 既に紐付け済みのデータで5日以上経過し、かつ在庫があるものを対象に詳細スペックや最新のレーティングを再取得する (`refresh` モード)。

4. **Brewery Enrichment (`uv run cli.py enrich breweries`)**
   - `untappd_data` の `untappd_brewery_url` があり、まだ `breweries` テーブルにないブルワリーの詳細（ホームページ、ロケーション、醸造所タイプ、ロゴ）を取得・更新する。

---

### 3.4. API レートリミット最適化（Gemini API 対策）

プロジェクトにおける最大の制約は、Google Gemini APIの無料枠制限（1日あたり20リクエスト/モデル）をいかにクリアするかです。これに対して以下の設計・設計パターンが適用されています。

- **自動フォールバック戦略 (Model Switching)**
  - プライマリモデルとして軽量で高速な `gemini-2.5-flash-lite` を使用。
  - レートリミット（`429 RESOURCE_EXHAUSTED`）を検知すると、自動的にフォールバックモデルである `gemini-2.5-flash` に切り替えてリクエストをリトライする。これにより1日最大40リクエストまで処理可能。
- **流量制御 (Throttling)**
  - APIへの急激なアクセスを防ぐため、リクエスト間に最低4秒（15 RPM相当）の間隔を空ける `request_interval` 制御を実装。
- **検索失敗の記録とバックオフ (Failure Backoff)**
  - 何度も検索に失敗する（Untappdに存在しないなど）ビールに対して、毎バッチで検索APIやスクレイピングが走るのを防ぐため、`untappd_search_failures` に記録し、一定期間（例: 24時間）は再検索をスキップする仕組みを導入。
- **逐次処理 (Sequential Processing)**
  - すでに判明しているブルワリー名の翻訳結果やエイリアスのキャッシュ情報を最大限活用し、新規ビールでも過去に同一ブルワリーの処理実績があれば翻訳のためのAPI呼び出しをスキップする。
