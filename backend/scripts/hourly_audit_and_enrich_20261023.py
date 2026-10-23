import asyncio
import logging
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client, refresh_materialized_view
from backend.src.services.untappd.http_client import scrape_beer_details
from backend.src.commands.enrich_untappd import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 1. 未エンリッチ商品（特定済みUntappd URL）: 20件 + 未紐付けから特定した2件 = 計22件
# 1. エンリッチ商品: 全26件
NEW_ENRICH_ITEMS = [
    # --- WITCH CRAFT MARKET (Varietal Beer Co.) ---
    {
        "url": "https://witchcraftmarket.com/products/casita-lager",
        "untappd_url": "https://untappd.com/b/varietal-beer-company-casita-lager/2623197",
        "gemini_update": {
            "brewery_name_en": "Varietal Beer Company",
            "brewery_name_jp": "ヴァラエタル",
            "beer_name_en": "Casita Lager",
            "beer_name_jp": "カシータ ラガー",
            "beer_name_core": "Casita Lager",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/varietal-beer-company-casita-lager/2623197"
        }
    },
    {
        "url": "https://witchcraftmarket.com/products/twine-climber",
        "untappd_url": "https://untappd.com/b/varietal-beer-co-twine-climber/2593312",
        "gemini_update": {
            "brewery_name_en": "Varietal Beer Company",
            "brewery_name_jp": "ヴァラエタル",
            "beer_name_en": "Twine Climber",
            "beer_name_jp": "トゥワインクライマー",
            "beer_name_core": "Twine Climber",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/varietal-beer-co-twine-climber/2593312"
        }
    },

    # --- アローム (West Coast Brewing, UCHU x RaR) ---
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8207",
        "untappd_url": "https://untappd.com/b/west-coast-brewing-modern-haze/7615474",
        "gemini_update": {
            "brewery_name_en": "West Coast Brewing",
            "brewery_name_jp": "ウエストコーストブルーイング",
            "beer_name_en": "Modern Haze",
            "beer_name_jp": "モダン・ヘイズ",
            "beer_name_core": "Modern Haze",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/west-coast-brewing-modern-haze/7615474"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=722",
        "untappd_url": "https://untappd.com/b/west-coast-brewing-starwatcher-cbd/4194889",
        "gemini_update": {
            "brewery_name_en": "West Coast Brewing",
            "brewery_name_jp": "ウエストコーストブルーイング",
            "beer_name_en": "Starwatcher CBD",
            "beer_name_jp": "スターウォッチャーCBD",
            "beer_name_core": "Starwatcher CBD",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/west-coast-brewing-starwatcher-cbd/4194889"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8206",
        "untappd_url": "https://untappd.com/b/uchu-brewing-quantum-saturation/7614366",
        "gemini_update": {
            "brewery_name_en": "Uchu Brewing",
            "brewery_name_jp": "うちゅうブルーイング",
            "beer_name_en": "Quantum Saturation",
            "beer_name_jp": "クォンタム・サチュレーション",
            "beer_name_core": "Quantum Saturation",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/uchu-brewing-quantum-saturation/7614366"
        }
    },

    # --- BEER VOLTA (West Coast Brewing) ---
    {
        "url": "https://beervolta.com/?pid=194070058",
        "untappd_url": "https://untappd.com/b/west-coast-brewing-starwatcher-cbd/4194889",
        "gemini_update": {
            "brewery_name_en": "West Coast Brewing",
            "brewery_name_jp": "ウエストコーストブルーイング",
            "beer_name_en": "Starwatcher CBD",
            "beer_name_jp": "スターウォッチャー CBD",
            "beer_name_core": "Starwatcher CBD",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/west-coast-brewing-starwatcher-cbd/4194889"
        }
    },
    {
        "url": "https://beervolta.com/?pid=194070056",
        "untappd_url": "https://untappd.com/b/west-coast-brewing-modern-haze/7615474",
        "gemini_update": {
            "brewery_name_en": "West Coast Brewing",
            "brewery_name_jp": "ウエストコーストブルーイング",
            "beer_name_en": "Modern Haze",
            "beer_name_jp": "モダン ヘイズ",
            "beer_name_core": "Modern Haze",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/west-coast-brewing-modern-haze/7615474"
        }
    },

    # --- WITCH CRAFT MARKET (Trap Door Brewing) ---
    {
        "url": "https://witchcraftmarket.com/products/trap-door-ipa",
        "untappd_url": "https://untappd.com/b/trap-door-brewing-trap-door-ipa/1329630",
        "gemini_update": {
            "brewery_name_en": "Trap Door Brewing",
            "brewery_name_jp": "トラップドア",
            "beer_name_en": "Trap Door IPA",
            "beer_name_jp": "トラップドア IPA",
            "beer_name_core": "Trap Door IPA",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/trap-door-brewing-trap-door-ipa/1329630"
        }
    },
    {
        "url": "https://witchcraftmarket.com/products/glowed-up",
        "untappd_url": "https://untappd.com/b/trap-door-brewing-glowed-up/1889866",
        "gemini_update": {
            "brewery_name_en": "Trap Door Brewing",
            "brewery_name_jp": "トラップドア",
            "beer_name_en": "Glowed Up",
            "beer_name_jp": "グロード アップ",
            "beer_name_core": "Glowed Up",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/trap-door-brewing-glowed-up/1889866"
        }
    },
    {
        "url": "https://witchcraftmarket.com/products/day-beer",
        "untappd_url": "https://untappd.com/b/trap-door-brewing-day-beer-west-coast-pale/4845883",
        "gemini_update": {
            "brewery_name_en": "Trap Door Brewing",
            "brewery_name_jp": "トラップドア",
            "beer_name_en": "Day Beer West Coast Pale",
            "beer_name_jp": "デイ ビア",
            "beer_name_core": "Day Beer",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/trap-door-brewing-day-beer-west-coast-pale/4845883"
        }
    },

    # --- マルホ酒店 (Whiplash, Garage Beer Co.) ---
    {
        "url": "https://maruho.shop/products/rollover-2026-10-空輸便-330ml-whiplash",
        "untappd_url": "https://untappd.com/b/whiplash-rollover/1521242",
        "gemini_update": {
            "brewery_name_en": "Whiplash",
            "brewery_name_jp": "ウィップラッシュ",
            "beer_name_en": "Rollover",
            "beer_name_jp": "ロールオーバー",
            "beer_name_core": "Rollover",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/whiplash-rollover/1521242"
        }
    },
    {
        "url": "https://maruho.shop/products/body-riddle-2026-10-空輸便-330ml-whiplash",
        "untappd_url": "https://untappd.com/b/whiplash-body-riddle/2153460",
        "gemini_update": {
            "brewery_name_en": "Whiplash",
            "brewery_name_jp": "ウィップラッシュ",
            "beer_name_en": "Body Riddle",
            "beer_name_jp": "ボディ リドル",
            "beer_name_core": "Body Riddle",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/whiplash-body-riddle/2153460"
        }
    },
    {
        "url": "https://maruho.shop/products/setting-sun-2026-10-空輸便-440ml-whiplash",
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
        "url": "https://maruho.shop/products/desire-lines-2026-10-空輸便-440ml-whiplash",
        "untappd_url": "https://untappd.com/b/whiplash-desire-lines/5779099",
        "gemini_update": {
            "brewery_name_en": "Whiplash",
            "brewery_name_jp": "ウィップラッシュ",
            "beer_name_en": "Desire Lines",
            "beer_name_jp": "デザイア ラインズ",
            "beer_name_core": "Desire Lines",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/whiplash-desire-lines/5779099"
        }
    },
    {
        "url": "https://maruho.shop/products/lew-2026-10-空輸便-440ml-whiplash",
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
        "url": "https://maruho.shop/products/irel-2026-10-空輸便-440ml-whiplash",
        "untappd_url": "https://untappd.com/b/whiplash-irel/7070740",
        "gemini_update": {
            "brewery_name_en": "Whiplash",
            "brewery_name_jp": "ウィップラッシュ",
            "beer_name_en": "Irel",
            "beer_name_jp": "アイレル",
            "beer_name_core": "Irel",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/whiplash-irel/7070740"
        }
    },
    {
        "url": "https://maruho.shop/products/disco-mystic-2026-10-空輸便-440ml-whiplash",
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
        "url": "https://maruho.shop/products/note-to-self-2026-10-空輸便-330ml-whiplash",
        "untappd_url": "https://untappd.com/b/whiplash-note-to-self/5745200",
        "gemini_update": {
            "brewery_name_en": "Whiplash",
            "brewery_name_jp": "ウィップラッシュ",
            "beer_name_en": "Note To Self",
            "beer_name_jp": "ノート トゥ セルフ",
            "beer_name_core": "Note To Self",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/whiplash-note-to-self/5745200"
        }
    },
    {
        "url": "https://maruho.shop/products/quiet-crowd-2026-10-空輸便-330ml-whiplash",
        "untappd_url": "https://untappd.com/b/whiplash-quiet-crowd/4726392",
        "gemini_update": {
            "brewery_name_en": "Whiplash",
            "brewery_name_jp": "ウィップラッシュ",
            "beer_name_en": "Quiet Crowd",
            "beer_name_jp": "クワイエット クラウド",
            "beer_name_core": "Quiet Crowd",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/whiplash-quiet-crowd/4726392"
        }
    },
    {
        "url": "https://maruho.shop/products/knudsen-2026-07-440ml-garage",
        "untappd_url": "https://untappd.com/b/garage-beer-co-knudsen/6630293",
        "gemini_update": {
            "brewery_name_en": "Garage Beer Co.",
            "brewery_name_jp": "ガラージュ",
            "beer_name_en": "Knudsen",
            "beer_name_jp": "クヌードセン",
            "beer_name_core": "Knudsen",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/garage-beer-co-knudsen/6630293"
        }
    },

    # --- マルホ酒店 (追加特定分) ---
    {
        "url": "https://maruho.shop/products/demons-run-w-honey-coconut-vanila-375ml-urban-roots",
        "untappd_url": "https://untappd.com/b/urban-roots-brewing-and-smokehouse-demons-run-coconut-vanilla-2024/6037722",
        "gemini_update": {
            "brewery_name_en": "Urban Roots Brewing & Smokehouse",
            "brewery_name_jp": "アーバンルーツ",
            "beer_name_en": "Demons Run Coconut Vanilla (2024)",
            "beer_name_jp": "デーモンズ ラン ココナッツ バニラ",
            "beer_name_core": "Demons Run Coconut Vanilla",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/urban-roots-brewing-and-smokehouse-demons-run-coconut-vanilla-2024/6037722"
        }
    },
    {
        "url": "https://maruho.shop/products/cheddar-on-my-mind-2-a-cellarman-collaboration-750ml-olivers",
        "untappd_url": "https://untappd.com/b/oliver-s-cider-and-perry-cheddar-on-my-mind-2/5567244",
        "gemini_update": {
            "brewery_name_en": "Oliver's Cider & Perry",
            "brewery_name_jp": "オリバーズ",
            "beer_name_en": "Cheddar On My Mind #2",
            "beer_name_jp": "チェダー オン マイ マインド #2",
            "beer_name_core": "Cheddar On My Mind",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/oliver-s-cider-and-perry-cheddar-on-my-mind-2/5567244"
        }
    },
    {
        "url": "https://maruho.shop/products/family-preserve-750ml-casey",
        "untappd_url": "https://untappd.com/b/casey-brewing-blending-casey-family-preserves-nectarine/1262564",
        "gemini_update": {
            "brewery_name_en": "Casey Brewing & Blending",
            "brewery_name_jp": "ケイシー",
            "beer_name_en": "Casey Family Preserves - Nectarine",
            "beer_name_jp": "ファミリー プリザーブ ネクタリン",
            "beer_name_core": "Casey Family Preserves Nectarine",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/casey-brewing-blending-casey-family-preserves-nectarine/1262564"
        }
    },
    {
        "url": "https://maruho.shop/products/virginiablackberry500ml-hardywood",
        "untappd_url": "https://untappd.com/b/hardywood-park-craft-brewery-virginia-blackberry/217990",
        "gemini_update": {
            "brewery_name_en": "Hardywood Park Craft Brewery",
            "brewery_name_jp": "ハーディウッド",
            "beer_name_en": "Virginia Blackberry",
            "beer_name_jp": "バージニア ブラックベリー",
            "beer_name_core": "Virginia Blackberry",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/hardywood-park-craft-brewery-virginia-blackberry/217990"
        }
    }

    # --- 未紐付け在庫から特定した救済アイテム ---
    {
        "url": "https://witchcraftmarket.com/products/pinapple-yuzu-sour",
        "untappd_url": "https://untappd.com/b/collective-arts-brewing-pineapple-and-yuzu-sour/6754570",
        "gemini_update": {
            "brewery_name_en": "Collective Arts Brewing",
            "brewery_name_jp": "コレクティブアーツ",
            "beer_name_en": "Pineapple & Yuzu Sour",
            "beer_name_jp": "パイナップル ユズ サワー",
            "beer_name_core": "Pineapple & Yuzu Sour",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/collective-arts-brewing-pineapple-and-yuzu-sour/6754570"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8168",
        "untappd_url": "https://untappd.com/b/be-easy-brewing-lilikoi/7616706",
        "gemini_update": {
            "brewery_name_en": "Be Easy Brewing",
            "brewery_name_jp": "ビーイージーブルーイング",
            "beer_name_en": "Lilikoi",
            "beer_name_jp": "リリコイ",
            "beer_name_core": "Lilikoi",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/be-easy-brewing-lilikoi/7616706"
        }
    }
]

# 2. ローリング巡回対象 (Untappd 最新情報取得)
BEER_REFRESH_URLS = [
    "https://untappd.com/b/grandline-brewing-supermerge/6006778",
    "https://untappd.com/b/grandline-brewing-passion-voyage/6793366",
    "https://untappd.com/b/grandline-brewing-hello-world/5294533",
    "https://untappd.com/b/brouwerij-strubbe-keyte-oostendse-dobbel-tripel/90245",
    "https://untappd.com/b/oud-beersel-oude-geuze-vandervelden-142/5800809",
]

# 3. 調査済みUntappd未登録ビール (監査タイムスタンプ更新対象)
AUDITED_UNREGISTERED_BEERS = [
    {
        "url": "https://beervolta.com/?pid=193865151",
        "name": "バッテン : ゴールデン ピグ | Vatten: Golden Pig",
        "notes": "Vatten 3周年限定 Session IPA。Untappd未登録を確認。"
    },
    {
        "url": "https://151l.shop/?pid=192919839",
        "name": "伊勢角屋麦酒　カドラボ039（ISEKADOYA BEER KADOLABO 039）",
        "notes": "カドラボ39弾『French 5³ meets beer』。Untappd未登録を確認。"
    },
    {
        "url": "https://151l.shop/?pid=193631430",
        "name": "【9/24（木）入荷予定】ファーメンタリー　お茶！大和（FARMENTRY OCHA! YAMATO）",
        "notes": "FARMENTRY 大和茶使用ウィートエール。Untappd未登録を確認。"
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
            await asyncio.sleep(1.0)

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
        await asyncio.sleep(1.0)

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

    # 4. マテリアライズドビューのリフレッシュ
    logger.info("\n[4] Refreshing Materialized View (beer_info_view)...")
    refresh_materialized_view(sb, logger)
    logger.info("✅ Materialized view refreshed successfully!")

if __name__ == "__main__":
    asyncio.run(main())
