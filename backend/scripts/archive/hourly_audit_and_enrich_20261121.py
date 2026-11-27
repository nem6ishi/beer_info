import asyncio
import logging
import time
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client, refresh_materialized_view, sync_execute
from backend.src.services.untappd.http_client import scrape_beer_details, close_async_client
from backend.src.core.utils import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 1. 直近追加商品の誤紐付け・メタデータ是正アイテム
FIX_MISASSIGNED_ITEMS = [
    {
        "url": "https://maruho.shop/products/pils-de-pils-gold-dot-473ml-heater-allen",
        "name": "Pils De Pils Gold Dot 473ml/Heater Allen",
        "untappd_url": "https://untappd.com/b/gold-dot-beer-pils-de-pils/5789629",
        "gemini_update": {
            "brewery_name_en": "Gold Dot Beer",
            "brewery_name_jp": "ゴールドドットビア",
            "beer_name_en": "Pils de Pils",
            "beer_name_jp": "ピルス・ド・ピルス",
            "beer_name_core": "Pils de Pils",
            "search_hint": "Pils de Pils Gold Dot Beer",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/gold-dot-beer-pils-de-pils/5789629",
        },
    },
    {
        "url": "https://maruho.shop/products/helles-lager-gold-dot-473ml-heater-allen",
        "name": "Helles Lager Gold Dot 473ml/Heater Allen",
        "untappd_url": "https://untappd.com/b/gold-dot-beer-helles-lager/5348711",
        "gemini_update": {
            "brewery_name_en": "Gold Dot Beer",
            "brewery_name_jp": "ゴールドドットビア",
            "beer_name_en": "Helles Lager",
            "beer_name_jp": "ヘレスラガー",
            "beer_name_core": "Helles Lager",
            "search_hint": "Helles Lager Gold Dot Beer",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/gold-dot-beer-helles-lager/5348711",
        },
    },
]

# 2. 未エンリッチ商品 (最優先 20件) + Untappd未紐付け在庫ビール (特定済み新規登録 3件)
NEW_ENRICH_ITEMS = [
    # --- 未エンリッチ商品 (20件) ---
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8401",
        "name": "ザ・ブルーリー / トゥエルブ・デイズ・オブ・クリスマス・エール (2026) (French Oak Fermented Belgian-Style Dubbel Ale w/ Spices) 375ml瓶 [The Bruery / 12 Days of Christmas Ale (2026)]",
        "untappd_url": "https://untappd.com/b/the-bruery-12-days-of-christmas-ale/6734053",
        "gemini_update": {
            "brewery_name_en": "The Bruery",
            "brewery_name_jp": "ザ・ブルーリー",
            "beer_name_en": "12 Days of Christmas Ale",
            "beer_name_jp": "トゥエルブ・デイズ・オブ・クリスマス・エール (2026)",
            "beer_name_core": "12 Days of Christmas Ale",
            "search_hint": "12 Days of Christmas Ale The Bruery",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/the-bruery-12-days-of-christmas-ale/6734053",
        },
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8400",
        "name": "ザ・ブルーリー / ブラックチューズデー 2026 (Barrel-aged Imperial Stout) 375ml瓶 [The Bruery / Black Tuesday 2026]",
        "untappd_url": "https://untappd.com/b/the-bruery-black-tuesday-2026/7009515",
        "gemini_update": {
            "brewery_name_en": "The Bruery",
            "brewery_name_jp": "ザ・ブルーリー",
            "beer_name_en": "Black Tuesday (2026)",
            "beer_name_jp": "ブラックチューズデー 2026",
            "beer_name_core": "Black Tuesday",
            "search_hint": "Black Tuesday 2026 The Bruery",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/the-bruery-black-tuesday-2026/7009515",
        },
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8406",
        "name": "トパトパ / アザッカIPA (Single Hop IPA) 355ml缶 [Topa Topa Brewing / Azacca IPA]",
        "untappd_url": "https://untappd.com/b/topa-topa-brewing-co-solitude-series-azacca/1263844",
        "gemini_update": {
            "brewery_name_en": "Topa Topa Brewing Co.",
            "brewery_name_jp": "トパトパ",
            "beer_name_en": "Solitude Series: Azacca",
            "beer_name_jp": "アザッカIPA",
            "beer_name_core": "Azacca IPA",
            "search_hint": "Solitude Series Azacca Topa Topa Brewing Co.",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/topa-topa-brewing-co-solitude-series-azacca/1263844",
        },
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8405",
        "name": "トパトパ / クラッシュIPA (Single Hop IPA) 355ml缶 [Topa Topa Brewing / Krush IPA]",
        "untappd_url": "https://untappd.com/b/topa-topa-brewing-co-solitude-series-krush-ipa/7443282",
        "gemini_update": {
            "brewery_name_en": "Topa Topa Brewing Co.",
            "brewery_name_jp": "トパトパ",
            "beer_name_en": "Solitude Series - Krush IPA",
            "beer_name_jp": "クラッシュIPA",
            "beer_name_core": "Krush IPA",
            "search_hint": "Solitude Series Krush IPA Topa Topa Brewing Co.",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/topa-topa-brewing-co-solitude-series-krush-ipa/7443282",
        },
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8404",
        "name": "トパトパ / エルドラドIPA (Single Hop IPA) 355ml缶 [Topa Topa Brewing / El Dorado IPA]",
        "untappd_url": "https://untappd.com/b/topa-topa-brewing-co-el-dorado-ipa/7654338",
        "gemini_update": {
            "brewery_name_en": "Topa Topa Brewing Co.",
            "brewery_name_jp": "トパトパ",
            "beer_name_en": "El Dorado IPA",
            "beer_name_jp": "エルドラドIPA",
            "beer_name_core": "El Dorado IPA",
            "search_hint": "El Dorado IPA Topa Topa Brewing Co.",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/topa-topa-brewing-co-el-dorado-ipa/7654338",
        },
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8403",
        "name": "トパトパ x ソサエティ / ファスト・フレンズ (DDH West Coast IPA) 473ml缶 [Topa Topa x Societe / Fast Friends]",
        "untappd_url": "https://untappd.com/b/topa-topa-brewing-co-fast-friends/7018557",
        "gemini_update": {
            "brewery_name_en": "Topa Topa Brewing Co.",
            "brewery_name_jp": "トパトパ",
            "beer_name_en": "Fast Friends",
            "beer_name_jp": "ファスト・フレンズ",
            "beer_name_core": "Fast Friends",
            "search_hint": "Fast Friends Topa Topa Brewing Co. Societe",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/topa-topa-brewing-co-fast-friends/7018557",
        },
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8402",
        "name": "コロナドブリューイング / ダンジョンズ (Blood Orange Hazy IPA) 473ml缶 [Coronado Brewing / Dungeons]",
        "untappd_url": "https://untappd.com/b/coronado-brewing-company-dungeons/6921482",
        "gemini_update": {
            "brewery_name_en": "Coronado Brewing Company",
            "brewery_name_jp": "コロナドブリューイング",
            "beer_name_en": "Dungeons",
            "beer_name_jp": "ダンジョンズ",
            "beer_name_core": "Dungeons",
            "search_hint": "Dungeons Coronado Brewing Company",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/coronado-brewing-company-dungeons/6921482",
        },
    },
    {
        "url": "https://151l.shop/?pid=194559000",
        "name": "【11/22（日）または24（火）入荷予定】オフスクリプト×ミリュー　イェア、サイエンス！　空輸（Off Script Brewing Yeah, Science!）",
        "untappd_url": "https://untappd.com/b/off-script-brewing-yeah-science/7161772",
        "gemini_update": {
            "brewery_name_en": "Off Script Brewing",
            "brewery_name_jp": "オフスクリプト",
            "beer_name_en": "Yeah, Science!",
            "beer_name_jp": "イェア、サイエンス！",
            "beer_name_core": "Yeah, Science!",
            "search_hint": "Yeah, Science! Off Script Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/off-script-brewing-yeah-science/7161772",
        },
    },
    {
        "url": "https://151l.shop/?pid=194558731",
        "name": "【11/22（日）または24（火）入荷予定】リリック　フィアーアディクテッド　空輸（Lyric Brewing Company Fear Addicted）",
        "untappd_url": "https://untappd.com/b/lyric-brewing-company-fear-addicted-2026/7187613",
        "gemini_update": {
            "brewery_name_en": "Lyric Brewing Company",
            "brewery_name_jp": "リリック",
            "beer_name_en": "Fear Addicted (2026)",
            "beer_name_jp": "フィアーアディクテッド",
            "beer_name_core": "Fear Addicted",
            "search_hint": "Fear Addicted 2026 Lyric Brewing Company",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/lyric-brewing-company-fear-addicted-2026/7187613",
        },
    },
    {
        "url": "https://151l.shop/?pid=194558691",
        "name": "【11/22（日）または24（火）入荷予定】リリック　ファミリアーヒーローズ　空輸（Lyric Brewing Company Familiar Heroes）",
        "untappd_url": "https://untappd.com/b/lyric-brewing-company-familiar-heroes-2026/7223006",
        "gemini_update": {
            "brewery_name_en": "Lyric Brewing Company",
            "brewery_name_jp": "リリック",
            "beer_name_en": "Familiar Heroes (2026)",
            "beer_name_jp": "ファミリアーヒーローズ",
            "beer_name_core": "Familiar Heroes",
            "search_hint": "Familiar Heroes 2026 Lyric Brewing Company",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/lyric-brewing-company-familiar-heroes-2026/7223006",
        },
    },
    {
        "url": "https://151l.shop/?pid=194558770",
        "name": "【11/22（日）または24（火）入荷予定】リリック×メッソーレム　デスグリーツミーワーム　空輸（Lyric Brewing Company Death Greets Me Warm）",
        "untappd_url": "https://untappd.com/b/lyric-brewing-company-death-greets-me-warm/7187555",
        "gemini_update": {
            "brewery_name_en": "Lyric Brewing Company",
            "brewery_name_jp": "リリック",
            "beer_name_en": "Death Greets Me Warm",
            "beer_name_jp": "デスグリーツミーワーム",
            "beer_name_core": "Death Greets Me Warm",
            "search_hint": "Death Greets Me Warm Lyric Brewing Company Messorem",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/lyric-brewing-company-death-greets-me-warm/7187555",
        },
    },
    {
        "url": "https://151l.shop/?pid=194558669",
        "name": "【11/22（日）または24（火）入荷予定】テスト×RaR　ミュージックオブスフィアーズ　空輸（TEST Music Of The Spheres）",
        "untappd_url": "https://untappd.com/b/test-music-of-the-spheres/7609930",
        "gemini_update": {
            "brewery_name_en": "TEST",
            "brewery_name_jp": "テスト",
            "beer_name_en": "Music of the Spheres",
            "beer_name_jp": "ミュージックオブスフィアーズ",
            "beer_name_core": "Music of the Spheres",
            "search_hint": "Music of the Spheres TEST",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/test-music-of-the-spheres/7609930",
        },
    },
    {
        "url": "https://151l.shop/?pid=194558650",
        "name": "【11/22（日）または24（火）入荷予定】テスト×イーブルツインNY　チケッツトゥザサンセット　空輸（TEST Tickets To the Sunset）",
        "untappd_url": "https://untappd.com/b/test-tickets-to-the-sunset/6921498",
        "gemini_update": {
            "brewery_name_en": "TEST",
            "brewery_name_jp": "テスト",
            "beer_name_en": "Tickets To the Sunset",
            "beer_name_jp": "チケッツトゥザサンセット",
            "beer_name_core": "Tickets To the Sunset",
            "search_hint": "Tickets To the Sunset TEST",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/test-tickets-to-the-sunset/6921498",
        },
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000001597",
        "name": "【Kadoya Nouveau/伊勢角屋麦酒】",
        "untappd_url": None,  # 2026年復活作(ABV 9%)はUntappd未登録 (2021年版はABV 8.5%の過去レシピ)
        "gemini_update": {
            "brewery_name_en": "ISEKADO",
            "brewery_name_jp": "伊勢角屋麦酒",
            "beer_name_en": "Kadoya Nouveau (2026)",
            "beer_name_jp": "Kadoya Nouveau",
            "beer_name_core": "Kadoya Nouveau",
            "search_hint": "Kadoya Nouveau 2026 ISEKADO",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": None,
        },
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000002124",
        "name": "【7種の桃のエール/サンクトガーレン】",
        "untappd_url": "https://untappd.com/b/sankt-gallen-brewery-7-kinds-of-peach-ale-7-2026/7614517",
        "gemini_update": {
            "brewery_name_en": "Sankt Gallen Brewery",
            "brewery_name_jp": "サンクトガーレン",
            "beer_name_en": "7 Kinds of Peach Ale (2026)",
            "beer_name_jp": "7種の桃のエール",
            "beer_name_core": "7 Kinds of Peach Ale",
            "search_hint": "7 Kinds of Peach Ale 2026 Sankt Gallen Brewery",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/sankt-gallen-brewery-7-kinds-of-peach-ale-7-2026/7614517",
        },
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000003455",
        "name": "【el Diablo 2026/サンクトガーレン】",
        "untappd_url": "https://untappd.com/b/sankt-gallen-brewery-el-diablo-2026/7687613",
        "gemini_update": {
            "brewery_name_en": "Sankt Gallen Brewery",
            "brewery_name_jp": "サンクトガーレン",
            "beer_name_en": "El Diablo (2026)",
            "beer_name_jp": "el Diablo 2026",
            "beer_name_core": "el Diablo",
            "search_hint": "El Diablo 2026 Sankt Gallen Brewery",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/sankt-gallen-brewery-el-diablo-2026/7687613",
        },
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000003454",
        "name": "【Un angel 2026/サンクトガーレン】",
        "untappd_url": "https://untappd.com/b/sankt-gallen-brewery-un-angel-2026/7687605",
        "gemini_update": {
            "brewery_name_en": "Sankt Gallen Brewery",
            "brewery_name_jp": "サンクトガーレン",
            "beer_name_en": "Un Angel (2026)",
            "beer_name_jp": "Un angel 2026",
            "beer_name_core": "Un Angel",
            "search_hint": "Un Angel 2026 Sankt Gallen Brewery",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/sankt-gallen-brewery-un-angel-2026/7687605",
        },
    },
    {
        "url": "https://beervolta.com/?pid=194547586",
        "name": "ウェストコースト ボイドエンジェル / West Coast ( WCB ) Void Angel",
        "untappd_url": "https://untappd.com/b/west-coast-brewing-void-angel/6596530",
        "gemini_update": {
            "brewery_name_en": "West Coast Brewing",
            "brewery_name_jp": "ウェストコーストブルーイング",
            "beer_name_en": "Void Angel",
            "beer_name_jp": "ボイドエンジェル",
            "beer_name_core": "Void Angel",
            "search_hint": "Void Angel West Coast Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/west-coast-brewing-void-angel/6596530",
        },
    },
    {
        "url": "https://maruho.shop/products/black-tuesday-375ml-the-bruery",
        "name": "Black Tuesday 2026 375ml/The Bruery",
        "untappd_url": "https://untappd.com/b/the-bruery-black-tuesday-2026/7009515",
        "gemini_update": {
            "brewery_name_en": "The Bruery",
            "brewery_name_jp": "ザ・ブルーリー",
            "beer_name_en": "Black Tuesday (2026)",
            "beer_name_jp": "ブラックチューズデー 2026",
            "beer_name_core": "Black Tuesday",
            "search_hint": "Black Tuesday 2026 The Bruery",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/the-bruery-black-tuesday-2026/7009515",
        },
    },
    {
        "url": "https://maruho.shop/products/12-days-of-christmas-ale-375ml-the-bruery",
        "name": "12 Days Of Christmas Ale 2026 375ml/The Bruery",
        "untappd_url": "https://untappd.com/b/the-bruery-12-days-of-christmas-ale/6734053",
        "gemini_update": {
            "brewery_name_en": "The Bruery",
            "brewery_name_jp": "ザ・ブルーリー",
            "beer_name_en": "12 Days of Christmas Ale",
            "beer_name_jp": "12デイズ・オブ・クリスマス・エール (2026)",
            "beer_name_core": "12 Days of Christmas Ale",
            "search_hint": "12 Days of Christmas Ale The Bruery",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/the-bruery-12-days-of-christmas-ale/6734053",
        },
    },
    # --- Untappd未紐付け在庫ビール (特定済み新規登録 3件) ---
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000003450",
        "name": "【ゆらゆらハードサイダー チェリーサイダー/REC CIDER BEER WORKS】",
        "untappd_url": "https://untappd.com/b/rec-cider-beer-works-yura-yura-hard-cider-cherry-cider/6825228",
        "gemini_update": {
            "brewery_name_en": "REC Cider Beer Works",
            "brewery_name_jp": "レックサイダー",
            "beer_name_en": "Yura Yura Hard Cider Cherry Cider",
            "beer_name_jp": "ゆらゆらハードサイダー チェリーサイダー",
            "beer_name_core": "Yura Yura Hard Cider Cherry Cider",
            "search_hint": "Yura Yura Hard Cider Cherry Cider REC Cider Beer Works",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/rec-cider-beer-works-yura-yura-hard-cider-cherry-cider/6825228",
        },
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000003449",
        "name": "【ゆらゆらハードサイダー ニュートーン/REC CIDER BEER WORKS】",
        "untappd_url": "https://untappd.com/b/rec-cider-beer-works-new-tone-cider/6220908",
        "gemini_update": {
            "brewery_name_en": "REC Cider Beer Works",
            "brewery_name_jp": "レックサイダー",
            "beer_name_en": "New-Tone Cider",
            "beer_name_jp": "ゆらゆらハードサイダー ニュートーン",
            "beer_name_core": "New-Tone Cider",
            "search_hint": "New-Tone Cider REC Cider Beer Works",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/rec-cider-beer-works-new-tone-cider/6220908",
        },
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8342",
        "name": "フェアアイル / コーンラガー 473ml缶 [Fair Isle Brewing / Corn Lager]",
        "untappd_url": "https://untappd.com/b/fair-isle-brewing-oaxacan-green-corn-lager/6769624",
        "gemini_update": {
            "brewery_name_en": "Fair Isle Brewing",
            "brewery_name_jp": "フェアアイル",
            "beer_name_en": "Oaxacan Green Corn Lager",
            "beer_name_jp": "コーンラガー",
            "beer_name_core": "Oaxacan Green Corn Lager",
            "search_hint": "Oaxacan Green Corn Lager Fair Isle Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/fair-isle-brewing-oaxacan-green-corn-lager/6769624",
        },
    },
]

# 3. Untappd未登録確認済みアイテム (調査日時のみ更新)
UNLINKED_CHECKED_URLS = [
    "https://beer-chouseiya.shop/shopdetail/000000003451",  # ゆらゆらハードサイダー アップルバース/REC CIDER BEER WORKS (Untappd未登録)
    "https://beer-chouseiya.shop/shopdetail/000000001311",  # STORMY DUDES FESTA 2026/CraftRock× RAZORS EDGE (2026年版未登録)
]

# 4. Untappd詳細取得・最新化対象 (新規・是正・ローリング対象・直近確認)
BEER_REFRESH_URLS = [
    # 是正対象 (Gold Dot Beer)
    "https://untappd.com/b/gold-dot-beer-pils-de-pils/5789629",
    "https://untappd.com/b/gold-dot-beer-helles-lager/5348711",
    # 新規エンリッチ対象
    "https://untappd.com/b/the-bruery-12-days-of-christmas-ale/6734053",
    "https://untappd.com/b/the-bruery-black-tuesday-2026/7009515",
    "https://untappd.com/b/topa-topa-brewing-co-solitude-series-azacca/1263844",
    "https://untappd.com/b/topa-topa-brewing-co-solitude-series-krush-ipa/7443282",
    "https://untappd.com/b/topa-topa-brewing-co-el-dorado-ipa/7654338",
    "https://untappd.com/b/topa-topa-brewing-co-fast-friends/7018557",
    "https://untappd.com/b/coronado-brewing-company-dungeons/6921482",
    "https://untappd.com/b/off-script-brewing-yeah-science/7161772",
    "https://untappd.com/b/lyric-brewing-company-fear-addicted-2026/7187613",
    "https://untappd.com/b/lyric-brewing-company-familiar-heroes-2026/7223006",
    "https://untappd.com/b/lyric-brewing-company-death-greets-me-warm/7187555",
    "https://untappd.com/b/test-music-of-the-spheres/7609930",
    "https://untappd.com/b/test-tickets-to-the-sunset/6921498",
    "https://untappd.com/b/sankt-gallen-brewery-7-kinds-of-peach-ale-7-2026/7614517",
    "https://untappd.com/b/sankt-gallen-brewery-el-diablo-2026/7687613",
    "https://untappd.com/b/sankt-gallen-brewery-un-angel-2026/7687605",
    "https://untappd.com/b/west-coast-brewing-void-angel/6596530",
    # 未紐付けから新規特定
    "https://untappd.com/b/rec-cider-beer-works-yura-yura-hard-cider-cherry-cider/6825228",
    "https://untappd.com/b/rec-cider-beer-works-new-tone-cider/6220908",
    "https://untappd.com/b/fair-isle-brewing-oaxacan-green-corn-lager/6769624",
    # ローリング巡回監査 (5件)
    "https://untappd.com/b/topa-topa-brewing-company-chief-peak-ipa/1117720",
    "https://untappd.com/b/isekado-jungle-fantasy/6366593",
    "https://untappd.com/b/ise-kadoya-brain-melting-ultra-heaven-3-x-ipa/6653697",
    "https://untappd.com/b/isekado-the-silence-of-the-cats/7610735",
    "https://untappd.com/b/burgeon-beer-company-treevana/1919989",
    # 直近確認対象 (残り3件も念のため最新化)
    "https://untappd.com/b/fremont-brewing-the-rusty-nail-2026/6750086",
    "https://untappd.com/b/fremont-brewing-17th-anniversary-barrel-aged-golden-barleywine-ale-2026/6831488",
    "https://untappd.com/b/fremont-brewing-head-full-of-fresh-hops-2026/6999000",
]


def run_db_op(op_func, max_retries=3, delay=1.0):
    for attempt in range(max_retries):
        try:
            return op_func()
        except Exception as e:
            logger.warning(f"DB operation failed (attempt {attempt+1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                raise e
            time.sleep(delay * (attempt + 1))


async def main():
    sb = get_supabase_client()
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. 誤紐付け・メタデータ是正
    logger.info(f"\n[1] Correcting {len(FIX_MISASSIGNED_ITEMS)} misassigned/mismatched beer items...")
    for item in FIX_MISASSIGNED_ITEMS:
        url = item["url"]
        untappd_url = item["untappd_url"]
        gem_update = dict(item["gemini_update"])

        logger.info(f"  Fixing {url} -> {untappd_url}")

        gem_update["url"] = url
        gem_update["updated_at"] = now_iso
        run_db_op(lambda g=gem_update: sync_execute(sb.table("gemini_data").upsert(g, on_conflict="url")))

        run_db_op(lambda u=url, uu=untappd_url: sync_execute(sb.table("scraped_beers").update({
            "untappd_url": uu,
            "untappd_enriched_at": now_iso,
        }).eq("url", u)))

    # 2. 新規・未紐付け特定商品のエンリッチ登録
    logger.info(f"\n[2] Enriching {len(NEW_ENRICH_ITEMS)} items...")
    for item in NEW_ENRICH_ITEMS:
        url = item["url"]
        untappd_url = item["untappd_url"]
        gem_update = dict(item["gemini_update"])

        logger.info(f"  Enriching {url} -> {untappd_url}")

        gem_update["url"] = url
        gem_update["updated_at"] = now_iso
        run_db_op(lambda g=gem_update: sync_execute(sb.table("gemini_data").upsert(g, on_conflict="url")))

        run_db_op(lambda u=url, uu=untappd_url: sync_execute(sb.table("scraped_beers").update({
            "untappd_url": uu,
            "untappd_enriched_at": now_iso,
        }).eq("url", u)))

    # 3. Untappd未登録ビール調査済みマーク更新
    logger.info(f"\n[3] Updating investigation timestamp for {len(UNLINKED_CHECKED_URLS)} unlinked beers...")
    for url in UNLINKED_CHECKED_URLS:
        logger.info(f"  Checked (still unlinked on Untappd): {url}")
        run_db_op(lambda u=url: sync_execute(sb.table("scraped_beers").update({
            "untappd_enriched_at": now_iso,
        }).eq("url", u)))

    # 4. Untappd データの詳細取得・最新化
    logger.info(f"\n[4] Scraping & updating Untappd details for {len(BEER_REFRESH_URLS)} beers...")
    for untappd_url in BEER_REFRESH_URLS:
        logger.info(f"  Scraping details for {untappd_url}...")
        details = await scrape_beer_details(untappd_url)
        if details:
            payload = map_details_to_payload(details)
            payload["untappd_url"] = untappd_url
            payload["fetched_at"] = now_iso
            run_db_op(lambda p=payload: sync_execute(sb.table("untappd_data").upsert(p, on_conflict="untappd_url")))
            logger.info(
                f"  ✅ Updated: [{details.get('untappd_brewery_name')}] {details.get('untappd_beer_name')} "
                f"| Rating: {details.get('untappd_rating')} | Checkins: {details.get('untappd_rating_count')}"
            )
        else:
            logger.warning(f"  ❌ Failed to scrape details for {untappd_url}")
        await asyncio.sleep(0.5)

    await close_async_client()

    # 5. マテリアライズドビューのリフレッシュ
    logger.info("\n[5] Refreshing Materialized View (beer_info_view)...")
    run_db_op(lambda: refresh_materialized_view(sb, logger))
    logger.info("✅ Materialized view refreshed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
