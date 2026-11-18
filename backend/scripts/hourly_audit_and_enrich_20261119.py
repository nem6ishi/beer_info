import asyncio
import logging
import time
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client, refresh_materialized_view, sync_execute
from backend.src.services.untappd.http_client import scrape_beer_details, close_async_client
from backend.src.core.utils import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 1. 直近追加 & ローリング監査 誤紐付け・メタデータ是正アイテム
FIX_MISASSIGNED_ITEMS = [
    {
        "url": "https://beervolta.com/?pid=184107314",
        "name": "トゥーミータートール アタスマニアンワイルド エール / Two Metre Tall A Tasmanian Wild Ale (BLEND #2) 375ml",
        "untappd_url": "https://untappd.com/b/two-metre-tall-tasmanian-wild-ale-blend-2-2023/5674720",
        "gemini_update": {
            "brewery_name_en": "Two Metre Tall",
            "brewery_name_jp": "トゥーミータートール",
            "beer_name_en": "Tasmanian Wild Ale Blend #2 (2023)",
            "beer_name_jp": "タスマニアン ワイルド エール (ブレンド #2)",
            "beer_name_core": "Tasmanian Wild Ale",
            "search_hint": "Tasmanian Wild Ale Blend #2 2023 Two Metre Tall",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/two-metre-tall-tasmanian-wild-ale-blend-2-2023/5674720",
        },
    },
    {
        "url": "https://maruho.shop/products/shadowsoftheireyes18-rarebarrel",
        "name": "Shadows of their eyes18/Rare barrel",
        "untappd_url": "https://untappd.com/b/the-rare-barrel-shadows-of-their-eyes-2018/2805619",
        "gemini_update": {
            "brewery_name_en": "The Rare Barrel",
            "brewery_name_jp": "ザ レアバレル",
            "beer_name_en": "Shadows of Their Eyes (2018)",
            "beer_name_jp": "シャドウズ オブ ゼア アイズ 2018",
            "beer_name_core": "Shadows of Their Eyes",
            "search_hint": "Shadows of Their Eyes 2018 The Rare Barrel",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/the-rare-barrel-shadows-of-their-eyes-2018/2805619",
        },
    },
]

# 2. 未エンリッチ商品 (最優先) + Untappd未紐付け在庫ビール (特定済み登録)
NEW_ENRICH_ITEMS = [
    # --- 未エンリッチ商品 (20件) ---
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8381",
        "name": "トートピアブルワリー / エンプティフォビア (空虚恐怖症) (DDH Hazy Pale Ale) 500ml缶 [Totopia Brewery / Emptyphobia]",
        "untappd_url": "https://untappd.com/b/totopia-brewery-emptyphobia/7681250",
        "gemini_update": {
            "brewery_name_en": "Totopia Brewery",
            "brewery_name_jp": "トートピアブルワリー",
            "beer_name_en": "Emptyphobia",
            "beer_name_jp": "エンプティフォビア (空虚恐怖症)",
            "beer_name_core": "Emptyphobia",
            "search_hint": "Emptyphobia Totopia Brewery",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/totopia-brewery-emptyphobia/7681250",
        },
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8380",
        "name": "トートピアブルワリー / ゾーンフォビア (領域恐怖症) (West Coast Lager) 500ml缶 [Totopia Brewery / Zonephobia]",
        "untappd_url": "https://untappd.com/b/totopia-brewery-zonephobia/7681240",
        "gemini_update": {
            "brewery_name_en": "Totopia Brewery",
            "brewery_name_jp": "トートピアブルワリー",
            "beer_name_en": "Zonephobia",
            "beer_name_jp": "ゾーンフォビア (領域恐怖症)",
            "beer_name_core": "Zonephobia",
            "search_hint": "Zonephobia Totopia Brewery",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/totopia-brewery-zonephobia/7681240",
        },
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=1196",
        "name": "うちゅうブルーイング / SUN (DDH West Coast IPA) 350ml缶 [UCHU BREWING / SUN]",
        "untappd_url": "https://untappd.com/b/uchu-brewing-sun/6031002",
        "gemini_update": {
            "brewery_name_en": "Uchu Brewing",
            "brewery_name_jp": "うちゅうブルーイング",
            "beer_name_en": "SUN",
            "beer_name_jp": "SUN",
            "beer_name_core": "SUN",
            "search_hint": "SUN Uchu Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/uchu-brewing-sun/6031002",
        },
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8379",
        "name": "うちゅうブルーイング / 宇宙IPA (DDH IPA) (2026年11月入荷) 350ml缶 [UCHU BREWING / UCHU IPA]",
        "untappd_url": "https://untappd.com/b/uchu-brewing-ipa-uchu-ipa-2026/6617021",
        "gemini_update": {
            "brewery_name_en": "Uchu Brewing",
            "brewery_name_jp": "うちゅうブルーイング",
            "beer_name_en": "宇宙IPA (UCHU IPA) (2026-)",
            "beer_name_jp": "宇宙IPA",
            "beer_name_core": "UCHU IPA",
            "search_hint": "宇宙IPA UCHU IPA 2026 Uchu Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/uchu-brewing-ipa-uchu-ipa-2026/6617021",
        },
    },
    {
        "url": "https://151l.shop/?pid=194512621",
        "name": "【11/21（土）入荷予定・おひとり様2本まで】うちゅうブルーイング　宇宙ブレイク3　缶（UCHU Brewing UCHU BREAK3）",
        "untappd_url": "https://untappd.com/b/uchu-brewing-break3-uchu-break3/7682783",
        "gemini_update": {
            "brewery_name_en": "Uchu Brewing",
            "brewery_name_jp": "うちゅうブルーイング",
            "beer_name_en": "宇宙BREAK3 (UCHU BREAK3)",
            "beer_name_jp": "宇宙ブレイク3",
            "beer_name_core": "UCHU BREAK3",
            "search_hint": "宇宙BREAK3 UCHU BREAK3 Uchu Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/uchu-brewing-break3-uchu-break3/7682783",
        },
    },
    {
        "url": "https://151l.shop/?pid=194512565",
        "name": "【11/21（土）入荷予定】うちゅうブルーイング　ミューオン　ピーチ+パッション　缶（UCHU Brewing MUON peach+passionfruit）",
        "untappd_url": "https://untappd.com/b/uchu-brewing-muon-peach-passionfruit/5212952",
        "gemini_update": {
            "brewery_name_en": "Uchu Brewing",
            "brewery_name_jp": "うちゅうブルーイング",
            "beer_name_en": "MUON peach+passionfruit",
            "beer_name_jp": "ミューオン ピーチ+パッション",
            "beer_name_core": "MUON peach+passionfruit",
            "search_hint": "MUON peach passionfruit Uchu Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/uchu-brewing-muon-peach-passionfruit/5212952",
        },
    },
    {
        "url": "https://151l.shop/?pid=194511859",
        "name": "【11/20（金）入荷予定】バテレ　スカビオサ（VERTERE Scabiosa）",
        "untappd_url": None,
        "gemini_update": {
            "brewery_name_en": "VERTERE",
            "brewery_name_jp": "バテレ",
            "beer_name_en": "Scabiosa",
            "beer_name_jp": "スカビオサ",
            "beer_name_core": "Scabiosa",
            "search_hint": "Scabiosa VERTERE",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": None,
        },
    },
    {
        "url": "https://151l.shop/?pid=194511615",
        "name": "【11/20（金）入荷予定・必ず注意事項をお読みください】トパトパ　エルドラドIPA（Topa Topa El Dorado IPA）",
        "untappd_url": "https://untappd.com/b/topa-topa-brewing-co-el-dorado-ipa/7654338",
        "gemini_update": {
            "brewery_name_en": "Topa Topa Brewing Co.",
            "brewery_name_jp": "トパトパ",
            "beer_name_en": "El Dorado IPA",
            "beer_name_jp": "エルドラド IPA",
            "beer_name_core": "El Dorado IPA",
            "search_hint": "El Dorado IPA Topa Topa Brewing Co.",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/topa-topa-brewing-co-el-dorado-ipa/7654338",
        },
    },
    {
        "url": "https://151l.shop/?pid=194511659",
        "name": "【11/20（金）入荷予定・必ず注意事項をお読みください】トパトパ　クラッシュIPA（Topa Topa  Krush IPA）",
        "untappd_url": "https://untappd.com/b/topa-topa-brewing-co-solitude-series-krush-ipa/7443282",
        "gemini_update": {
            "brewery_name_en": "Topa Topa Brewing Co.",
            "brewery_name_jp": "トパトパ",
            "beer_name_en": "Solitude Series - Krush IPA",
            "beer_name_jp": "クラッシュ IPA",
            "beer_name_core": "Krush IPA",
            "search_hint": "Solitude Series Krush IPA Topa Topa Brewing Co.",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/topa-topa-brewing-co-solitude-series-krush-ipa/7443282",
        },
    },
    {
        "url": "https://151l.shop/?pid=194511570",
        "name": "【11/20（金）入荷予定】トパトパ×ソサエティ　ファストフレンズ（Topa Topa Fast Friends）",
        "untappd_url": "https://untappd.com/b/topa-topa-brewing-co-fast-friends/7018557",
        "gemini_update": {
            "brewery_name_en": "Topa Topa Brewing Co.",
            "brewery_name_jp": "トパトパ",
            "beer_name_en": "Fast Friends",
            "beer_name_jp": "ファストフレンズ",
            "beer_name_core": "Fast Friends",
            "search_hint": "Fast Friends Topa Topa Brewing Co. Societe",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/topa-topa-brewing-co-fast-friends/7018557",
        },
    },
    {
        "url": "https://151l.shop/?pid=194511261",
        "name": "【11/20（金）入荷予定】コロナドブルーイング　ビッグウィークエンド（Coronado Brewing Big Weekend DIPA）",
        "untappd_url": "https://untappd.com/b/coronado-brewing-company-big-weekend/5040298",
        "gemini_update": {
            "brewery_name_en": "Coronado Brewing Company",
            "brewery_name_jp": "コロナドブルーイング",
            "beer_name_en": "Big Weekend",
            "beer_name_jp": "ビッグウィークエンド",
            "beer_name_core": "Big Weekend",
            "search_hint": "Big Weekend Coronado Brewing Company",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/coronado-brewing-company-big-weekend/5040298",
        },
    },
    {
        "url": "https://151l.shop/?pid=194511104",
        "name": "【11/20（金）入荷予定】コロナドブルーイング　ダンジョンズ（Coronado Brewing Dungeons）",
        "untappd_url": "https://untappd.com/b/coronado-brewing-company-dungeons/6921482",
        "gemini_update": {
            "brewery_name_en": "Coronado Brewing Company",
            "brewery_name_jp": "コロナドブルーイング",
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
        "url": "https://151l.shop/?pid=194511175",
        "name": "【11/20（金）入荷予定】コロナドブルーイング　ウィークエンドヴァイブス（Coronado Brewing Week End Vibes）",
        "untappd_url": "https://untappd.com/b/coronado-brewing-company-weekend-vibes/2868166",
        "gemini_update": {
            "brewery_name_en": "Coronado Brewing Company",
            "brewery_name_jp": "コロナドブルーイング",
            "beer_name_en": "Weekend Vibes",
            "beer_name_jp": "ウィークエンドヴァイブス",
            "beer_name_core": "Weekend Vibes",
            "search_hint": "Weekend Vibes Coronado Brewing Company",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/coronado-brewing-company-weekend-vibes/2868166",
        },
    },
    {
        "url": "https://151l.shop/?pid=194511217",
        "name": "【11/20（金）入荷予定】コロナドブルーイング　ヘイジーウィークエンド（Coronado Brewing Hazy Weekend）",
        "untappd_url": "https://untappd.com/b/coronado-brewing-company-hazy-weekend/6571217",
        "gemini_update": {
            "brewery_name_en": "Coronado Brewing Company",
            "brewery_name_jp": "コロナドブルーイング",
            "beer_name_en": "Hazy Weekend",
            "beer_name_jp": "ヘイジーウィークエンド",
            "beer_name_core": "Hazy Weekend",
            "search_hint": "Hazy Weekend Coronado Brewing Company",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/coronado-brewing-company-hazy-weekend/6571217",
        },
    },
    {
        "url": "https://151l.shop/?pid=194510603",
        "name": "【11/19（木）予定・とても美味しいイチオシブルワリー！】リクリブルーイング　ライカ（RIKRI BREWING Laika）",
        "untappd_url": "https://untappd.com/b/rikri-brewing-laika/7679547",
        "gemini_update": {
            "brewery_name_en": "RIKRI BREWING",
            "brewery_name_jp": "リクリブルーイング",
            "beer_name_en": "Laika",
            "beer_name_jp": "ライカ",
            "beer_name_core": "Laika",
            "search_hint": "Laika RIKRI BREWING",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/rikri-brewing-laika/7679547",
        },
    },
    {
        "url": "https://151l.shop/?pid=194510242",
        "name": "【11/19（木）入荷予定】トートピアブルワリー　エンプティフォビア（Totopia Brewery Emptyphobia）",
        "untappd_url": "https://untappd.com/b/totopia-brewery-emptyphobia/7681250",
        "gemini_update": {
            "brewery_name_en": "Totopia Brewery",
            "brewery_name_jp": "トートピアブルワリー",
            "beer_name_en": "Emptyphobia",
            "beer_name_jp": "エンプティフォビア",
            "beer_name_core": "Emptyphobia",
            "search_hint": "Emptyphobia Totopia Brewery",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/totopia-brewery-emptyphobia/7681250",
        },
    },
    {
        "url": "https://151l.shop/?pid=194510134",
        "name": "【11/19（木）入荷予定】トートピアブルワリー　ゾーンフォビア（Totopia Brewery  Zonephobia）",
        "untappd_url": "https://untappd.com/b/totopia-brewery-zonephobia/7681240",
        "gemini_update": {
            "brewery_name_en": "Totopia Brewery",
            "brewery_name_jp": "トートピアブルワリー",
            "beer_name_en": "Zonephobia",
            "beer_name_jp": "ゾーンフォビア",
            "beer_name_core": "Zonephobia",
            "search_hint": "Zonephobia Totopia Brewery",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/totopia-brewery-zonephobia/7681240",
        },
    },
    {
        "url": "https://151l.shop/?pid=194509573",
        "name": "【11/19（木）予定・必ず合計「6本」になるようご注文下さい】フリモント　ヘッドフルオブフレッシュホップ2026（Fremont Head Full of Fresh Hops 2026）",
        "untappd_url": "https://untappd.com/b/fremont-brewing-head-full-of-fresh-hops-2026/6999000",
        "gemini_update": {
            "brewery_name_en": "Fremont Brewing",
            "brewery_name_jp": "フリモント",
            "beer_name_en": "Head Full of Fresh Hops (2026)",
            "beer_name_jp": "ヘッドフルオブフレッシュホップ2026",
            "beer_name_core": "Head Full of Fresh Hops",
            "search_hint": "Head Full of Fresh Hops 2026 Fremont Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/fremont-brewing-head-full-of-fresh-hops-2026/6999000",
        },
    },
    {
        "url": "https://151l.shop/?pid=194509484",
        "name": "【11/19（木）予定・必ず合計「6本」になるようご注文下さい】フリモント　フィールドトゥファーメント2026（Fremont field to ferment2026）",
        "untappd_url": "https://untappd.com/b/fremont-brewing-field-to-ferment-fresh-hop-pale/1730025",
        "gemini_update": {
            "brewery_name_en": "Fremont Brewing",
            "brewery_name_jp": "フリモント",
            "beer_name_en": "Field to Ferment Fresh Hop Pale",
            "beer_name_jp": "フィールドトゥファーメント2026",
            "beer_name_core": "Field to Ferment",
            "search_hint": "Field to Ferment Fresh Hop Pale Fremont Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/fremont-brewing-field-to-ferment-fresh-hop-pale/1730025",
        },
    },
    {
        "url": "https://151l.shop/?pid=194509695",
        "name": "【11/19（木）入荷予定】フリモント　プリモ（Fremont Primo）",
        "untappd_url": "https://untappd.com/b/fremont-brewing-primo/6857834",
        "gemini_update": {
            "brewery_name_en": "Fremont Brewing",
            "brewery_name_jp": "フリモント",
            "beer_name_en": "Primo",
            "beer_name_jp": "プリモ",
            "beer_name_core": "Primo",
            "search_hint": "Primo Fremont Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/fremont-brewing-primo/6857834",
        },
    },
    {
        "url": "https://151l.shop/?pid=194510044",
        "name": "【11/19（木）予定・必ず合計「6本」になるようご注文下さい】フリモント　フレッシュホップラッシュIPA2026（Fremont fresh hop lush 2026）",
        "untappd_url": "https://untappd.com/b/fremont-brewing-fresh-hop-lush-2026/6923171",
        "gemini_update": {
            "brewery_name_en": "Fremont Brewing",
            "brewery_name_jp": "フリモント",
            "beer_name_en": "Fresh Hop Lush (2026)",
            "beer_name_jp": "フレッシュホップラッシュIPA2026",
            "beer_name_core": "Fresh Hop Lush",
            "search_hint": "Fresh Hop Lush 2026 Fremont Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/fremont-brewing-fresh-hop-lush-2026/6923171",
        },
    },
    # --- Untappd未紐付け在庫ビール (特定済み登録 3件) ---
    {
        "url": "https://witchcraftmarket.com/products/maelstrom-hazy-ipa",
        "name": "[GAME BREW] 魔海侯フォルネウス MAELSTROM HAZY IPA / メイルストローム ヘイジーIPA",
        "untappd_url": "https://untappd.com/b/game-brew/7634894",
        "gemini_update": {
            "brewery_name_en": "GAME BREW",
            "brewery_name_jp": "ゲームブリュー",
            "beer_name_en": "魔海侯 フォルネウス",
            "beer_name_jp": "魔海侯フォルネウス メイルストローム ヘイジーIPA",
            "beer_name_core": "魔海侯 フォルネウス",
            "search_hint": "魔海侯 フォルネウス GAME BREW MAELSTROM HAZY IPA",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/game-brew/7634894",
        },
    },
    {
        "url": "https://151l.shop/?pid=194418052",
        "name": "【11/13-14入荷予定】バテレ　クリスマスビアー2026　バーレーワイン（VERTERE Christmas Beer 2026 Botanical Saison）",
        "untappd_url": "https://untappd.com/b/vertere-christmas-beer-barley-wine-2026/7674248",
        "gemini_update": {
            "brewery_name_en": "VERTERE",
            "brewery_name_jp": "バテレ",
            "beer_name_en": "Christmas Beer Barley Wine (2026)",
            "beer_name_jp": "クリスマスビアー2026 バーレーワイン",
            "beer_name_core": "Christmas Beer Barley Wine",
            "search_hint": "Christmas Beer Barley Wine 2026 VERTERE",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/vertere-christmas-beer-barley-wine-2026/7674248",
        },
    },
    {
        "url": "https://maruho.shop/products/zenne-y-frontera-batch-6-750ml-drie-fonteinen",
        "name": "Zenne y Frontera Batch 6 750ml/Drie Fonteinen",
        "untappd_url": "https://untappd.com/b/brouwerij-3-fonteinen-3-fonteinen-zenne-y-frontera-season-17-18-blend-no-50/3367226",
        "gemini_update": {
            "brewery_name_en": "Brouwerij 3 Fonteinen",
            "brewery_name_jp": "ドリー フォンテイネン",
            "beer_name_en": "3 Fonteinen Zenne y Frontera (season 17|18) Blend No. 50",
            "beer_name_jp": "ゼンネ イ フロンテーラ バッチ6",
            "beer_name_core": "Zenne y Frontera",
            "search_hint": "3 Fonteinen Zenne y Frontera season 17 18 Blend No. 50 Batch 6",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/brouwerij-3-fonteinen-3-fonteinen-zenne-y-frontera-season-17-18-blend-no-50/3367226",
        },
    },
]

# 3. Untappd未登録のまま調査済みタイムスタンプを更新する商品 (次回ローリング順送り)
UNLINKED_CHECKED_URLS = [
    "https://151l.shop/?pid=193631430",  # FARMENTRY OCHA! YAMATO (Untappd未登録)
    "https://witchcraftmarket.com/products/buchikamashi-helles",  # GAME BREW 魔戦士公 アラケス BUCHIKAMASHI HELLES (Untappd未登録)
]

# 4. Untappd詳細取得・最新化対象 (新規・是正・ローリング対象)
BEER_REFRESH_URLS = [
    # 是正対象
    "https://untappd.com/b/two-metre-tall-tasmanian-wild-ale-blend-2-2023/5674720",
    "https://untappd.com/b/the-rare-barrel-shadows-of-their-eyes-2018/2805619",
    # 新規エンリッチ & 未紐付け特定 (重複排除)
    "https://untappd.com/b/totopia-brewery-emptyphobia/7681250",
    "https://untappd.com/b/totopia-brewery-zonephobia/7681240",
    "https://untappd.com/b/uchu-brewing-sun/6031002",
    "https://untappd.com/b/uchu-brewing-ipa-uchu-ipa-2026/6617021",
    "https://untappd.com/b/uchu-brewing-break3-uchu-break3/7682783",
    "https://untappd.com/b/uchu-brewing-muon-peach-passionfruit/5212952",
    "https://untappd.com/b/topa-topa-brewing-co-el-dorado-ipa/7654338",
    "https://untappd.com/b/topa-topa-brewing-co-solitude-series-krush-ipa/7443282",
    "https://untappd.com/b/topa-topa-brewing-co-fast-friends/7018557",
    "https://untappd.com/b/coronado-brewing-company-big-weekend/5040298",
    "https://untappd.com/b/coronado-brewing-company-dungeons/6921482",
    "https://untappd.com/b/coronado-brewing-company-weekend-vibes/2868166",
    "https://untappd.com/b/coronado-brewing-company-hazy-weekend/6571217",
    "https://untappd.com/b/rikri-brewing-laika/7679547",
    "https://untappd.com/b/fremont-brewing-head-full-of-fresh-hops-2026/6999000",
    "https://untappd.com/b/fremont-brewing-field-to-ferment-fresh-hop-pale/1730025",
    "https://untappd.com/b/fremont-brewing-primo/6857834",
    "https://untappd.com/b/fremont-brewing-fresh-hop-lush-2026/6923171",
    "https://untappd.com/b/game-brew/7634894",
    "https://untappd.com/b/vertere-christmas-beer-barley-wine-2026/7674248",
    "https://untappd.com/b/brouwerij-3-fonteinen-3-fonteinen-zenne-y-frontera-season-17-18-blend-no-50/3367226",
    # ローリング巡回監査 (残り4件)
    "https://untappd.com/b/the-rare-barrel-a-peach-in-reach/2283550",
    "https://untappd.com/b/deschutes-brewery-planete-plum/3712932",
    "https://untappd.com/b/far-yeast-brewing-company-kagua-rouge/185358",
    "https://untappd.com/b/kiuchi-brewery-hitachino-nest-white-ale/1573",
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
