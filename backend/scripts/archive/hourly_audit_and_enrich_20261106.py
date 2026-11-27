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
    # --- 8 bit Brewing Company ---
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8298",
        "untappd_url": "https://untappd.com/b/8-bit-brewing-company-no-fly-zone/6310908",
        "gemini_update": {
            "brewery_name_en": "8 bit Brewing Company",
            "brewery_name_jp": "エイトビット",
            "beer_name_en": "No Fly Zone",
            "beer_name_jp": "ノー フライゾーン",
            "beer_name_core": "No Fly Zone",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/8-bit-brewing-company-no-fly-zone/6310908"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8297",
        "untappd_url": "https://untappd.com/b/8-bit-brewing-company-calling-in-sick/5588477",
        "gemini_update": {
            "brewery_name_en": "8 bit Brewing Company",
            "brewery_name_jp": "エイトビット",
            "beer_name_en": "Calling In Sick",
            "beer_name_jp": "コーリング イン シック",
            "beer_name_core": "Calling In Sick",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/8-bit-brewing-company-calling-in-sick/5588477"
        }
    },

    # --- Bootstrap Brewing Company ---
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8296",
        "untappd_url": "https://untappd.com/b/bootstrap-brewing-double-lush-puppy-juicy-ipa/5727060",
        "gemini_update": {
            "brewery_name_en": "Bootstrap Brewing Company",
            "brewery_name_jp": "ブートストラップ",
            "beer_name_en": "Double Lush Puppy",
            "beer_name_jp": "ダブル ラッシュ パピー",
            "beer_name_core": "Double Lush Puppy",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/bootstrap-brewing-double-lush-puppy-juicy-ipa/5727060"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=5435",
        "untappd_url": "https://untappd.com/b/bootstrap-brewing-boat-snack-hazy-ipa/4639830",
        "gemini_update": {
            "brewery_name_en": "Bootstrap Brewing Company",
            "brewery_name_jp": "ブートストラップ",
            "beer_name_en": "Boat Snack",
            "beer_name_jp": "ボート スナック",
            "beer_name_core": "Boat Snack",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/bootstrap-brewing-boat-snack-hazy-ipa/4639830"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=5432",
        "untappd_url": "https://untappd.com/b/bootstrap-brewing-insane-rush-ipa/200225",
        "gemini_update": {
            "brewery_name_en": "Bootstrap Brewing Company",
            "brewery_name_jp": "ブートストラップ",
            "beer_name_en": "Insane Rush",
            "beer_name_jp": "インセイン ラッシュ",
            "beer_name_core": "Insane Rush",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/bootstrap-brewing-insane-rush-ipa/200225"
        }
    },

    # --- Y.Market Brewing ---
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8292",
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
        "url": "https://www.arome.jp/products/detail.php?product_id=8291",
        "untappd_url": "https://untappd.com/b/y-market-brewing-yoriai-nagoya-union-2026-2026/6960998",
        "gemini_update": {
            "brewery_name_en": "Y.Market Brewing",
            "brewery_name_jp": "ワイマーケット",
            "beer_name_en": "Yoriai Nagoya Union 2026",
            "beer_name_jp": "よりあい ナゴヤユニオン 2026",
            "beer_name_core": "Yoriai Nagoya Union 2026",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/y-market-brewing-yoriai-nagoya-union-2026-2026/6960998"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8290",
        "untappd_url": "https://untappd.com/b/y-market-brewing-frais-pils/6841925",
        "gemini_update": {
            "brewery_name_en": "Y.Market Brewing",
            "brewery_name_jp": "ワイマーケット",
            "beer_name_en": "Frais Pils",
            "beer_name_jp": "フレピルス",
            "beer_name_core": "Frais Pils",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/y-market-brewing-frais-pils/6841925"
        }
    },

    # --- West Coast Brewing (Liquid Magic & Full Hop Alchemist r11 各店舗分) ---
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8289",
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
        "url": "https://151l.shop/?pid=194319904",
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
        "url": "https://www.arome.jp/products/detail.php?product_id=8288",
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
        "url": "https://151l.shop/?pid=194319876",
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

    # --- 玉村本店 x 臺虎精釀 (Tea for Two 2 “red”) ---
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8287",
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

    # --- Anglo Japanese Brewing ---
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8285",
        "untappd_url": "https://untappd.com/b/ajb-co-forest-script/6961990",
        "gemini_update": {
            "brewery_name_en": "Anglo Japanese Brewing",
            "brewery_name_jp": "アングロ ジャパニーズ ブルーイング",
            "beer_name_en": "Forest Script",
            "beer_name_jp": "フォレスト スクリプト",
            "beer_name_core": "Forest Script",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/ajb-co-forest-script/6961990"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8284",
        "untappd_url": "https://untappd.com/b/ajb-co-re-lees/6914708",
        "gemini_update": {
            "brewery_name_en": "Anglo Japanese Brewing",
            "brewery_name_jp": "アングロ ジャパニーズ ブルーイング",
            "beer_name_en": "Re:Lees",
            "beer_name_jp": "リ：リーズ",
            "beer_name_core": "Re:Lees",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/ajb-co-re-lees/6914708"
        }
    },

    # --- マルホ酒店 RaR 3件 ---
    {
        "url": "https://maruho.shop/products/encapsulation-of-color-collab-w-test-473ml-rar",
        "untappd_url": "https://untappd.com/b/rar-brewing-encapsulation-of-color/7151932",
        "gemini_update": {
            "brewery_name_en": "RaR Brewing x The Test Brewery",
            "brewery_name_jp": "ロアーブルーイング x ザ・テスト・ブルワリー",
            "beer_name_en": "Encapsulation of Color",
            "beer_name_jp": "エンカプセレーション・オブ・カラー",
            "beer_name_core": "Encapsulation of Color",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/rar-brewing-encapsulation-of-color/7151932"
        }
    },
    {
        "url": "https://maruho.shop/products/believing-makes-it-better-collab-w-cloud-water-473ml-rar",
        "untappd_url": "https://untappd.com/b/rar-brewing-believing-makes-it-better/6852408",
        "gemini_update": {
            "brewery_name_en": "RaR Brewing x Cloudwater Brew Co.",
            "brewery_name_jp": "ロアーブルーイング x クラウドウォーター",
            "beer_name_en": "Believing Makes It Better",
            "beer_name_jp": "ビリーヴィン・メイクス・イット・ベター",
            "beer_name_core": "Believing Makes It Better",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/rar-brewing-believing-makes-it-better/6852408"
        }
    },
    {
        "url": "https://maruho.shop/products/savior-from-the-sea-collab-w-uchu-brewing-473ml-rar",
        "untappd_url": "https://untappd.com/b/rar-brewing-savior-from-the-sea/6924349",
        "gemini_update": {
            "brewery_name_en": "RaR Brewing x Uchu Brewing",
            "brewery_name_jp": "ロアーブルーイング x うちゅうブルーイング",
            "beer_name_en": "Savior From the Sea",
            "beer_name_jp": "セイヴァー・フロム・ザ・シー",
            "beer_name_core": "Savior From the Sea",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/rar-brewing-savior-from-the-sea/6924349"
        }
    },

    # --- Inkhorn BUNCHO 2026 #4 (一期一会～る 新規 & アローム 是正) ---
    {
        "url": "https://151l.shop/?pid=194327704",
        "untappd_url": "https://untappd.com/b/inkhorn-brewing-buncho-2026-4/7659119",
        "gemini_update": {
            "brewery_name_en": "Inkhorn Brewing",
            "brewery_name_jp": "インクホーン ブルーイング",
            "beer_name_en": "Buncho (2026 #4)",
            "beer_name_jp": "文鳥 2026 #4",
            "beer_name_core": "Buncho 2026 #4",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/inkhorn-brewing-buncho-2026-4/7659119"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=3185",
        "untappd_url": "https://untappd.com/b/inkhorn-brewing-buncho-2026-4/7659119",
        "gemini_update": {
            "brewery_name_en": "Inkhorn Brewing",
            "brewery_name_jp": "インクホーン ブルーイング",
            "beer_name_en": "Buncho (2026 #4)",
            "beer_name_jp": "文鳥 2026 #4",
            "beer_name_core": "Buncho 2026 #4",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/inkhorn-brewing-buncho-2026-4/7659119"
        }
    },

    # --- 未紐付け在庫ビールの特定・解消 4件 ---
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=4826",
        "untappd_url": "https://untappd.com/b/ajb-co-2026-aramatsuri2026/7608900",
        "gemini_update": {
            "brewery_name_en": "Anglo Japanese Brewing",
            "brewery_name_jp": "アングロ ジャパニーズ ブルーイング",
            "beer_name_en": "Aramatsuri 2026",
            "beer_name_jp": "荒祭 2026",
            "beer_name_core": "Aramatsuri 2026",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/ajb-co-2026-aramatsuri2026/7608900"
        }
    },
    {
        "url": "https://151l.shop/?pid=192919839",
        "untappd_url": "https://untappd.com/b/isekado-kadolabo-039-french-53-meets-beer/7657872",
        "gemini_update": {
            "brewery_name_en": "Ise Kadoya Brewery",
            "brewery_name_jp": "伊勢角屋麦酒",
            "beer_name_en": "Kadolabo 039 French 5³ Meets Beer",
            "beer_name_jp": "カドラボ 039 フレンチ 53 ミーツ ビール",
            "beer_name_core": "Kadolabo 039",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/isekado-kadolabo-039-french-53-meets-beer/7657872"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8208",
        "untappd_url": "https://untappd.com/b/vertere-cotinus/7652896",
        "gemini_update": {
            "brewery_name_en": "VERTERE",
            "brewery_name_jp": "バテレ",
            "beer_name_en": "Cotinus",
            "beer_name_jp": "コティヌス",
            "beer_name_core": "Cotinus",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/vertere-cotinus/7652896"
        }
    },
    {
        "url": "https://151l.shop/?pid=194189256",
        "untappd_url": "https://untappd.com/b/hinterland-brewery-packerland-pilsner/501979",
        "gemini_update": {
            "brewery_name_en": "Hinterland Brewery",
            "brewery_name_jp": "ヒンターランド",
            "beer_name_en": "Packerland Pilsner",
            "beer_name_jp": "パッカーランド ピルスナー",
            "beer_name_core": "Packerland Pilsner",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/hinterland-brewery-packerland-pilsner/501979"
        }
    },

    # --- 店舗横断同一商品 (151l, アローム, ちょうせいや, BEER VOLTA) ---
    {
        "url": "https://151l.shop/?pid=194319824",
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
        "url": "https://151l.shop/?pid=194319847",
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
        "url": "https://www.arome.jp/products/detail.php?product_id=8286",
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
        "url": "https://beervolta.com/view/item/000000007629",
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
        "url": "https://beervolta.com/view/item/000000007628",
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
]

# Untappd未登録ビールのステータス更新 (調査済みマーク付与)
UNREGISTERED_BEER_ITEMS = [
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8293",
        "notes": "ワイマーケット / ルプリンネクター∀ (Hazy IPA) 370ml缶 - Untappd未登録"
    },
    {
        "url": "https://151l.shop/?pid=193631430",
        "notes": "ファーメンタリー お茶！大和 (FARMENTRY OCHA! YAMATO) - Untappd未登録"
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000001789",
        "notes": "ちょうせいや LUPLIN NECTAR ∀ /Yマーケット - Untappd未登録"
    }
]

# 2. ローリング巡回・Untappd データの最新化対象
BEER_REFRESH_URLS = [
    "https://untappd.com/b/3-sons-brewing-co-coco-logic/6631064",
    "https://untappd.com/b/parrotdog-thunderbird-bright-ipa/5740517",
    "https://untappd.com/b/founders-brewing-co-all-day-tropics/6612106",
    "https://untappd.com/b/founders-brewing-co-all-day-west-coast/5219198"
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

    # 1. 新規エンリッチ & 未紐付け特定 (23件)
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

        # untappd_data scrape & upsert
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

    # 2. Untappd未登録商品の処理
    if UNREGISTERED_BEER_ITEMS:
        logger.info(f"\n[2] Updating {len(UNREGISTERED_BEER_ITEMS)} unregistered beer items (marking surveyed)...")
        for item in UNREGISTERED_BEER_ITEMS:
            url = item["url"]
            run_db_op(lambda: sync_execute(sb.table("scraped_beers").update({
                "untappd_url": None,
                "untappd_enriched_at": now_iso
            }).eq("url", url)))
            logger.info(f"  ✅ Marked surveyed (not on Untappd): {url} ({item['notes']})")

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
