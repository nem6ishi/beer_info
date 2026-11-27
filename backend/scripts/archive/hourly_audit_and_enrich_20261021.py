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
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8186",
        "untappd_url": "https://untappd.com/b/yokohama-bay-brewing-co-yuzu-weiss/5579014",
        "gemini_update": {
            "brewery_name_en": "Yokohama Bay Brewing",
            "brewery_name_jp": "横浜ベイブルーイング",
            "beer_name_en": "Yuzu Weiss",
            "beer_name_jp": "ゆずヴァイス",
            "beer_name_core": "Yuzu Weiss",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/yokohama-bay-brewing-co-yuzu-weiss/5579014"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8185",
        "untappd_url": "https://untappd.com/b/bay-brewing-yokohama-bay-weisse/206605",
        "gemini_update": {
            "brewery_name_en": "Yokohama Bay Brewing",
            "brewery_name_jp": "横浜ベイブルーイング",
            "beer_name_en": "Bay Weiss",
            "beer_name_jp": "ベイヴァイス",
            "beer_name_core": "Bay Weiss",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/bay-brewing-yokohama-bay-weisse/206605"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8184",
        "untappd_url": "https://untappd.com/b/bay-brewing-yokohama-bay-dark/460332",
        "gemini_update": {
            "brewery_name_en": "Yokohama Bay Brewing",
            "brewery_name_jp": "横浜ベイブルーイング",
            "beer_name_en": "Bay Dark",
            "beer_name_jp": "ベイダーク",
            "beer_name_core": "Bay Dark",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/bay-brewing-yokohama-bay-dark/460332"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8183",
        "untappd_url": "https://untappd.com/b/bay-brewing-yokohama-bay-pilsner/460329",
        "gemini_update": {
            "brewery_name_en": "Yokohama Bay Brewing",
            "brewery_name_jp": "横浜ベイブルーイング",
            "beer_name_en": "Bay Pilsner",
            "beer_name_jp": "ベイピルスナー",
            "beer_name_core": "Bay Pilsner",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/bay-brewing-yokohama-bay-pilsner/460329"
        }
    },
    {
        "url": "https://151l.shop/?pid=194065731",
        "untappd_url": "https://untappd.com/b/uchu-brewing-quantum-saturation/7614366",
        "gemini_update": {
            "brewery_name_en": "UCHU Brewing",
            "brewery_name_jp": "うちゅうブルーイング",
            "beer_name_en": "Quantum Saturation",
            "beer_name_jp": "クアンタムサチュレーション",
            "beer_name_core": "Quantum Saturation",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/uchu-brewing-quantum-saturation/7614366"
        }
    },
    {
        "url": "https://151l.shop/?pid=194060674",
        "untappd_url": "https://untappd.com/b/trademark-brewing-queen-of-hops/4809701",
        "gemini_update": {
            "brewery_name_en": "Trademark Brewing",
            "brewery_name_jp": "トレードマーク",
            "beer_name_en": "Queen of Hops",
            "beer_name_jp": "クィーンオブホップス",
            "beer_name_core": "Queen of Hops",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/trademark-brewing-queen-of-hops/4809701"
        }
    },
    {
        "url": "https://151l.shop/?pid=194060683",
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
        "url": "https://beervolta.com/?pid=193963935",
        "untappd_url": "https://untappd.com/b/tamamura-honten-co-shiga-kogen-fresh-hop-blonde-2026/6846081",
        "gemini_update": {
            "brewery_name_en": "Tamamura Honten Co.",
            "brewery_name_jp": "志賀高原ビール",
            "beer_name_en": "Shiga Kogen Fresh Hop Blonde (2026)",
            "beer_name_jp": "フレッシュホップブロンド",
            "beer_name_core": "Fresh Hop Blonde",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/tamamura-honten-co-shiga-kogen-fresh-hop-blonde-2026/6846081"
        }
    },
    {
        "url": "https://witchcraftmarket.com/products/nodogoshi",
        "untappd_url": "https://untappd.com/b/saltfields-brewing-nodogoshi-rice-lager/6234259",
        "gemini_update": {
            "brewery_name_en": "Saltfields Brewing",
            "brewery_name_jp": "ソルトフィールズブルーイング",
            "beer_name_en": "NODOGOSHI Rice Lager",
            "beer_name_jp": "ノドゴシ",
            "beer_name_core": "NODOGOSHI",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/saltfields-brewing-nodogoshi-rice-lager/6234259"
        }
    },
    {
        "url": "https://witchcraftmarket.com/products/ransnack-the-universe",
        "untappd_url": "https://untappd.com/b/collective-arts-brewing-ransack-the-universe/982103",
        "gemini_update": {
            "brewery_name_en": "Collective Arts Brewing",
            "brewery_name_jp": "コレクティブアーツ",
            "beer_name_en": "Ransack the Universe",
            "beer_name_jp": "ランサック ザ ユニバース",
            "beer_name_core": "Ransack the Universe",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/collective-arts-brewing-ransack-the-universe/982103"
        }
    },
    {
        "url": "https://witchcraftmarket.com/products/good-monster-3",
        "untappd_url": "https://untappd.com/b/collective-arts-brewing-good-monster/4175080",
        "gemini_update": {
            "brewery_name_en": "Collective Arts Brewing",
            "brewery_name_jp": "コレクティブアーツ",
            "beer_name_en": "Good Monster",
            "beer_name_jp": "グッドモンスター",
            "beer_name_core": "Good Monster",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/collective-arts-brewing-good-monster/4175080"
        }
    },
    {
        "url": "https://witchcraftmarket.com/products/between-the-palms",
        "untappd_url": "https://untappd.com/b/collective-arts-brewing-between-the-palms/6623357",
        "gemini_update": {
            "brewery_name_en": "Collective Arts Brewing",
            "brewery_name_jp": "コレクティブアーツ",
            "beer_name_en": "Between the Palms",
            "beer_name_jp": "ビトゥイーン ザ パームス",
            "beer_name_core": "Between the Palms",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/collective-arts-brewing-between-the-palms/6623357"
        }
    },
    {
        "url": "https://witchcraftmarket.com/products/life-in-the-clouds-2",
        "untappd_url": "https://untappd.com/b/collective-arts-brewing-life-in-the-clouds/2429930",
        "gemini_update": {
            "brewery_name_en": "Collective Arts Brewing",
            "brewery_name_jp": "コレクティブアーツ",
            "beer_name_en": "Life in the Clouds",
            "beer_name_jp": "ライフ イン ザ クラウズ",
            "beer_name_core": "Life in the Clouds",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/collective-arts-brewing-life-in-the-clouds/2429930"
        }
    },
    {
        "url": "https://witchcraftmarket.com/products/scenic-pass",
        "untappd_url": "https://untappd.com/b/collective-arts-brewing-scenic-pass/6789592",
        "gemini_update": {
            "brewery_name_en": "Collective Arts Brewing",
            "brewery_name_jp": "コレクティブアーツ",
            "beer_name_en": "Scenic Pass",
            "beer_name_jp": "シーニックパス",
            "beer_name_core": "Scenic Pass",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/collective-arts-brewing-scenic-pass/6789592"
        }
    },
    {
        "url": "https://beervolta.com/?pid=194065770",
        "untappd_url": "https://untappd.com/b/uchu-brewing-quantum-saturation/7614366",
        "gemini_update": {
            "brewery_name_en": "UCHU Brewing",
            "brewery_name_jp": "うちゅうブルーイング",
            "beer_name_en": "Quantum Saturation",
            "beer_name_jp": "クォンタム サチュレーション",
            "beer_name_core": "Quantum Saturation",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/uchu-brewing-quantum-saturation/7614366"
        }
    },
    {
        "url": "https://maruho.shop/products/goat-ram-collabo-w-pastore-375ml-holy-goat",
        "untappd_url": "https://untappd.com/b/holy-goat-brewing-goat-and-ram/5371755",
        "gemini_update": {
            "brewery_name_en": "Holy Goat Brewing",
            "brewery_name_jp": "ホーリーゴート",
            "beer_name_en": "Goat and Ram",
            "beer_name_jp": "ゴート＆ラム",
            "beer_name_core": "Goat and Ram",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/holy-goat-brewing-goat-and-ram/5371755"
        }
    },
    {
        "url": "https://maruho.shop/products/spectral-lore-375ml-holy-goat",
        "untappd_url": "https://untappd.com/b/holy-goat-brewing-spectral-lore/5000975",
        "gemini_update": {
            "brewery_name_en": "Holy Goat Brewing",
            "brewery_name_jp": "ホーリーゴート",
            "beer_name_en": "Spectral Lore",
            "beer_name_jp": "スペクトラル ロア",
            "beer_name_core": "Spectral Lore",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/holy-goat-brewing-spectral-lore/5000975"
        }
    },
    {
        "url": "https://maruho.shop/products/funky-blender-preserves-apricot-nectarine-750ml-casey",
        "untappd_url": "https://untappd.com/b/casey-brewing-and-blending-funky-blender-preserves-apricot-nectarine/3455799",
        "gemini_update": {
            "brewery_name_en": "Casey Brewing & Blending",
            "brewery_name_jp": "ケイシーブルーイング",
            "beer_name_en": "Funky Blender Preserves: Apricot + Nectarine",
            "beer_name_jp": "ファンキーブレンダー プリザーブス アプリコット ネクタリン",
            "beer_name_core": "Funky Blender Preserves Apricot Nectarine",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/casey-brewing-and-blending-funky-blender-preserves-apricot-nectarine/3455799"
        }
    }
]

# 2. 非ビール商品（リキュール・RTD等：product_type='other'へ修正）
NON_BEER_ITEMS = [
    {
        "url": "https://maruho.shop/products/jumpiest-hop-720ml-西山酒造場",
        "name": "Jumpiest Hop (Ready To Mix) 720ml / マルホ酒店×西山酒造場",
        "notes": "ビール由来スピリッツベースのフルーツリキュール。product_type -> other"
    }
]

# 3. 誤紐付け是正対象アイテム
MISMATCH_FIX_ITEMS = [
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000001893",
        "name": "【桃ヴァイツェン(川中島)/箕面ビール】購入制限１本 (ちょうせいや)",
        "old_untappd_url": "https://untappd.com/b/minoh-beer-minoh-kokusan-momo-weizen-wase/6800024",
        "correct_untappd_url": "https://untappd.com/b/minoh-beer-kokusan-momo-weizen-kawanakajima-hakutou-2026/7207211",
        "gemini_update": {
            "brewery_name_en": "Minoh Beer",
            "brewery_name_jp": "箕面ビール",
            "beer_name_en": "Kokusan Momo Weizen - Kawanakajima (2026)",
            "beer_name_jp": "桃ヴァイツェン(川中島)",
            "beer_name_core": "Kokusan Momo Weizen Kawanakajima",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/minoh-beer-kokusan-momo-weizen-kawanakajima-hakutou-2026/7207211"
        }
    }
]

# 4. ローリング巡回・Untappdデータ最新化対象（ユニークURL）
BEER_REFRESH_URLS = [
    "https://untappd.com/b/pomona-island-brew-co-tamaki-iv/6321139",
    "https://untappd.com/b/cloudwater-brew-co-race-your-own-heart/5010156",
    "https://untappd.com/b/unsung-brewing-co-metaplex/2076879",
    "https://untappd.com/b/minoh-beer-kokusan-momo-weizen-kawanakajima-hakutou-2026/7207211"
]

# 5. Untappd未登録確認済みアイテム（監査日時を更新して次回即時再検索を回避）
AUDITED_UNREGISTERED_BEERS = [
    {
        "url": "https://witchcraftmarket.com/products/heat-wave-ipa",
        "name": "[GAME BREW] 魔炎長 アウナス HEAT WAVE IPA / ヒートウェイブ IPA (WITCH CRAFT MARKET)",
        "notes": "GAME BREW（佐賀）とロマンシング佐賀コラボ四魔貴族シリーズ新作。Untappd未登録を確認"
    },
    {
        "url": "https://151l.shop/?pid=193571646",
        "name": "伊勢角屋麦酒 カドラボ041（ISEKADOYA BEER KADOLABO 041） (一期一会～る)",
        "notes": "伊勢角屋麦酒の実験醸造カドラボシリーズ新作（Marginal Ⅵ）。Untappd未登録を確認"
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8167",
        "name": "ビーイージーブルーイング / どさ？ゆっこさ！ (West Coast IPA) 350ml缶 (アローム)",
        "notes": "Be Easy Brewingの津軽弁シリーズ。Untappdブルワリー銘柄一覧で未登録を確認"
    },
    {
        "url": "https://beervolta.com/?pid=193866863",
        "name": "セッションズ : はっさくスマッシュ | Session's: Hassaku Smash (BEER VOLTA)",
        "notes": "Session's Brewery（広島）の柑橘SMaSHビール。Untappdブルワリー銘柄一覧で未登録を確認"
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8168",
        "name": "ビーイージーブルーイング / リリコイ (American IPA) 350ml缶 (アローム)",
        "notes": "Be Easy Brewingの新作IPA。Untappdブルワリー銘柄一覧で未登録を確認"
    }
]

async def main():
    sb = get_supabase_client()
    now_iso = datetime.now(timezone.utc).isoformat()

    logger.info("=" * 70)
    logger.info("🚀 Starting Hourly Beer Audit & Enrichment Pipeline (2026-10-21)")
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

            # untappd_data scrape & upsert
            details = await scrape_beer_details(untappd_url)
            if details:
                payload = map_details_to_payload(details)
                payload["untappd_url"] = untappd_url
                payload["fetched_at"] = now_iso
                sb.table("untappd_data").upsert(payload, on_conflict="untappd_url").execute()
                logger.info(f"  ✅ Enriched & Saved: [{details.get('untappd_brewery_name')}] {details.get('untappd_beer_name')} (Rating: {details.get('untappd_rating')})")
            else:
                logger.warning(f"  ⚠️ Could not scrape Untappd details for {untappd_url}")
            await asyncio.sleep(2.0)
    else:
        logger.info("\n[1] No unenriched beers to process.")

    # 2. 非ビール商品のステータス修正 (product_type='other')
    if NON_BEER_ITEMS:
        logger.info(f"\n[2] Setting {len(NON_BEER_ITEMS)} non-beer items to product_type='other'...")
        for item in NON_BEER_ITEMS:
            p_url = item["url"]
            sb.table("gemini_data").update({
                "product_type": "other",
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
            await asyncio.sleep(2.0)

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
        await asyncio.sleep(2.0)

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
