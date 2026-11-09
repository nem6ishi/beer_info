import asyncio
import logging
import time
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client, refresh_materialized_view, sync_execute
from backend.src.services.untappd.http_client import scrape_beer_details
from backend.src.core.utils import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 1. 新規エンリッチ & 未紐付け特定商品
NEW_ENRICH_ITEMS = [
    # --- WITCH CRAFT MARKET ---
    {
        "url": "https://witchcraftmarket.com/products/point-nemo",
        "untappd_url": "https://untappd.com/b/b-m-b-brewery-point-nemo/4338200",
        "gemini_update": {
            "brewery_name_en": "B.M.B Brewery",
            "brewery_name_jp": "B.M.Bブルーアリー",
            "beer_name_en": "Point Nemo",
            "beer_name_jp": "ポイント ネモ",
            "beer_name_core": "Point Nemo",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/b-m-b-brewery-point-nemo/4338200"
        }
    },

    # --- Antenna America: New Belgium ---
    {
        "url": "https://www.antenna-america.com/products/b042-c12001",
        "untappd_url": "https://untappd.com/b/new-belgium-brewing-company-fat-tire-ale/6887",
        "gemini_update": {
            "brewery_name_en": "New Belgium Brewing Company",
            "brewery_name_jp": "ニューベルジャン",
            "beer_name_en": "Fat Tire Ale",
            "beer_name_jp": "ファットタイヤ",
            "beer_name_core": "Fat Tire",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/new-belgium-brewing-company-fat-tire-ale/6887"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/b042-c12038",
        "untappd_url": "https://untappd.com/b/new-belgium-brewing-company-voodoo-ranger-ipa/1743544",
        "gemini_update": {
            "brewery_name_en": "New Belgium Brewing Company",
            "brewery_name_jp": "ニューベルジャン",
            "beer_name_en": "Voodoo Ranger IPA",
            "beer_name_jp": "ブードゥー レンジャー IPA",
            "beer_name_core": "Voodoo Ranger IPA",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/new-belgium-brewing-company-voodoo-ranger-ipa/1743544"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/b042-c12039",
        "untappd_url": "https://untappd.com/b/new-belgium-brewing-company-voodoo-ranger-imperial-ipa/1846245",
        "gemini_update": {
            "brewery_name_en": "New Belgium Brewing Company",
            "brewery_name_jp": "ニューベルジャン",
            "beer_name_en": "Voodoo Ranger Imperial IPA",
            "beer_name_jp": "ブードゥー レンジャー インペリアル IPA",
            "beer_name_core": "Voodoo Ranger Imperial IPA",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/new-belgium-brewing-company-voodoo-ranger-imperial-ipa/1846245"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/b042-c12060",
        "untappd_url": "https://untappd.com/b/new-belgium-brewing-company-voodoo-ranger-juicy-haze-ipa/2382318",
        "gemini_update": {
            "brewery_name_en": "New Belgium Brewing Company",
            "brewery_name_jp": "ニューベルジャン",
            "beer_name_en": "Voodoo Ranger Juicy Haze IPA",
            "beer_name_jp": "ブードゥー レンジャー ジューシー ヘイズ",
            "beer_name_core": "Voodoo Ranger Juicy Haze IPA",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/new-belgium-brewing-company-voodoo-ranger-juicy-haze-ipa/2382318"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/b042-c12087",
        "untappd_url": "https://untappd.com/b/new-belgium-brewing-company-voodoo-ranger-juice-force-ipa/4543503",
        "gemini_update": {
            "brewery_name_en": "New Belgium Brewing Company",
            "brewery_name_jp": "ニューベルジャン",
            "beer_name_en": "Voodoo Ranger Juice Force IPA",
            "beer_name_jp": "ブードゥー レンジャー ジュースフォース",
            "beer_name_core": "Voodoo Ranger Juice Force IPA",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/new-belgium-brewing-company-voodoo-ranger-juice-force-ipa/4543503"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/b042-c12088",
        "untappd_url": "https://untappd.com/b/new-belgium-brewing-company-voodoo-ranger-tropic-force-ipa/5632477",
        "gemini_update": {
            "brewery_name_en": "New Belgium Brewing Company",
            "brewery_name_jp": "ニューベルジャン",
            "beer_name_en": "Voodoo Ranger Tropic Force IPA",
            "beer_name_jp": "ブードゥー レンジャー トロピックフォース",
            "beer_name_core": "Voodoo Ranger Tropic Force IPA",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/new-belgium-brewing-company-voodoo-ranger-tropic-force-ipa/5632477"
        }
    },

    # --- Antenna America: Stem Ciders ---
    {
        "url": "https://www.antenna-america.com/products/c004-c12006",
        "untappd_url": "https://untappd.com/b/stem-ciders-chile-guava/2763026",
        "gemini_update": {
            "brewery_name_en": "Stem Ciders",
            "brewery_name_jp": "ステムサイダーズ",
            "beer_name_en": "Chile Guava",
            "beer_name_jp": "チリ グアバ",
            "beer_name_core": "Chile Guava",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/stem-ciders-chile-guava/2763026"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/c004-c12001",
        "untappd_url": "https://untappd.com/b/stem-ciders-real-dry/559144",
        "gemini_update": {
            "brewery_name_en": "Stem Ciders",
            "brewery_name_jp": "ステムサイダーズ",
            "beer_name_en": "Real Dry",
            "beer_name_jp": "リアルドライ",
            "beer_name_core": "Real Dry",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/stem-ciders-real-dry/559144"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/c004-c12010",
        "untappd_url": "https://untappd.com/b/stem-ciders-off-dry/1930689",
        "gemini_update": {
            "brewery_name_en": "Stem Ciders",
            "brewery_name_jp": "ステムサイダーズ",
            "beer_name_en": "Off-Dry",
            "beer_name_jp": "オフドライ",
            "beer_name_core": "Off-Dry",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/stem-ciders-off-dry/1930689"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/c004-c12011",
        "untappd_url": "https://untappd.com/b/stem-ciders-apricot-haze/5367941",
        "gemini_update": {
            "brewery_name_en": "Stem Ciders",
            "brewery_name_jp": "ステムサイダーズ",
            "beer_name_en": "Apricot Haze",
            "beer_name_jp": "アプリコット ヘイズ",
            "beer_name_core": "Apricot Haze",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/stem-ciders-apricot-haze/5367941"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/c004-c12012",
        "untappd_url": "https://untappd.com/b/stem-ciders-blueberry-lime/6207254",
        "gemini_update": {
            "brewery_name_en": "Stem Ciders",
            "brewery_name_jp": "ステムサイダーズ",
            "beer_name_en": "Blueberry Lime",
            "beer_name_jp": "ブルーベリー ライム",
            "beer_name_core": "Blueberry Lime",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/stem-ciders-blueberry-lime/6207254"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/c004-c12013",
        "untappd_url": "https://untappd.com/b/stem-ciders-harvest-peach/6492214",
        "gemini_update": {
            "brewery_name_en": "Stem Ciders",
            "brewery_name_jp": "ステムサイダーズ",
            "beer_name_en": "Harvest Peach",
            "beer_name_jp": "ハーベスト ピーチ",
            "beer_name_core": "Harvest Peach",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/stem-ciders-harvest-peach/6492214"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/c004-c12003",
        "untappd_url": "https://untappd.com/b/stem-ciders-pear/2032805",
        "gemini_update": {
            "brewery_name_en": "Stem Ciders",
            "brewery_name_jp": "ステムサイダーズ",
            "beer_name_en": "Pear",
            "beer_name_jp": "ペアー",
            "beer_name_core": "Pear",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/stem-ciders-pear/2032805"
        }
    },

    # --- 一期一会～る ---
    {
        "url": "https://151l.shop/?pid=194371181",
        "untappd_url": "https://untappd.com/b/uchu-brewing-whiteout/7659081",
        "gemini_update": {
            "brewery_name_en": "UCHU Brewing",
            "brewery_name_jp": "うちゅうブルーイング",
            "beer_name_en": "WHITEOUT",
            "beer_name_jp": "ホワイトアウト",
            "beer_name_core": "WHITEOUT",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/uchu-brewing-whiteout/7659081"
        }
    },
    {
        "url": "https://151l.shop/?pid=194319375",
        "untappd_url": "https://untappd.com/b/y-market-brewing-lupulin-nectar/7663871",
        "gemini_update": {
            "brewery_name_en": "Y.Market Brewing",
            "brewery_name_jp": "ワイマーケット",
            "beer_name_en": "Lupulin Nectar ∀",
            "beer_name_jp": "ルプリンネクター ターンエー",
            "beer_name_core": "Lupulin Nectar ∀",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/y-market-brewing-lupulin-nectar/7663871"
        }
    },

    # --- マルホ酒店 ---
    {
        "url": "https://maruho.shop/products/アオイト-750ml-甘く浮く",
        "untappd_url": "https://untappd.com/b/amaku-uku-aoito-2026/7628430",
        "gemini_update": {
            "brewery_name_en": "Amaku Uku",
            "brewery_name_jp": "甘く浮く",
            "beer_name_en": "Aoito 2026",
            "beer_name_jp": "アオイト 2026",
            "beer_name_core": "Aoito",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/amaku-uku-aoito-2026/7628430"
        }
    },
    {
        "url": "https://maruho.shop/products/soleil-473ml-hudson-valley",
        "untappd_url": "https://untappd.com/b/hudson-valley-brewery-soleil-sipa/2597723",
        "gemini_update": {
            "brewery_name_en": "Hudson Valley Brewery",
            "brewery_name_jp": "ハドソンバレー",
            "beer_name_en": "Soleil SIPA",
            "beer_name_jp": "ソレイユ",
            "beer_name_core": "Soleil",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/hudson-valley-brewery-soleil-sipa/2597723"
        }
    },

    # --- アローム ---
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8295",
        "untappd_url": "https://untappd.com/b/totopia-brewery-4phobia-sumi/7656946",
        "gemini_update": {
            "brewery_name_en": "Totopia Brewery",
            "brewery_name_jp": "トートピアブルワリー",
            "beer_name_en": "4phobia - Sumi",
            "beer_name_jp": "4フォビア 澄",
            "beer_name_core": "4phobia",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/totopia-brewery-4phobia-sumi/7656946"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8283",
        "untappd_url": "https://untappd.com/b/ajb-co-cherry-lager/6721837",
        "gemini_update": {
            "brewery_name_en": "AJB Co. x Marble Beers",
            "brewery_name_jp": "AJB x マーブル",
            "beer_name_en": "Cherry Lager",
            "beer_name_jp": "チェリーラガー",
            "beer_name_core": "Cherry Lager",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/ajb-co-cherry-lager/6721837"
        }
    },

    # --- ちょうせいや ---
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000003223",
        "untappd_url": "https://untappd.com/b/y-market-brewing-ichiban-bakujyu-ipa/7637879",
        "gemini_update": {
            "brewery_name_en": "Y.Market Brewing",
            "brewery_name_jp": "ワイマーケット",
            "beer_name_en": "Ichiban Bakujyu IPA",
            "beer_name_jp": "一番麦汁IPA",
            "beer_name_core": "Ichiban Bakujyu IPA",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/y-market-brewing-ichiban-bakujyu-ipa/7637879"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000001071",
        "untappd_url": "https://untappd.com/b/yorocco-beer-skywalker-ipa/666451",
        "gemini_update": {
            "brewery_name_en": "Yorocco Beer",
            "brewery_name_jp": "ヨロッコビール",
            "beer_name_en": "Sky Walker IPA",
            "beer_name_jp": "スカイウォーカー IPA",
            "beer_name_core": "Sky Walker IPA",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/yorocco-beer-skywalker-ipa/666451"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000000083",
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
        "url": "https://beer-chouseiya.shop/shopdetail/000000003225",
        "untappd_url": "https://untappd.com/b/west-coast-brewing-liquid-magic/7656688",
        "gemini_update": {
            "brewery_name_en": "West Coast Brewing",
            "brewery_name_jp": "ウエストコーストブルーイング",
            "beer_name_en": "Liquid Magic",
            "beer_name_jp": "リキッド マジック",
            "beer_name_core": "Liquid Magic",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/west-coast-brewing-liquid-magic/7656688"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000003005",
        "untappd_url": "https://untappd.com/b/west-coast-brewing-full-hop-alchemist-r11/7656689",
        "gemini_update": {
            "brewery_name_en": "West Coast Brewing",
            "brewery_name_jp": "ウエストコーストブルーイング",
            "beer_name_en": "Full Hop Alchemist r11",
            "beer_name_jp": "フルホップ アルケミスト r11",
            "beer_name_core": "Full Hop Alchemist r11",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/west-coast-brewing-full-hop-alchemist-r11/7656689"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000002217",
        "untappd_url": "https://untappd.com/b/yorocco-beer-harvest-saison-2026/7651097",
        "gemini_update": {
            "brewery_name_en": "Yorocco Beer",
            "brewery_name_jp": "ヨロッコビール",
            "beer_name_en": "Harvest Saison 2026",
            "beer_name_jp": "ハーベスト セゾン 2026",
            "beer_name_core": "Harvest Saison",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/yorocco-beer-harvest-saison-2026/7651097"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000000101",
        "untappd_url": "https://untappd.com/b/yorocco-beer-you-can-color-outside-the-lines/7616777",
        "gemini_update": {
            "brewery_name_en": "Yorocco Beer",
            "brewery_name_jp": "ヨロッコビール",
            "beer_name_en": "You Can Color Outside the Lines!",
            "beer_name_jp": "ユー キャン カラー アウトサイド ザ ラインズ",
            "beer_name_core": "You Can Color Outside the Lines",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/yorocco-beer-you-can-color-outside-the-lines/7616777"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000001253",
        "untappd_url": "https://untappd.com/b/yorocco-beer-bright-moments/3930459",
        "gemini_update": {
            "brewery_name_en": "Yorocco Beer",
            "brewery_name_jp": "ヨロッコビール",
            "beer_name_en": "Bright Moments",
            "beer_name_jp": "ブライト モーメンツ",
            "beer_name_core": "Bright Moments",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/yorocco-beer-bright-moments/3930459"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000003405",
        "untappd_url": "https://untappd.com/b/yorocco-beer-lager-du-soleil/6825983",
        "gemini_update": {
            "brewery_name_en": "Yorocco Beer",
            "brewery_name_jp": "ヨロッコビール",
            "beer_name_en": "Lager Du Soleil",
            "beer_name_jp": "ラガー ド ソレイユ",
            "beer_name_core": "Lager Du Soleil",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/yorocco-beer-lager-du-soleil/6825983"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000001789",
        "untappd_url": "https://untappd.com/b/y-market-brewing-lupulin-nectar/7663871",
        "gemini_update": {
            "brewery_name_en": "Y.Market Brewing",
            "brewery_name_jp": "ワイマーケット",
            "beer_name_en": "Lupulin Nectar ∀",
            "beer_name_jp": "ルプリンネクター ターンエー",
            "beer_name_core": "Lupulin Nectar ∀",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/y-market-brewing-lupulin-nectar/7663871"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000003440",
        "untappd_url": "https://untappd.com/b/tamamura-honten-co-barrel-aged-yama-bushi-tea-for-two-2-red/7628557",
        "gemini_update": {
            "brewery_name_en": "Tamamura Honten x Taihu Brewing",
            "brewery_name_jp": "玉村本店 x 臺虎精釀",
            "beer_name_en": "Barrel Aged Yama-Bushi Tea for Two 2 \"red\"",
            "beer_name_jp": "木樽熟成 山伏 ティー・フォー・トゥー 2 レッド",
            "beer_name_core": "Tea for Two 2 red",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/tamamura-honten-co-barrel-aged-yama-bushi-tea-for-two-2-red/7628557"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000001724",
        "untappd_url": "https://untappd.com/b/tamamura-honten-co-barrel-aged-yama-bushi-tea-for-two-2-blonde/7628551",
        "gemini_update": {
            "brewery_name_en": "Tamamura Honten x Taihu Brewing",
            "brewery_name_jp": "玉村本店 x 臺虎精釀",
            "beer_name_en": "Barrel Aged Yama-Bushi Tea for Two 2 \"blonde\"",
            "beer_name_jp": "木樽熟成 山伏 ティー・フォー・トゥー 2 ブロンド",
            "beer_name_core": "Tea for Two 2 blonde",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/tamamura-honten-co-barrel-aged-yama-bushi-tea-for-two-2-blonde/7628551"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000003428",
        "untappd_url": "https://untappd.com/b/tamamura-honten-co-shiga-kogen-house-lager-4-01-yamada-nishiki/6918512",
        "gemini_update": {
            "brewery_name_en": "Tamamura Honten Co.",
            "brewery_name_jp": "志賀高原ビール",
            "beer_name_en": "House Lager 4.01 Yamada Nishiki",
            "beer_name_jp": "ハウスラガー 4.01 山田錦",
            "beer_name_core": "House Lager 4.01",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/tamamura-honten-co-shiga-kogen-house-lager-4-01-yamada-nishiki/6918512"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000003359",
        "untappd_url": "https://untappd.com/b/tamamura-honten-co-shiga-kogen-fresh-hop-pils-2026/7074718",
        "gemini_update": {
            "brewery_name_en": "Tamamura Honten Co.",
            "brewery_name_jp": "志賀高原ビール",
            "beer_name_en": "Fresh Hop Pils (2026)",
            "beer_name_jp": "フレッシュホップ ピルス (2026)",
            "beer_name_core": "Fresh Hop Pils",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/tamamura-honten-co-shiga-kogen-fresh-hop-pils-2026/7074718"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000002275",
        "untappd_url": "https://untappd.com/b/tamamura-honten-co-shiga-kogen-fresh-hop-africa-pale-ale-2026/6918508",
        "gemini_update": {
            "brewery_name_en": "Tamamura Honten Co.",
            "brewery_name_jp": "志賀高原ビール",
            "beer_name_en": "Fresh Hop Africa Pale Ale (2026)",
            "beer_name_jp": "フレッシュホップ アフリカペールエール (2026)",
            "beer_name_core": "Fresh Hop Africa Pale Ale",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/tamamura-honten-co-shiga-kogen-fresh-hop-africa-pale-ale-2026/6918508"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000001797",
        "untappd_url": "https://untappd.com/b/tamamura-honten-co-shiga-kogen-mugamuchu/2829795",
        "gemini_update": {
            "brewery_name_en": "Tamamura Honten Co.",
            "brewery_name_jp": "志賀高原ビール",
            "beer_name_en": "Mugamuchu",
            "beer_name_jp": "無我霧中",
            "beer_name_core": "Mugamuchu",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/tamamura-honten-co-shiga-kogen-mugamuchu/2829795"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000000982",
        "untappd_url": "https://untappd.com/b/tamamura-honten-co-shiga-kogen-takassy/6673805",
        "gemini_update": {
            "brewery_name_en": "Tamamura Honten Co.",
            "brewery_name_jp": "志賀高原ビール",
            "beer_name_en": "Takassy",
            "beer_name_jp": "タカッシー",
            "beer_name_core": "Takassy",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/tamamura-honten-co-shiga-kogen-takassy/6673805"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000000494",
        "untappd_url": "https://untappd.com/b/tamamura-honten-co-shiga-kogen-house-ipa/20222",
        "gemini_update": {
            "brewery_name_en": "Tamamura Honten Co.",
            "brewery_name_jp": "志賀高原ビール",
            "beer_name_en": "House IPA",
            "beer_name_jp": "ハウスIPA",
            "beer_name_core": "House IPA",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/tamamura-honten-co-shiga-kogen-house-ipa/20222"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000000020",
        "untappd_url": "https://untappd.com/b/tamamura-honten-co-shiga-kogen-vsow/6758882",
        "gemini_update": {
            "brewery_name_en": "Tamamura Honten Co.",
            "brewery_name_jp": "志賀高原ビール",
            "beer_name_en": "VSOW",
            "beer_name_jp": "VSOW",
            "beer_name_core": "VSOW",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/tamamura-honten-co-shiga-kogen-vsow/6758882"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000002606",
        "untappd_url": "https://untappd.com/b/uchu-brewing-ghost-in-the-nebula/7648425",
        "gemini_update": {
            "brewery_name_en": "UCHU Brewing",
            "brewery_name_jp": "うちゅうブルーイング",
            "beer_name_en": "GHOST IN THE NEBULA",
            "beer_name_jp": "ゴースト イン ザ ネビュラ",
            "beer_name_core": "GHOST IN THE NEBULA",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/uchu-brewing-ghost-in-the-nebula/7648425"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000000863",
        "untappd_url": "https://untappd.com/b/uchu-brewing-orochi/7646855",
        "gemini_update": {
            "brewery_name_en": "UCHU Brewing",
            "brewery_name_jp": "うちゅうブルーイング",
            "beer_name_en": "OROCHI",
            "beer_name_jp": "オロチ",
            "beer_name_core": "OROCHI",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/uchu-brewing-orochi/7646855"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000002020",
        "untappd_url": "https://untappd.com/b/minoh-beer-high-collar-pils/6779247",
        "gemini_update": {
            "brewery_name_en": "Minoh Beer",
            "brewery_name_jp": "箕面ビール",
            "beer_name_en": "High Collar Pils",
            "beer_name_jp": "ハイカラピルス",
            "beer_name_core": "High Collar Pils",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/minoh-beer-high-collar-pils/6779247"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000001815",
        "untappd_url": "https://untappd.com/b/minoh-beer-tea-bitter/6754566",
        "gemini_update": {
            "brewery_name_en": "Minoh Beer",
            "brewery_name_jp": "箕面ビール",
            "beer_name_en": "Tea Bitter",
            "beer_name_jp": "紅茶ビター",
            "beer_name_core": "Tea Bitter",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/minoh-beer-tea-bitter/6754566"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000000783",
        "untappd_url": "https://untappd.com/b/almanac-dream-sequence-01/3773386",
        "gemini_update": {
            "brewery_name_en": "Almanac Beer Company",
            "brewery_name_jp": "オルマナック",
            "beer_name_en": "Dream Sequence 01",
            "beer_name_jp": "ドリーム シーケンス 01",
            "beer_name_core": "Dream Sequence 01",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/almanac-dream-sequence-01/3773386"
        }
    }
]

# 2. 誤紐付けの是正（Audit Correction）
CORRECTION_ITEMS = [
    {
        "url": "https://witchcraftmarket.com/products/art-blood-2",
        "untappd_url": "https://untappd.com/b/collective-arts-brewing-art-and-blood-ii/6885830",
        "gemini_update": {
            "brewery_name_en": "Collective Arts Brewing x Blood Brothers",
            "brewery_name_jp": "コレクティブアーツ x ブラッドブラザーズ",
            "beer_name_en": "Art & Blood II",
            "beer_name_jp": "アート & ブラッド 2",
            "beer_name_core": "Art & Blood II",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/collective-arts-brewing-art-and-blood-ii/6885830"
        }
    }
]

# 3. ローリング巡回・情報更新対象
BEER_REFRESH_URLS = [
    "https://untappd.com/b/finback-brewery-beyond/6733686",
    "https://untappd.com/b/collective-arts-brewing-between-the-palms/6623357",
    "https://untappd.com/b/saltfields-brewing-nodogoshi-rice-lager/6234259",
    "https://untappd.com/b/collective-arts-brewing-daily-forecast-mimosa/4748563",
    "https://untappd.com/b/collective-arts-brewing-art-and-blood-ii/6885830"
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

    # 1. 新規エンリッチ & 未紐付け特定商品の登録
    logger.info(f"\n[1] Enriching {len(NEW_ENRICH_ITEMS)} target beers...")
    for item in NEW_ENRICH_ITEMS:
        url = item["url"]
        untappd_url = item["untappd_url"]
        gem_update = item["gemini_update"]

        logger.info(f"  Enriching {url} -> {untappd_url}")

        # gemini_data upsert
        gem_update["url"] = url
        gem_update["updated_at"] = now_iso
        run_db_op(lambda: sync_execute(sb.table("gemini_data").upsert(gem_update, on_conflict="url")))

        # scraped_beers update
        run_db_op(lambda: sync_execute(sb.table("scraped_beers").update({
            "untappd_url": untappd_url,
            "untappd_enriched_at": now_iso
        }).eq("url", url)))

        # untappd_data scrape & upsert (if details needed)
        details = await scrape_beer_details(untappd_url)
        if details:
            payload = map_details_to_payload(details)
            payload["untappd_url"] = untappd_url
            payload["fetched_at"] = now_iso
            run_db_op(lambda: sync_execute(sb.table("untappd_data").upsert(payload, on_conflict="untappd_url")))
            logger.info(f"  ✅ Enriched & Saved: [{details.get('untappd_brewery_name')}] {details.get('untappd_beer_name')} (Rating: {details.get('untappd_rating')})")
        else:
            logger.warning(f"  ⚠️ Could not scrape Untappd details for {untappd_url}")
        await asyncio.sleep(0.5)

    # 2. 誤紐付けの是正
    if CORRECTION_ITEMS:
        logger.info(f"\n[2] Correcting {len(CORRECTION_ITEMS)} mismatched items...")
        for item in CORRECTION_ITEMS:
            url = item["url"]
            untappd_url = item["untappd_url"]
            gem_update = item["gemini_update"]

            logger.info(f"  Correcting {url} -> {untappd_url}")

            # gemini_data upsert
            gem_update["url"] = url
            gem_update["updated_at"] = now_iso
            run_db_op(lambda: sync_execute(sb.table("gemini_data").upsert(gem_update, on_conflict="url")))

            # scraped_beers update
            run_db_op(lambda: sync_execute(sb.table("scraped_beers").update({
                "untappd_url": untappd_url,
                "untappd_enriched_at": now_iso
            }).eq("url", url)))

            # untappd_data scrape & upsert
            details = await scrape_beer_details(untappd_url)
            if details:
                payload = map_details_to_payload(details)
                payload["untappd_url"] = untappd_url
                payload["fetched_at"] = now_iso
                run_db_op(lambda: sync_execute(sb.table("untappd_data").upsert(payload, on_conflict="untappd_url")))
                logger.info(f"  ✅ Corrected & Saved: [{details.get('untappd_brewery_name')}] {details.get('untappd_beer_name')} (Rating: {details.get('untappd_rating')})")
            else:
                logger.warning(f"  ⚠️ Could not scrape Untappd details for {untappd_url}")
            await asyncio.sleep(0.5)

    # 3. ローリング巡回・Untappd データの最新化
    logger.info(f"\n[3] Scraping & updating Untappd details for {len(BEER_REFRESH_URLS)} rolling audit beers...")
    for untappd_url in BEER_REFRESH_URLS:
        logger.info(f"  Scraping details for {untappd_url}...")
        details = await scrape_beer_details(untappd_url)
        if details:
            payload = map_details_to_payload(details)
            payload["untappd_url"] = untappd_url
            payload["fetched_at"] = now_iso
            run_db_op(lambda: sync_execute(sb.table("untappd_data").upsert(payload, on_conflict="untappd_url")))
            logger.info(f"  ✅ Updated: [{details.get('untappd_brewery_name')}] {details.get('untappd_beer_name')} | Rating: {details.get('untappd_rating')} | Checkins: {details.get('untappd_rating_count')}")
        else:
            logger.warning(f"  ❌ Failed to scrape details for {untappd_url}")
        await asyncio.sleep(0.5)

    # 4. マテリアライズドビューのリフレッシュ
    logger.info("\n[4] Refreshing Materialized View (beer_info_view)...")
    run_db_op(lambda: refresh_materialized_view(sb, logger))
    logger.info("✅ Materialized view refreshed successfully!")

if __name__ == "__main__":
    asyncio.run(main())
