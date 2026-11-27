import asyncio
import logging
import time
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client, refresh_materialized_view, sync_execute
from backend.src.services.untappd.http_client import scrape_beer_details, close_async_client
from backend.src.core.utils import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 1. 誤紐付け・メタデータ是正アイテム
FIX_MISASSIGNED_ITEMS = [
    {
        # BEER VOLTA の「伊勢角屋 x 嘉之助 : シャドウプレイ2026」が非バレルエイジ通常版(4698156)に誤紐付けされていたため解除
        "url": "https://beervolta.com/?pid=194522357",
        "name": "伊勢角屋 x 嘉之助 : シャドウプレイ2026 | Isekado x Kanosuke: Barrel Aged Shadowplay 2026",
        "untappd_url": None,
        "gemini_update": {
            "brewery_name_en": "Isekado x Kanosuke",
            "brewery_name_jp": "伊勢角屋 x 嘉之助",
            "beer_name_en": "Barrel Aged Shadowplay 2026",
            "beer_name_jp": "シャドウプレイ2026",
            "beer_name_core": "Barrel Aged Shadowplay 2026",
            "search_hint": "Barrel Aged Shadowplay 2026 Isekado Kanosuke",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": None,
        },
    },
]

# 2. 未エンリッチ商品 (12件) + Untappd未紐付け在庫ビール新規特定 (4件 + 横展開2件)
NEW_ENRICH_ITEMS = [
    # --- 未エンリッチ商品 (12件) ---
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8422",
        "name": "(空輸) ザ・テスト x ロアー / ミュージック・オブ・ザ・スフィアーズ (Hazy Triple IPA) 473ml缶 [The Test x RaR / Music of the Spheres]",
        "untappd_url": "https://untappd.com/b/test-music-of-the-spheres/7609930",
        "gemini_update": {
            "brewery_name_en": "TEST",
            "brewery_name_jp": "ザ・テスト",
            "beer_name_en": "Music of the Spheres",
            "beer_name_jp": "ミュージック・オブ・ザ・スフィアーズ",
            "beer_name_core": "Music of the Spheres",
            "search_hint": "Music of the Spheres TEST",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/test-music-of-the-spheres/7609930",
        },
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8421",
        "name": "(空輸) ザ・テスト x イーブルツイン / チケッツ・トゥ・ザ・サンセット (Hazy Triple IPA) 473ml缶 [The Test x Evil Twin / Tickets to the Sunset]",
        "untappd_url": "https://untappd.com/b/test-tickets-to-the-sunset/6921498",
        "gemini_update": {
            "brewery_name_en": "TEST",
            "brewery_name_jp": "ザ・テスト",
            "beer_name_en": "Tickets To the Sunset",
            "beer_name_jp": "チケッツ・トゥ・ザ・サンセット",
            "beer_name_core": "Tickets To the Sunset",
            "search_hint": "Tickets To the Sunset TEST",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/test-tickets-to-the-sunset/6921498",
        },
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8419",
        "name": "(空輸) オフスクリプト x トールツリーズ / ゼア・イズ・ノー・スプーン (DDH Hazy Double IPA) 473ml缶 [Off Script x Tall Trees / There Is No Spoon]",
        "untappd_url": "https://untappd.com/b/off-script-brewing-there-is-no-spoon/7161488",
        "gemini_update": {
            "brewery_name_en": "Off Script Brewing",
            "brewery_name_jp": "オフスクリプト",
            "beer_name_en": "There Is No Spoon",
            "beer_name_jp": "ゼア・イズ・ノー・スプーン",
            "beer_name_core": "There Is No Spoon",
            "search_hint": "There Is No Spoon Off Script Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/off-script-brewing-there-is-no-spoon/7161488",
        },
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8418",
        "name": "(空輸) リリック / フィアー・アディクテッド (Hazy Double IPA) 473ml缶 [Lyric Brewing Company / Fear Addicted]",
        "untappd_url": "https://untappd.com/b/lyric-brewing-company-fear-addicted-2026/7187613",
        "gemini_update": {
            "brewery_name_en": "Lyric Brewing Company",
            "brewery_name_jp": "リリック",
            "beer_name_en": "Fear Addicted (2026)",
            "beer_name_jp": "フィアー・アディクテッド",
            "beer_name_core": "Fear Addicted",
            "search_hint": "Fear Addicted 2026 Lyric Brewing Company",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/lyric-brewing-company-fear-addicted-2026/7187613",
        },
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8417",
        "name": "(空輸) リリック / ファミリア・ヒーローズ (Hazy Double IPA) 473ml缶 [Lyric Brewing Company / Familiar Heroes]",
        "untappd_url": "https://untappd.com/b/lyric-brewing-company-familiar-heroes-2026/7223006",
        "gemini_update": {
            "brewery_name_en": "Lyric Brewing Company",
            "brewery_name_jp": "リリック",
            "beer_name_en": "Familiar Heroes (2026)",
            "beer_name_jp": "ファミリア・ヒーローズ",
            "beer_name_core": "Familiar Heroes",
            "search_hint": "Familiar Heroes 2026 Lyric Brewing Company",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/lyric-brewing-company-familiar-heroes-2026/7223006",
        },
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8416",
        "name": "(空輸) リリック x メッソレム / デス・グリーツ・ミー・ウォーム (Hazy Double IPA) 473ml缶 [Lyric x Messorem / Death Greets Me Warm]",
        "untappd_url": "https://untappd.com/b/lyric-brewing-company-death-greets-me-warm/7187555",
        "gemini_update": {
            "brewery_name_en": "Lyric Brewing Company",
            "brewery_name_jp": "リリック",
            "beer_name_en": "Death Greets Me Warm",
            "beer_name_jp": "デス・グリーツ・ミー・ウォーム",
            "beer_name_core": "Death Greets Me Warm",
            "search_hint": "Death Greets Me Warm Lyric Brewing Company",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/lyric-brewing-company-death-greets-me-warm/7187555",
        },
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8414",
        "name": "シングルヒル / ファイブ・シスターズ (Fresh Hop IPA) 473ml缶 [Single Hill / Five Sisters]",
        "untappd_url": "https://untappd.com/b/single-hill-brewing-five-sisters-2026/6961657",
        "gemini_update": {
            "brewery_name_en": "Single Hill Brewing",
            "brewery_name_jp": "シングルヒル",
            "beer_name_en": "Five Sisters (2026)",
            "beer_name_jp": "ファイブ・シスターズ",
            "beer_name_core": "Five Sisters",
            "search_hint": "Five Sisters 2026 Single Hill Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/single-hill-brewing-five-sisters-2026/6961657",
        },
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8413",
        "name": "シングルヒル / ダンクマスター・フラッシュ (DDH West Coast DIPA) 473ml缶 [Single Hill / Dankmaster Flash]",
        "untappd_url": "https://untappd.com/b/single-hill-brewing-dankmaster-flash/6390587",
        "gemini_update": {
            "brewery_name_en": "Single Hill Brewing",
            "brewery_name_jp": "シングルヒル",
            "beer_name_en": "Dankmaster Flash",
            "beer_name_jp": "ダンクマスター・フラッシュ",
            "beer_name_core": "Dankmaster Flash",
            "search_hint": "Dankmaster Flash Single Hill Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/single-hill-brewing-dankmaster-flash/6390587",
        },
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8412",
        "name": "シングルヒル / フレッシュホップ・ラテラルA (Fresh Hop Hazy IPA) 473ml缶 [Single Hill / Fresh Hop Lateral A]",
        "untappd_url": "https://untappd.com/b/single-hill-brewing-fresh-hop-lateral-a-2026/6961659",
        "gemini_update": {
            "brewery_name_en": "Single Hill Brewing",
            "brewery_name_jp": "シングルヒル",
            "beer_name_en": "Fresh Hop Lateral A (2026)",
            "beer_name_jp": "フレッシュホップ・ラテラルA",
            "beer_name_core": "Fresh Hop Lateral A",
            "search_hint": "Fresh Hop Lateral A 2026 Single Hill Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/single-hill-brewing-fresh-hop-lateral-a-2026/6961659",
        },
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=3500",
        "name": "シングルヒル / イーストサイド (West Coast IPA) 473ml缶 [Single Hill / Eastside]",
        "untappd_url": "https://untappd.com/b/single-hill-brewing-eastside-ipa/2696024",
        "gemini_update": {
            "brewery_name_en": "Single Hill Brewing",
            "brewery_name_jp": "シングルヒル",
            "beer_name_en": "Eastside IPA",
            "beer_name_jp": "イーストサイド",
            "beer_name_core": "Eastside IPA",
            "search_hint": "Eastside IPA Single Hill Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/single-hill-brewing-eastside-ipa/2696024",
        },
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=5108",
        "name": "フリームファミリーブリュワーズ / ジャパニーズラガー 473ml缶 [pFriem Family Brewers / Japanese Lager]",
        "untappd_url": "https://untappd.com/b/pfriem-family-brewers-japanese-lager/2691203",
        "gemini_update": {
            "brewery_name_en": "pFriem Family Brewers",
            "brewery_name_jp": "フリームファミリーブリュワーズ",
            "beer_name_en": "Japanese Lager",
            "beer_name_jp": "ジャパニーズラガー",
            "beer_name_core": "Japanese Lager",
            "search_hint": "Japanese Lager pFriem Family Brewers",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/pfriem-family-brewers-japanese-lager/2691203",
        },
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8415",
        "name": "フリームファミリーブリュワーズ / トロピカルヘイジーIPA 355ml缶 [pFriem Family Brewers / Tropical Hazy IPA]",
        "untappd_url": "https://untappd.com/b/pfriem-family-brewers-tropical-hazy-ipa/6580696",
        "gemini_update": {
            "brewery_name_en": "pFriem Family Brewers",
            "brewery_name_jp": "フリームファミリーブリュワーズ",
            "beer_name_en": "Tropical Hazy IPA",
            "beer_name_jp": "トロピカルヘイジーIPA",
            "beer_name_core": "Tropical Hazy IPA",
            "search_hint": "Tropical Hazy IPA pFriem Family Brewers",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/pfriem-family-brewers-tropical-hazy-ipa/6580696",
        },
    },
    # --- Untappd未紐付け在庫ビールから新規特定 (4件 + 横展開2件) ---
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000003453",
        "name": "【DUBLIN STOUT/箕面ビール】",
        "untappd_url": "https://untappd.com/b/minoh-beer-dublin-stout/7684657",
        "gemini_update": {
            "brewery_name_en": "Minoh Beer",
            "brewery_name_jp": "箕面ビール",
            "beer_name_en": "Dublin Stout",
            "beer_name_jp": "DUBLIN STOUT",
            "beer_name_core": "Dublin Stout",
            "search_hint": "Dublin Stout Minoh Beer",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/minoh-beer-dublin-stout/7684657",
        },
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=3603",
        "name": "フリームファミリーブリュワーズ / ラガー (Helles Lager) 355ml缶 [pFriem Family Brewers / Lager]",
        "untappd_url": "https://untappd.com/b/pfriem-family-brewers-lager/5397709",
        "gemini_update": {
            "brewery_name_en": "pFriem Family Brewers",
            "brewery_name_jp": "フリームファミリーブリュワーズ",
            "beer_name_en": "Lager",
            "beer_name_jp": "ラガー",
            "beer_name_core": "Lager",
            "search_hint": "Lager pFriem Family Brewers",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/pfriem-family-brewers-lager/5397709",
        },
    },
    {
        "url": "https://151l.shop/?pid=194511776",
        "name": "【11/20（金）入荷予定】バテレ　プレスリア（VERTERE Preslia）",
        "untappd_url": "https://untappd.com/b/vertere-preslia/7685748",
        "gemini_update": {
            "brewery_name_en": "VERTERE",
            "brewery_name_jp": "バテレ",
            "beer_name_en": "Preslia",
            "beer_name_jp": "プレスリア",
            "beer_name_core": "Preslia",
            "search_hint": "Preslia VERTERE",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/vertere-preslia/7685748",
        },
    },
    {
        "url": "https://151l.shop/?pid=194511626",
        "name": "【11/20（金）入荷予定・必ず注意事項をお読みください】トパトパ　アザッカIPA（Topa Topa El Azacca IPA）",
        "untappd_url": "https://untappd.com/b/topa-topa-brewing-co-solitude-series-azacca/1263844",
        "gemini_update": {
            "brewery_name_en": "Topa Topa Brewing Co.",
            "brewery_name_jp": "トパトパ",
            "beer_name_en": "Solitude Series: Azacca",
            "beer_name_jp": "アザッカIPA",
            "beer_name_core": "Azacca",
            "search_hint": "Solitude Series Azacca Topa Topa Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/topa-topa-brewing-co-solitude-series-azacca/1263844",
        },
    },
    {
        "url": "https://151l.shop/?pid=194558801",
        "name": "【11/22（日）または24（火）入荷予定】オフスクリプト×トールツリーズ　ゼアーイズノースプーン　空輸（Off Script Brewing There is No Spoon）",
        "untappd_url": "https://untappd.com/b/off-script-brewing-there-is-no-spoon/7161488",
        "gemini_update": {
            "brewery_name_en": "Off Script Brewing",
            "brewery_name_jp": "オフスクリプト×トールツリーズ",
            "beer_name_en": "There Is No Spoon",
            "beer_name_jp": "ゼアーイズノースプーン",
            "beer_name_core": "There Is No Spoon",
            "search_hint": "There Is No Spoon Off Script Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/off-script-brewing-there-is-no-spoon/7161488",
        },
    },
    {
        "url": "https://beervolta.com/?pid=194573864",
        "name": "オフスクリプト x トールツリーズ : ゼア イズ ノー スプーン | Off Script x Tall Trees: There Is No Spoon",
        "untappd_url": "https://untappd.com/b/off-script-brewing-there-is-no-spoon/7161488",
        "gemini_update": {
            "brewery_name_en": "Off Script Brewing",
            "brewery_name_jp": "オフスクリプト x トールツリーズ",
            "beer_name_en": "There Is No Spoon",
            "beer_name_jp": "ゼア イズ ノー スプーン",
            "beer_name_core": "There Is No Spoon",
            "search_hint": "There Is No Spoon Off Script Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/off-script-brewing-there-is-no-spoon/7161488",
        },
    },
]

# 3. Untappd未登録確認済みアイテム (調査日時のみ更新)
UNLINKED_CHECKED_URLS = [
    "https://151l.shop/?pid=194512469",  # 伊勢角屋麦酒 バレルエイジドシャドウプレイ2026 (嘉之助樽版はUntappd未登録)
]

# 4. Untappd詳細取得・最新化対象 (新規特定・ローリング巡回監査・直近確認)
BEER_REFRESH_URLS = [
    # 新規エンリッチ & 未紐付け特定 (14銘柄ユニーク)
    "https://untappd.com/b/test-music-of-the-spheres/7609930",
    "https://untappd.com/b/test-tickets-to-the-sunset/6921498",
    "https://untappd.com/b/off-script-brewing-there-is-no-spoon/7161488",
    "https://untappd.com/b/lyric-brewing-company-fear-addicted-2026/7187613",
    "https://untappd.com/b/lyric-brewing-company-familiar-heroes-2026/7223006",
    "https://untappd.com/b/lyric-brewing-company-death-greets-me-warm/7187555",
    "https://untappd.com/b/single-hill-brewing-five-sisters-2026/6961657",
    "https://untappd.com/b/single-hill-brewing-dankmaster-flash/6390587",
    "https://untappd.com/b/single-hill-brewing-fresh-hop-lateral-a-2026/6961659",
    "https://untappd.com/b/single-hill-brewing-eastside-ipa/2696024",
    "https://untappd.com/b/pfriem-family-brewers-japanese-lager/2691203",
    "https://untappd.com/b/pfriem-family-brewers-tropical-hazy-ipa/6580696",
    "https://untappd.com/b/minoh-beer-dublin-stout/7684657",
    "https://untappd.com/b/pfriem-family-brewers-lager/5397709",
    "https://untappd.com/b/vertere-preslia/7685748",
    "https://untappd.com/b/topa-topa-brewing-co-solitude-series-azacca/1263844",
    # ローリング巡回監査 (5件)
    "https://untappd.com/b/farmentry-imperial-stout/6711419",
    "https://untappd.com/b/pfriem-family-brewers-pilsner/355980",
    "https://untappd.com/b/pfriem-family-brewers-pale/3939227",
    "https://untappd.com/b/pfriem-family-brewers-west-coast-ipa/5444652",
    "https://untappd.com/b/pfriem-family-brewers-ipa/202179",
    # 直近確認対象 (5件も最新化)
    "https://untappd.com/b/farmentry-farmentry-mihama-base-mohawk-ahead-wc-dipa/7674416",
    "https://untappd.com/b/farmentry-farmentry-mihama-base-mohawk-ahead-ne-dipa/7674433",
    "https://untappd.com/b/y-market-brewing-third-eye-ipa/6687632",
    "https://untappd.com/b/nomcraft-brewing-moon-calendar/6694683",
    "https://untappd.com/b/popihn-sauvages-assemblage-14-2021/5029273",
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
    logger.info(f"\n[1] Correcting {len(FIX_MISASSIGNED_ITEMS)} misassigned beer items...")
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
        logger.info(f"  Checked (unlinked on Untappd): {url}")
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
                f"| Style: {details.get('untappd_style')} | ABV: {details.get('untappd_abv')} "
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
