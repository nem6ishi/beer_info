import asyncio
import logging
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client, refresh_materialized_view
from backend.src.services.untappd.http_client import scrape_beer_details
from backend.src.commands.enrich_untappd import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 1. 未エンリッチ商品（特定済みUntappd URL）
NEW_ENRICH_ITEMS = [
    # --- アローム (Trademark Brewing) ---
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8200",
        "untappd_url": "https://untappd.com/b/trademark-brewing-codebreaker-west-coast-ipa/3903203",
        "gemini_update": {
            "brewery_name_en": "Trademark Brewing",
            "brewery_name_jp": "トレードマーク",
            "beer_name_en": "Codebreaker West Coast IPA",
            "beer_name_jp": "コードブレイカー",
            "beer_name_core": "Codebreaker",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/trademark-brewing-codebreaker-west-coast-ipa/3903203"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8204",
        "untappd_url": "https://untappd.com/b/trademark-brewing-oh-l-a-la/6374667",
        "gemini_update": {
            "brewery_name_en": "Trademark Brewing",
            "brewery_name_jp": "トレードマーク",
            "beer_name_en": "Oh Là Là",
            "beer_name_jp": "オー・ラ・ラ",
            "beer_name_core": "Oh La La",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/trademark-brewing-oh-l-a-la/6374667"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8203",
        "untappd_url": "https://untappd.com/b/trademark-brewing-complicated-shirt/6885467",
        "gemini_update": {
            "brewery_name_en": "Trademark Brewing",
            "brewery_name_jp": "トレードマーク",
            "beer_name_en": "Complicated Shirt",
            "beer_name_jp": "コンプリケイテッド・シャツ",
            "beer_name_core": "Complicated Shirt",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/trademark-brewing-complicated-shirt/6885467"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8202",
        "untappd_url": "https://untappd.com/b/trademark-brewing-playa-de-noche/6043964",
        "gemini_update": {
            "brewery_name_en": "Trademark Brewing",
            "brewery_name_jp": "トレードマーク",
            "beer_name_en": "Playa de Noche",
            "beer_name_jp": "プラヤ・デ・ノーチェ",
            "beer_name_core": "Playa de Noche",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/trademark-brewing-playa-de-noche/6043964"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8201",
        "untappd_url": "https://untappd.com/b/trademark-brewing-family-truckster/6688763",
        "gemini_update": {
            "brewery_name_en": "Trademark Brewing",
            "brewery_name_jp": "トレードマーク",
            "beer_name_en": "Family Truckster",
            "beer_name_jp": "ファミリー・トラックスター",
            "beer_name_core": "Family Truckster",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/trademark-brewing-family-truckster/6688763"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8198",
        "untappd_url": "https://untappd.com/b/trademark-brewing-hili-smash/4849351",
        "gemini_update": {
            "brewery_name_en": "Trademark Brewing",
            "brewery_name_jp": "トレードマーク",
            "beer_name_en": "HiLi Smash",
            "beer_name_jp": "ハイライ・スマッシュ",
            "beer_name_core": "HiLi Smash",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/trademark-brewing-hili-smash/4849351"
        }
    },
    # --- アローム (Crooked Stave) ---
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8197",
        "untappd_url": "https://untappd.com/b/crooked-stave-brewing-co-funk-it-up/3577500",
        "gemini_update": {
            "brewery_name_en": "Crooked Stave Brewing Co.",
            "brewery_name_jp": "クルケッドステイブ",
            "beer_name_en": "Funk It Up",
            "beer_name_jp": "ファンク・イット・アップ",
            "beer_name_core": "Funk It Up",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/crooked-stave-brewing-co-funk-it-up/3577500"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8196",
        "untappd_url": "https://untappd.com/b/crooked-stave-brewing-co-st-bretta/2146225",
        "gemini_update": {
            "brewery_name_en": "Crooked Stave Brewing Co.",
            "brewery_name_jp": "クルケッドステイブ",
            "beer_name_en": "St. Bretta",
            "beer_name_jp": "セントブレッタ",
            "beer_name_core": "St Bretta",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/crooked-stave-brewing-co-st-bretta/2146225"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8195",
        "untappd_url": "https://untappd.com/b/crooked-stave-brewing-co-juicy-east-ipa/3911490",
        "gemini_update": {
            "brewery_name_en": "Crooked Stave Brewing Co.",
            "brewery_name_jp": "クルケッドステイブ",
            "beer_name_en": "Juicy East IPA",
            "beer_name_jp": "ジューシー・イースト",
            "beer_name_core": "Juicy East",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/crooked-stave-brewing-co-juicy-east-ipa/3911490"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8194",
        "untappd_url": "https://untappd.com/b/crooked-stave-brewing-co-sour-rose/1702801",
        "gemini_update": {
            "brewery_name_en": "Crooked Stave Brewing Co.",
            "brewery_name_jp": "クルケッドステイブ",
            "beer_name_en": "Sour Rosé",
            "beer_name_jp": "サワーロゼ",
            "beer_name_core": "Sour Rose",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/crooked-stave-brewing-co-sour-rose/1702801"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8193",
        "untappd_url": "https://untappd.com/b/crooked-stave-brewing-co-nz-pils/6287331",
        "gemini_update": {
            "brewery_name_en": "Crooked Stave Brewing Co.",
            "brewery_name_jp": "クルケッドステイブ",
            "beer_name_en": "NZ Pils",
            "beer_name_jp": "ニュージーピルス",
            "beer_name_core": "NZ Pils",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/crooked-stave-brewing-co-nz-pils/6287331"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8192",
        "untappd_url": "https://untappd.com/b/crooked-stave-brewing-co-sour-rita/4140538",
        "gemini_update": {
            "brewery_name_en": "Crooked Stave Brewing Co.",
            "brewery_name_jp": "クルケッドステイブ",
            "beer_name_en": "Sour Rita",
            "beer_name_jp": "サワーリータ",
            "beer_name_core": "Sour Rita",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/crooked-stave-brewing-co-sour-rita/4140538"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8191",
        "untappd_url": "https://untappd.com/b/crooked-stave-brewing-co-juicy-west/4139309",
        "gemini_update": {
            "brewery_name_en": "Crooked Stave Brewing Co.",
            "brewery_name_jp": "クルケッドステイブ",
            "beer_name_en": "Juicy West",
            "beer_name_jp": "ジューシー・ウェスト",
            "beer_name_core": "Juicy West",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/crooked-stave-brewing-co-juicy-west/4139309"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8190",
        "untappd_url": "https://untappd.com/b/crooked-stave-brewing-co-just-peachy/5446501",
        "gemini_update": {
            "brewery_name_en": "Crooked Stave Brewing Co.",
            "brewery_name_jp": "クルケッドステイブ",
            "beer_name_en": "Just Peachy",
            "beer_name_jp": "ジャスト・ピーチー",
            "beer_name_core": "Just Peachy",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/crooked-stave-brewing-co-just-peachy/5446501"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8189",
        "untappd_url": "https://untappd.com/b/crooked-stave-brewing-co-italian-pilsner/6329734",
        "gemini_update": {
            "brewery_name_en": "Crooked Stave Brewing Co.",
            "brewery_name_jp": "クルケッドステイブ",
            "beer_name_en": "Italian Pilsner",
            "beer_name_jp": "イタリアンピルスナー",
            "beer_name_core": "Italian Pilsner",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/crooked-stave-brewing-co-italian-pilsner/6329734"
        }
    },
    # --- アローム (Totopia コラボ) ---
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8188",
        "untappd_url": "https://untappd.com/b/totopia-brewery-floraphilia/7614476",
        "gemini_update": {
            "brewery_name_en": "Totopia Brewery",
            "brewery_name_jp": "トートピア",
            "beer_name_en": "Floraphilia",
            "beer_name_jp": "フローラフィリア",
            "beer_name_core": "Floraphilia",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/totopia-brewery-floraphilia/7614476"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8187",
        "untappd_url": "https://untappd.com/b/totopia-brewery-youphilia/7614478",
        "gemini_update": {
            "brewery_name_en": "Totopia Brewery",
            "brewery_name_jp": "トートピア",
            "beer_name_en": "Youphilia",
            "beer_name_jp": "ユーフィリア",
            "beer_name_core": "Youphilia",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/totopia-brewery-youphilia/7614478"
        }
    },
    # --- 一期一会～る ---
    {
        "url": "https://151l.shop/?pid=194083826",
        "untappd_url": "https://untappd.com/b/georgetown-brewing-company-bodhizafa/1094728",
        "gemini_update": {
            "brewery_name_en": "Georgetown Brewing Company",
            "brewery_name_jp": "ジョージタウン",
            "beer_name_en": "Bodhizafa IPA",
            "beer_name_jp": "ボーディザファIPA",
            "beer_name_core": "Bodhizafa",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/georgetown-brewing-company-bodhizafa/1094728"
        }
    },
    {
        "url": "https://151l.shop/?pid=194083833",
        "untappd_url": "https://untappd.com/b/georgetown-brewing-company-lucille/8812",
        "gemini_update": {
            "brewery_name_en": "Georgetown Brewing Company",
            "brewery_name_jp": "ジョージタウン",
            "beer_name_en": "Lucille IPA",
            "beer_name_jp": "ルシールIPA",
            "beer_name_core": "Lucille",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/georgetown-brewing-company-lucille/8812"
        }
    },
    {
        "url": "https://151l.shop/?pid=194083768",
        "untappd_url": "https://untappd.com/b/uchu-brewing-high-uchu-high-2026/7615405",
        "gemini_update": {
            "brewery_name_en": "UCHU BREWING",
            "brewery_name_jp": "うちゅうブルーイング",
            "beer_name_en": "宇宙HIGH(UCHU HIGH)(2026-)",
            "beer_name_jp": "うちゅうハイ",
            "beer_name_core": "UCHU HIGH",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/uchu-brewing-high-uchu-high-2026/7615405"
        }
    },
    {
        "url": "https://151l.shop/?pid=194079996",
        "untappd_url": "https://untappd.com/b/vertere-spinosa/5983194",
        "gemini_update": {
            "brewery_name_en": "VERTERE",
            "brewery_name_jp": "バテレ",
            "beer_name_en": "Spinosa",
            "beer_name_jp": "スピノザ",
            "beer_name_core": "Spinosa",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/vertere-spinosa/5983194"
        }
    },
    {
        "url": "https://151l.shop/?pid=193944737",
        "untappd_url": "https://untappd.com/b/electric-eye-beer-co-golden-riff-society/6781488",
        "gemini_update": {
            "brewery_name_en": "Electric Eye Beer Co.",
            "brewery_name_jp": "エレクトリックアイ",
            "beer_name_en": "Golden Riff Society",
            "beer_name_jp": "ゴールデンリフソサエティ",
            "beer_name_core": "Golden Riff Society",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/electric-eye-beer-co-golden-riff-society/6781488"
        }
    },
    # --- BEER VOLTA ---
    {
        "url": "https://beervolta.com/?pid=194070855",
        "untappd_url": "https://untappd.com/b/windsor-and-eton-brewery-guardsman/50084",
        "gemini_update": {
            "brewery_name_en": "Windsor & Eton Brewery",
            "brewery_name_jp": "ウィンザー・アンド・イートン",
            "beer_name_en": "Guardsman",
            "beer_name_jp": "ガーズマン",
            "beer_name_core": "Guardsman",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/windsor-and-eton-brewery-guardsman/50084"
        }
    },
    {
        "url": "https://beervolta.com/?pid=194070854",
        "untappd_url": "https://untappd.com/b/windsor-and-eton-windsor-knot/46803",
        "gemini_update": {
            "brewery_name_en": "Windsor & Eton Brewery",
            "brewery_name_jp": "ウィンザー・アンド・イートン",
            "beer_name_en": "Windsor Knot",
            "beer_name_jp": "ウィンザー ノット",
            "beer_name_core": "Windsor Knot",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/windsor-and-eton-windsor-knot/46803"
        }
    },
    {
        "url": "https://beervolta.com/?pid=194070853",
        "untappd_url": "https://untappd.com/b/whiplash-disco-mystic/4100870",
        "gemini_update": {
            "brewery_name_en": "Whiplash",
            "brewery_name_jp": "ウィップラッシュ",
            "beer_name_en": "Disco Mystic",
            "beer_name_jp": "ディスコ ミスティック",
            "beer_name_core": "Disco Mystic",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/whiplash-disco-mystic/4100870"
        }
    },
    {
        "url": "https://beervolta.com/?pid=194070852",
        "untappd_url": "https://untappd.com/b/whiplash-irel/7070740",
        "gemini_update": {
            "brewery_name_en": "Whiplash",
            "brewery_name_jp": "ウィップラッシュ",
            "beer_name_en": "Irel",
            "beer_name_jp": "アイル",
            "beer_name_core": "Irel",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/whiplash-irel/7070740"
        }
    },
    {
        "url": "https://beervolta.com/?pid=194070851",
        "untappd_url": "https://untappd.com/b/whiplash-lew/7070903",
        "gemini_update": {
            "brewery_name_en": "Whiplash",
            "brewery_name_jp": "ウィップラッシュ",
            "beer_name_en": "Lew",
            "beer_name_jp": "ルー",
            "beer_name_core": "Lew",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/whiplash-lew/7070903"
        }
    },
    {
        "url": "https://beervolta.com/?pid=194070850",
        "untappd_url": "https://untappd.com/b/whiplash-desire-lines/5779099",
        "gemini_update": {
            "brewery_name_en": "Whiplash",
            "brewery_name_jp": "ウィップラッシュ",
            "beer_name_en": "Desire Lines",
            "beer_name_jp": "ディザイア ラインズ",
            "beer_name_core": "Desire Lines",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/whiplash-desire-lines/5779099"
        }
    },
    {
        "url": "https://beervolta.com/?pid=194070848",
        "untappd_url": "https://untappd.com/b/whiplash-setting-sun/2994774",
        "gemini_update": {
            "brewery_name_en": "Whiplash",
            "brewery_name_jp": "ウィップラッシュ",
            "beer_name_en": "Setting Sun",
            "beer_name_jp": "セッティング サン",
            "beer_name_core": "Setting Sun",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/whiplash-setting-sun/2994774"
        }
    },
    {
        "url": "https://beervolta.com/?pid=194050124",
        "untappd_url": "https://untappd.com/b/totopia-brewery-youphilia/7614478",
        "gemini_update": {
            "brewery_name_en": "Totopia Brewery",
            "brewery_name_jp": "トートピア",
            "beer_name_en": "Youphilia",
            "beer_name_jp": "ユーフィリア（愛するあなたへ）",
            "beer_name_core": "Youphilia",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/totopia-brewery-youphilia/7614478"
        }
    },
    {
        "url": "https://beervolta.com/?pid=193912221",
        "untappd_url": "https://untappd.com/b/atsumi-peninsula-brewing-co-opapa/7615529",
        "gemini_update": {
            "brewery_name_en": "Atsumi Peninsula Brewing Co",
            "brewery_name_jp": "渥美半島醸造",
            "beer_name_en": "Opapa",
            "beer_name_jp": "オパパ",
            "beer_name_core": "Opapa",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/atsumi-peninsula-brewing-co-opapa/7615529"
        }
    },
    # --- マルホ酒店 ---
    {
        "url": "https://maruho.shop/products/la-vndl-beaux-art-330ml-prizm",
        "untappd_url": "https://untappd.com/b/vndl-beaux-arts/5247618",
        "gemini_update": {
            "brewery_name_en": "VNDL",
            "brewery_name_jp": "フリズム",
            "beer_name_en": "Beaux Arts",
            "beer_name_jp": "ブーアート",
            "beer_name_core": "Beaux Arts",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/vndl-beaux-arts/5247618"
        }
    },
    {
        "url": "https://maruho.shop/products/bien-sur-cranberries-750ml-gueuzerie-tilquin",
        "untappd_url": "https://untappd.com/b/brouwerij-de-dochter-van-de-korenaar-bien-sur-gin-sour-ale-with-cranberries/6487649",
        "gemini_update": {
            "brewery_name_en": "Brouwerij De Dochter van de Korenaar",
            "brewery_name_jp": "ドクトル・ヴァン・ドゥ・コールナール",
            "beer_name_en": "Bien-sûr Gin Sour Ale With Cranberries",
            "beer_name_jp": "ビヤンシュール & クランベリーズ",
            "beer_name_core": "Bien-sur Gin Sour Ale With Cranberries",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/brouwerij-de-dochter-van-de-korenaar-bien-sur-gin-sour-ale-with-cranberries/6487649"
        }
    },
    {
        "url": "https://maruho.shop/products/セゾンデュポン",
        "untappd_url": "https://untappd.com/b/brasserie-dupont-saison-dupont/8073",
        "gemini_update": {
            "brewery_name_en": "Brasserie Dupont",
            "brewery_name_jp": "デュポン",
            "beer_name_en": "Saison Dupont",
            "beer_name_jp": "セゾン デュポン",
            "beer_name_core": "Saison Dupont",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/brasserie-dupont-saison-dupont/8073"
        }
    },
    {
        "url": "https://maruho.shop/products/エスプレッソスタウト-常陸野ネスト",
        "untappd_url": "https://untappd.com/b/kiuchi-brewery-hitachino-nest-espresso-stout/154",
        "gemini_update": {
            "brewery_name_en": "Kiuchi Brewery",
            "brewery_name_jp": "木内酒造",
            "beer_name_en": "Hitachino Nest Espresso Stout",
            "beer_name_jp": "常陸野ネスト エスプレッソスタウト",
            "beer_name_core": "Hitachino Nest Espresso Stout",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/kiuchi-brewery-hitachino-nest-espresso-stout/154"
        }
    }
]

# 2. 非ビール商品（グッズ・RTD等：product_type='other'へ更新）
NON_BEER_ITEMS = [
    {
        "url": "https://maruho.shop/products/カミナリ-garrulo",
        "name": "カミナリ/Garrulo (マルホ酒店)",
        "product_type": "other",
        "notes": "刺繍ブランドGARRULOのワッペン/ステッカー（非ビール・グッズ）"
    },
    {
        "url": "https://maruho.shop/products/hop-glow-soda-collab-w-若潮酒造-350ml-伊勢角麦酒",
        "name": "Hop Glow Soda (collab w/若潮酒造） 350ml/伊勢角麦酒 (マルホ酒店)",
        "product_type": "other",
        "notes": "若潮酒造芋焼酎のホップ炭酸水割り・麦芽ゼロ（焼酎ソーダ/RTD）"
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000001796",
        "name": "【HOP GLOW SODA/伊勢角屋麦酒】 (ちょうせいや)",
        "product_type": "other",
        "notes": "若潮酒造芋焼酎のホップ炭酸水割り・麦芽ゼロ（焼酎ソーダ/RTD）"
    }
]

# 3. 誤紐付け是正対象アイテム
MISMATCH_FIX_ITEMS = [
    {
        "url": "https://witchcraftmarket.com/products/art-and-blood-2",
        "name": "[Collective Arts] Art & Blood 2/ アート & ブラッド 2 (WITCH CRAFT MARKET)",
        "old_untappd_url": "https://untappd.com/b/collective-arts-brewing-art-and-blood/6400938",
        "correct_untappd_url": "https://untappd.com/b/collective-arts-brewing-art-and-blood-ii/6958285",
        "gemini_update": {
            "brewery_name_en": "Collective Arts Brewing",
            "brewery_name_jp": "コレクティブアーツ",
            "beer_name_en": "Art And Blood II",
            "beer_name_jp": "アート & ブラッド 2",
            "beer_name_core": "Art And Blood II",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/collective-arts-brewing-art-and-blood-ii/6958285"
        }
    }
]

# 4. ローリング巡回・Untappdデータ最新化対象（ユニークURL）
BEER_REFRESH_URLS = [
    "https://untappd.com/b/beachwood-brewing-mocha-machine/322703",
    "https://untappd.com/b/8-wired-hop-salad/3831937",
    "https://untappd.com/b/von-ebert-brewing-volatile-substance/2696677",
    "https://untappd.com/b/tree-house-brewing-company-very-azure/5353459"
]

# 5. Untappd未登録確認済みアイテム（監査日時を更新して次回即時再検索を回避）
AUDITED_UNREGISTERED_BEERS = [
    {
        "url": "https://witchcraftmarket.com/products/maelstrom-hazy-ipa",
        "name": "[GAME BREW] 魔海侯フォルネウス MAELSTROM HAZY IPA (WITCH CRAFT MARKET)",
        "notes": "GAME BREW（佐賀）とロマ佐賀コラボ四魔貴族シリーズ新作。Untappdブルワリーページを精査し未登録を確認"
    }
]

async def main():
    sb = get_supabase_client()
    now_iso = datetime.now(timezone.utc).isoformat()

    logger.info("=" * 70)
    logger.info("🚀 Starting Hourly Beer Audit & Enrichment Pipeline (2026-10-22)")
    logger.info("=" * 70)

    # 1. 未エンリッチ商品のDB登録 & Untappdスクレイピング
    if NEW_ENRICH_ITEMS:
        logger.info(f"\n[1] Enriching {len(NEW_ENRICH_ITEMS)} unenriched beers...")
        for item in NEW_ENRICH_ITEMS:
            url = item["url"]
            untappd_url = item["untappd_url"]
            gem_update = item["gemini_update"]

            logger.info(f"  Enriching {url} -> {untappd_url}")

            # gemini_data upsert
            gem_update["url"] = url
            gem_update["updated_at"] = now_iso
            sb.table("gemini_data").upsert(gem_update, on_conflict="url").execute()

            # scraped_beers update
            sb.table("scraped_beers").update({
                "untappd_url": untappd_url,
                "untappd_enriched_at": now_iso
            }).eq("url", url).execute()

            # untappd_data scrape & upsert (スキップ可能ならスキップ)
            existing_u = sb.table("untappd_data").select("untappd_url").eq("untappd_url", untappd_url).execute()
            if existing_u.data:
                logger.info(f"  ⚡ Already in untappd_data, skipping scrape: {untappd_url}")
            else:
                details = await scrape_beer_details(untappd_url)
                if details:
                    payload = map_details_to_payload(details)
                    payload["untappd_url"] = untappd_url
                    payload["fetched_at"] = now_iso
                    sb.table("untappd_data").upsert(payload, on_conflict="untappd_url").execute()
                    logger.info(f"  ✅ Enriched & Saved: [{details.get('untappd_brewery_name')}] {details.get('untappd_beer_name')} (Rating: {details.get('untappd_rating')})")
                else:
                    logger.warning(f"  ⚠️ Could not scrape Untappd details for {untappd_url}")
                await asyncio.sleep(1.5)
    else:
        logger.info("\n[1] No unenriched beers to process.")

    # 2. 非ビール商品のステータス修正 (product_type='goods' / 'other')
    if NON_BEER_ITEMS:
        logger.info(f"\n[2] Setting {len(NON_BEER_ITEMS)} non-beer items to correct product_type...")
        for item in NON_BEER_ITEMS:
            p_url = item["url"]
            p_type = item["product_type"]
            sb.table("gemini_data").update({
                "product_type": p_type,
                "untappd_url": None,
                "updated_at": now_iso
            }).eq("url", p_url).execute()

            sb.table("scraped_beers").update({
                "untappd_url": None,
                "untappd_enriched_at": now_iso
            }).eq("url", p_url).execute()

            logger.info(f"  ✅ Updated non-beer: {item['name']}\n    -> {item['notes']}")

    # 3. 誤紐付け是正
    if MISMATCH_FIX_ITEMS:
        logger.info(f"\n[3] Fixing {len(MISMATCH_FIX_ITEMS)} mismatched Untappd links...")
        for item in MISMATCH_FIX_ITEMS:
            p_url = item["url"]
            correct_untappd = item["correct_untappd_url"]
            gem_update = item["gemini_update"]

            logger.info(f"  Fixing {item['name']}: {item['old_untappd_url']} -> {correct_untappd}")

            gem_update["url"] = p_url
            gem_update["updated_at"] = now_iso
            sb.table("gemini_data").upsert(gem_update, on_conflict="url").execute()

            sb.table("scraped_beers").update({
                "untappd_url": correct_untappd,
                "untappd_enriched_at": now_iso
            }).eq("url", p_url).execute()

            details = await scrape_beer_details(correct_untappd)
            if details:
                payload = map_details_to_payload(details)
                payload["untappd_url"] = correct_untappd
                payload["fetched_at"] = now_iso
                sb.table("untappd_data").upsert(payload, on_conflict="untappd_url").execute()
                logger.info(f"  ✅ Saved Correct Untappd Data: [{details.get('untappd_brewery_name')}] {details.get('untappd_beer_name')} (Rating: {details.get('untappd_rating')})")
            await asyncio.sleep(1.5)

    # 4. ローリング巡回・Untappd データの最新化
    logger.info(f"\n[4] Scraping & updating Untappd details for {len(BEER_REFRESH_URLS)} rolling audit beers...")
    for untappd_url in BEER_REFRESH_URLS:
        logger.info(f"  Scraping details for {untappd_url}...")
        details = await scrape_beer_details(untappd_url)
        if details:
            payload = map_details_to_payload(details)
            payload["untappd_url"] = untappd_url
            payload["fetched_at"] = now_iso
            sb.table("untappd_data").upsert(payload, on_conflict="untappd_url").execute()
            logger.info(f"  ✅ Updated: [{details.get('untappd_brewery_name')}] {details.get('untappd_beer_name')} | Rating: {details.get('untappd_rating')} | Checkins: {details.get('untappd_rating_count')}")
        else:
            logger.warning(f"  ❌ Failed to scrape details for {untappd_url}")
        await asyncio.sleep(1.5)

    # 5. Untappd未登録アイテムの監査日時更新
    logger.info(f"\n[5] Updating audit timestamps for {len(AUDITED_UNREGISTERED_BEERS)} verified unregistered beers...")
    for item in AUDITED_UNREGISTERED_BEERS:
        p_url = item["url"]
        sb.table("scraped_beers").update({
            "untappd_enriched_at": now_iso
        }).eq("url", p_url).execute()

        sb.table("gemini_data").update({
            "updated_at": now_iso
        }).eq("url", p_url).execute()

        logger.info(f"  ✅ Audited: {item['name']}\n    -> {item['notes']}")

    # 6. マテリアライズドビューのリフレッシュ
    logger.info("\n[6] Refreshing Materialized View (beer_info_view)...")
    refresh_materialized_view(sb, logger)
    logger.info("✅ Materialized view refreshed successfully!")

if __name__ == "__main__":
    asyncio.run(main())
