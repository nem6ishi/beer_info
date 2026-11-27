import asyncio
import logging
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client, refresh_materialized_view
from backend.src.services.untappd.http_client import scrape_beer_details
from backend.src.commands.enrich_untappd import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 1. 新規エンリッチ商品: 27件 + 未紐付けから特定した4件 = 計31件
NEW_ENRICH_ITEMS = [
    # --- アローム ---
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8210",
        "untappd_url": "https://untappd.com/b/teenage-brewing-a-krush-banger/7615567",
        "gemini_update": {
            "brewery_name_en": "Teenage Brewing",
            "brewery_name_jp": "ティーンネイジブルーイング",
            "beer_name_en": "A Krush Banger",
            "beer_name_jp": "ア・クラッシュ・バンガー",
            "beer_name_core": "A Krush Banger",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/teenage-brewing-a-krush-banger/7615567"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8211",
        "untappd_url": "https://untappd.com/b/teenage-brewing-loom/7615563",
        "gemini_update": {
            "brewery_name_en": "Teenage Brewing",
            "brewery_name_jp": "ティーンネイジブルーイング",
            "beer_name_en": "Loom",
            "beer_name_jp": "ルーム",
            "beer_name_core": "Loom",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/teenage-brewing-loom/7615563"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=3492",
        "untappd_url": "https://untappd.com/b/uchu-brewing-high-uchu-high-2026/7615405",
        "gemini_update": {
            "brewery_name_en": "Uchu Brewing",
            "brewery_name_jp": "うちゅうブルーイング",
            "beer_name_en": "UCHU HIGH",
            "beer_name_jp": "宇宙HIGH",
            "beer_name_core": "UCHU HIGH",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/uchu-brewing-high-uchu-high-2026/7615405"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8212",
        "untappd_url": "https://untappd.com/b/whiplash-rollover/1521242",
        "gemini_update": {
            "brewery_name_en": "Whiplash",
            "brewery_name_jp": "ウィプラッシュ",
            "beer_name_en": "Rollover",
            "beer_name_jp": "ロールオーバー",
            "beer_name_core": "Rollover",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/whiplash-rollover/1521242"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8213",
        "untappd_url": "https://untappd.com/b/whiplash-body-riddle/2153460",
        "gemini_update": {
            "brewery_name_en": "Whiplash",
            "brewery_name_jp": "ウィプラッシュ",
            "beer_name_en": "Body Riddle",
            "beer_name_jp": "ボディ・リドル",
            "beer_name_core": "Body Riddle",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/whiplash-body-riddle/2153460"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8214",
        "untappd_url": "https://untappd.com/b/whiplash-blue-ghosts/3179938",
        "gemini_update": {
            "brewery_name_en": "Whiplash",
            "brewery_name_jp": "ウィプラッシュ",
            "beer_name_en": "Blue Ghosts",
            "beer_name_jp": "ブルー・ゴースト",
            "beer_name_core": "Blue Ghosts",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/whiplash-blue-ghosts/3179938"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8215",
        "untappd_url": "https://untappd.com/b/whiplash-note-to-self/5745200",
        "gemini_update": {
            "brewery_name_en": "Whiplash",
            "brewery_name_jp": "ウィプラッシュ",
            "beer_name_en": "Note to Self",
            "beer_name_jp": "ノート・トゥ・セルフ",
            "beer_name_core": "Note to Self",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/whiplash-note-to-self/5745200"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8216",
        "untappd_url": "https://untappd.com/b/whiplash-quiet-crowd/4726392",
        "gemini_update": {
            "brewery_name_en": "Whiplash",
            "brewery_name_jp": "ウィプラッシュ",
            "beer_name_en": "Quiet Crowd",
            "beer_name_jp": "クワイエット・クラウド",
            "beer_name_core": "Quiet Crowd",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/whiplash-quiet-crowd/4726392"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8217",
        "untappd_url": "https://untappd.com/b/whiplash-setting-sun/2994774",
        "gemini_update": {
            "brewery_name_en": "Whiplash",
            "brewery_name_jp": "ウィプラッシュ",
            "beer_name_en": "Setting Sun",
            "beer_name_jp": "セッティング・サン",
            "beer_name_core": "Setting Sun",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/whiplash-setting-sun/2994774"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8218",
        "untappd_url": "https://untappd.com/b/whiplash-desire-lines/5779099",
        "gemini_update": {
            "brewery_name_en": "Whiplash",
            "brewery_name_jp": "ウィプラッシュ",
            "beer_name_en": "Desire Lines",
            "beer_name_jp": "デザイア・ラインズ",
            "beer_name_core": "Desire Lines",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/whiplash-desire-lines/5779099"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8219",
        "untappd_url": "https://untappd.com/b/whiplash-lew/7070903",
        "gemini_update": {
            "brewery_name_en": "Whiplash",
            "brewery_name_jp": "ウィプラッシュ",
            "beer_name_en": "Lew",
            "beer_name_jp": "ルー",
            "beer_name_core": "Lew",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/whiplash-lew/7070903"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8220",
        "untappd_url": "https://untappd.com/b/whiplash-irel/7070740",
        "gemini_update": {
            "brewery_name_en": "Whiplash",
            "brewery_name_jp": "ウィプラッシュ",
            "beer_name_en": "IRÉL",
            "beer_name_jp": "イレル",
            "beer_name_core": "IRÉL",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/whiplash-irel/7070740"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8221",
        "untappd_url": "https://untappd.com/b/whiplash-disco-mystic/4100870",
        "gemini_update": {
            "brewery_name_en": "Whiplash",
            "brewery_name_jp": "ウィプラッシュ",
            "beer_name_en": "Disco Mystic",
            "beer_name_jp": "ディスコ・ミスティック",
            "beer_name_core": "Disco Mystic",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/whiplash-disco-mystic/4100870"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8222",
        "untappd_url": "https://untappd.com/b/whiplash-into-the-abyss/6349102",
        "gemini_update": {
            "brewery_name_en": "Whiplash",
            "brewery_name_jp": "ウィプラッシュ",
            "beer_name_en": "Into the Abyss",
            "beer_name_jp": "イントゥ・ジ・アビス",
            "beer_name_core": "Into the Abyss",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/whiplash-into-the-abyss/6349102"
        }
    },

    # --- マルホ酒店 ---
    {
        "url": "https://maruho.shop/products/bodhizafa-473ml-georgetown",
        "untappd_url": "https://untappd.com/b/georgetown-brewing-company-bodhizafa/1094728",
        "gemini_update": {
            "brewery_name_en": "Georgetown Brewing Company",
            "brewery_name_jp": "ジョージタウン",
            "beer_name_en": "Bodhizafa",
            "beer_name_jp": "ボーディザファ",
            "beer_name_core": "Bodhizafa",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/georgetown-brewing-company-bodhizafa/1094728"
        }
    },
    {
        "url": "https://maruho.shop/products/宇宙-high-350ml-うちゅうブルーイング",
        "untappd_url": "https://untappd.com/b/uchu-brewing-high-uchu-high-2026/7615405",
        "gemini_update": {
            "brewery_name_en": "Uchu Brewing",
            "brewery_name_jp": "うちゅうブルーイング",
            "beer_name_en": "UCHU HIGH",
            "beer_name_jp": "宇宙HIGH",
            "beer_name_core": "UCHU HIGH",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/uchu-brewing-high-uchu-high-2026/7615405"
        }
    },
    {
        "url": "https://maruho.shop/products/quantum-saturation-collab-w-rar-350ml-うちゅうブルーイング",
        "untappd_url": "https://untappd.com/b/uchu-brewing-quantum-saturation/7614366",
        "gemini_update": {
            "brewery_name_en": "Uchu Brewing",
            "brewery_name_jp": "うちゅうブルーイング",
            "beer_name_en": "Quantum Saturation",
            "beer_name_jp": "クアンタム サチュレーション",
            "beer_name_core": "Quantum Saturation",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/uchu-brewing-quantum-saturation/7614366"
        }
    },
    {
        "url": "https://maruho.shop/products/点灯-750ml-passific",
        "untappd_url": "https://untappd.com/b/passific-brewing-tento/7113733",
        "gemini_update": {
            "brewery_name_en": "Passific Brewing",
            "brewery_name_jp": "パシフィックブルーイング",
            "beer_name_en": "Tento",
            "beer_name_jp": "点灯",
            "beer_name_core": "Tento",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/passific-brewing-tento/7113733"
        }
    },
    {
        "url": "https://maruho.shop/products/sukittu-350ml-passific",
        "untappd_url": "https://untappd.com/b/passific-brewing-sukittu/5088795",
        "gemini_update": {
            "brewery_name_en": "Passific Brewing",
            "brewery_name_jp": "パシフィックブルーイング",
            "beer_name_en": "Sukittu",
            "beer_name_jp": "スキット",
            "beer_name_core": "Sukittu",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/passific-brewing-sukittu/5088795"
        }
    },
    {
        "url": "https://maruho.shop/products/himmel-350ml-passific",
        "untappd_url": "https://untappd.com/b/passific-brewing-himmel/6021680",
        "gemini_update": {
            "brewery_name_en": "Passific Brewing",
            "brewery_name_jp": "パシフィックブルーイング",
            "beer_name_en": "Himmel",
            "beer_name_jp": "ヒンメル",
            "beer_name_core": "Himmel",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/passific-brewing-himmel/6021680"
        }
    },
    {
        "url": "https://maruho.shop/products/youphilia-collab-w-whiplash-500ml-totopia",
        "untappd_url": "https://untappd.com/b/totopia-brewery-youphilia/7614478",
        "gemini_update": {
            "brewery_name_en": "Totopia Brewery",
            "brewery_name_jp": "トートピアブルワリー",
            "beer_name_en": "Youphilia",
            "beer_name_jp": "ユーフィリア",
            "beer_name_core": "Youphilia",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/totopia-brewery-youphilia/7614478"
        }
    },
    {
        "url": "https://maruho.shop/products/polka-350ml-passific",
        "untappd_url": "https://untappd.com/b/passific-brewing-polka/5056127",
        "gemini_update": {
            "brewery_name_en": "Passific Brewing",
            "brewery_name_jp": "パシフィックブルーイング",
            "beer_name_en": "Polka",
            "beer_name_jp": "ポルカ",
            "beer_name_core": "Polka",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/passific-brewing-polka/5056127"
        }
    },
    {
        "url": "https://maruho.shop/products/erve-654ml-nevel",
        "untappd_url": "https://untappd.com/b/nevel-erve/3724723",
        "gemini_update": {
            "brewery_name_en": "Nevel",
            "brewery_name_jp": "ネヴェル",
            "beer_name_en": "Erve",
            "beer_name_jp": "エルヴェ",
            "beer_name_core": "Erve",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/nevel-erve/3724723"
        }
    },
    {
        "url": "https://maruho.shop/products/abricot-750ml-mont-saleve",
        "untappd_url": "https://untappd.com/b/la-brasserie-du-mont-saleve-abricot/5920627",
        "gemini_update": {
            "brewery_name_en": "Mont Saleve",
            "brewery_name_jp": "モン サレーヴ",
            "beer_name_en": "Abricot",
            "beer_name_jp": "アブリコ",
            "beer_name_core": "Abricot",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/la-brasserie-du-mont-saleve-abricot/5920627"
        }
    },

    # --- ちょうせいや ---
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000002102",
        "untappd_url": "https://untappd.com/b/west-coast-brewing-modern-haze/7615474",
        "gemini_update": {
            "brewery_name_en": "West Coast Brewing",
            "brewery_name_jp": "ウエストコーストブルーイング",
            "beer_name_en": "Modern Haze",
            "beer_name_jp": "モダンヘイズ",
            "beer_name_core": "Modern Haze",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/west-coast-brewing-modern-haze/7615474"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000000479",
        "untappd_url": "https://untappd.com/b/uchu-brewing-quantum-saturation/7614366",
        "gemini_update": {
            "brewery_name_en": "Uchu Brewing",
            "brewery_name_jp": "うちゅうブルーイング",
            "beer_name_en": "Quantum Saturation",
            "beer_name_jp": "クアンタム サチュレーション",
            "beer_name_core": "Quantum Saturation",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/uchu-brewing-quantum-saturation/7614366"
        }
    },

    # --- BEER VOLTA ---
    {
        "url": "https://beervolta.com/?pid=194134191",
        "untappd_url": "https://untappd.com/b/georgetown-brewing-company-bodhizafa/1094728",
        "gemini_update": {
            "brewery_name_en": "Georgetown Brewing Company",
            "brewery_name_jp": "ジョージタウン",
            "beer_name_en": "Bodhizafa",
            "beer_name_jp": "ボーディザファ",
            "beer_name_core": "Bodhizafa",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/georgetown-brewing-company-bodhizafa/1094728"
        }
    },

    # --- 未紐付けから昇格したアイテム ---
    {
        "url": "https://maruho.shop/products/wind-from-farm-350ml-paint-palette",
        "untappd_url": "https://untappd.com/b/paint-palette-brewing-wind-from-farm/6545922",
        "gemini_update": {
            "brewery_name_en": "Paint Palette Brewing",
            "brewery_name_jp": "ペイントパレット",
            "beer_name_en": "Wind From Farm",
            "beer_name_jp": "ウィンド フロム ファーム",
            "beer_name_core": "Wind From Farm",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/paint-palette-brewing-wind-from-farm/6545922"
        }
    },
    {
        "url": "https://witchcraftmarket.com/products/the-unsinkable-tartanic",
        "untappd_url": "https://untappd.com/b/barebottle-brewing-company-the-unsinkable-tartanic/2862669",
        "gemini_update": {
            "brewery_name_en": "Barebottle Brewing Company",
            "brewery_name_jp": "ベアボトル",
            "beer_name_en": "The Unsinkable Tartanic",
            "beer_name_jp": "ザ アンシンカブル タータニック",
            "beer_name_core": "The Unsinkable Tartanic",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/barebottle-brewing-company-the-unsinkable-tartanic/2862669"
        }
    },
    {
        "url": "https://beervolta.com/?pid=194050123",
        "untappd_url": "https://untappd.com/b/totopia-brewery-floraphilia/7614476",
        "gemini_update": {
            "brewery_name_en": "Totopia Brewery",
            "brewery_name_jp": "トートピアブルワリー",
            "beer_name_en": "Floraphilia",
            "beer_name_jp": "フローラフィリア",
            "beer_name_core": "Floraphilia",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/totopia-brewery-floraphilia/7614476"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8199",
        "untappd_url": "https://untappd.com/b/trademark-brewing-queen-of-hops/4809701",
        "gemini_update": {
            "brewery_name_en": "Trademark Brewing",
            "brewery_name_jp": "トレードマーク",
            "beer_name_en": "Queen of Hops",
            "beer_name_jp": "クイーン・オブ・ホップス",
            "beer_name_core": "Queen of Hops",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/trademark-brewing-queen-of-hops/4809701"
        }
    },
    {
        "url": "https://maruho.shop/products/into-the-abyss-2026-10-空輸便-440ml-whiplash",
        "untappd_url": "https://untappd.com/b/whiplash-into-the-abyss/6349102",
        "gemini_update": {
            "brewery_name_en": "Whiplash",
            "brewery_name_jp": "ウィプラッシュ",
            "beer_name_en": "Into the Abyss",
            "beer_name_jp": "イントゥ・ジ・アビス",
            "beer_name_core": "Into the Abyss",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/whiplash-into-the-abyss/6349102"
        }
    }
]

# 2. ローリング巡回・情報更新対象 Untappd URL (4件)
BEER_REFRESH_URLS = [
    "https://untappd.com/b/namachan-brewing-yamitsuki-ale-mapo-10th-batch/6808022",
    "https://untappd.com/b/atsumi-peninsula-brewing-co-waimamaku/6594980",
    "https://untappd.com/b/atsumi-peninsula-brewing-co-weka/6381498",
    "https://untappd.com/b/atsumi-peninsula-brewing-co-hakapoua/6553246",
]

# 3. 調査済みUntappd未登録ビール (監査タイムスタンプ更新対象: 3件)
AUDITED_UNREGISTERED_BEERS = [
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8208",
        "name": "バテレ / コティヌス (Irish Red Ale) 500ml缶 [VERTERE / Cotinus #1]",
        "notes": "VERTERE の新作 Irish Red Ale。Untappd未登録を確認。"
    },
    {
        "url": "https://151l.shop/?pid=193631430",
        "name": "【9/24（木）入荷予定】ファーメンタリー　お茶！大和（FARMENTRY OCHA! YAMATO）",
        "notes": "FARMENTRY 大和茶使用ウィートエール。Untappd未登録を確認。"
    },
    {
        "url": "https://151l.shop/?pid=192919839",
        "name": "伊勢角屋麦酒　カドラボ039（ISEKADOYA BEER KADOLABO 039）",
        "notes": "伊勢角屋麦酒 KADOLABO 039。Untappd未登録を確認。"
    }
]

# 4. 非ビール（RTD / 焼酎ソーダ等）の是正対象
NON_BEER_ITEMS = [
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000001796",
        "name": "【HOP GLOW SODA/伊勢角屋麦酒】",
        "product_type": "other"
    },
    {
        "url": "https://maruho.shop/products/hop-glow-soda-collab-w-若潮酒造-350ml-伊勢角麦酒",
        "name": "Hop Glow Soda (collab w/若潮酒造） 350ml/伊勢角麦酒",
        "product_type": "other"
    }
]

async def main():
    sb = get_supabase_client()
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. 新規エンリッチ
    logger.info(f"\n[1] Enriching {len(NEW_ENRICH_ITEMS)} target beers...")
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

        # untappd_data scrape & upsert
        existing_u = sb.table("untappd_data").select("untappd_url").eq("untappd_url", untappd_url).execute()
        if existing_u.data:
            logger.info(f"  ⚡ Already in untappd_data, updating details: {untappd_url}")
        
        details = await scrape_beer_details(untappd_url)
        if details:
            payload = map_details_to_payload(details)
            payload["untappd_url"] = untappd_url
            payload["fetched_at"] = now_iso
            sb.table("untappd_data").upsert(payload, on_conflict="untappd_url").execute()
            logger.info(f"  ✅ Enriched & Saved: [{details.get('untappd_brewery_name')}] {details.get('untappd_beer_name')} (Rating: {details.get('untappd_rating')})")
        else:
            logger.warning(f"  ⚠️ Could not scrape Untappd details for {untappd_url}")
        await asyncio.sleep(0.5)

    # 2. ローリング巡回・Untappd データの最新化
    logger.info(f"\n[2] Scraping & updating Untappd details for {len(BEER_REFRESH_URLS)} rolling audit beers...")
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
        await asyncio.sleep(0.5)

    # 3. Untappd未登録アイテムの監査日時更新
    logger.info(f"\n[3] Updating audit timestamps for {len(AUDITED_UNREGISTERED_BEERS)} verified unregistered beers...")
    for item in AUDITED_UNREGISTERED_BEERS:
        p_url = item["url"]
        sb.table("scraped_beers").update({
            "untappd_enriched_at": now_iso
        }).eq("url", p_url).execute()

        sb.table("gemini_data").update({
            "product_type": "beer",
            "updated_at": now_iso
        }).eq("url", p_url).execute()

        logger.info(f"  ✅ Audited: {item['name']}\n    -> {item['notes']}")

    # 4. 非ビールアイテムの product_type 是正
    logger.info(f"\n[4] Correcting product_type for {len(NON_BEER_ITEMS)} non-beer items...")
    for item in NON_BEER_ITEMS:
        p_url = item["url"]
        sb.table("gemini_data").update({
            "product_type": item["product_type"],
            "updated_at": now_iso
        }).eq("url", p_url).execute()
        sb.table("scraped_beers").update({
            "untappd_enriched_at": now_iso
        }).eq("url", p_url).execute()
        logger.info(f"  ✅ Corrected product_type: {item['product_type']} for {item['name']}")

    # 5. マテリアライズドビューのリフレッシュ
    logger.info("\n[5] Refreshing Materialized View (beer_info_view)...")
    refresh_materialized_view(sb, logger)
    logger.info("✅ Materialized view refreshed successfully!")

if __name__ == "__main__":
    asyncio.run(main())
