import re
import logging
from typing import Optional, Dict, Any, List
from ...core.db import get_supabase_client
from ...core.types import GeminiExtraction

logger = logging.getLogger(__name__)

class LocalCacheResolver:
    def __init__(self) -> None:
        self.brewery_dict: Dict[str, Dict[str, Any]] = {}
        try:
            self.supabase = get_supabase_client()
            self._load_brewery_dictionary()
        except Exception as e:
            logger.warning(f"Could not initialize Supabase client for cache resolver: {e}")
            self.supabase = None

    def _load_brewery_dictionary(self) -> None:
        """データベースからブルワリー辞書をメモリにロードする"""
        if not self.supabase:
            return
        try:
            res = self.supabase.table("breweries").select("id, name_en, name_jp, aliases, untappd_url").execute()
            if res.data:
                for row in res.data:
                    keys = []
                    if row.get("name_en"):
                        keys.append(row["name_en"].lower())
                        # "Brewing" などの一般的なサフィックスを除外したキーも登録
                        cleaned_en = re.sub(r'\b(brewing|brewery|beer|co)\b', '', row["name_en"].lower()).strip()
                        if cleaned_en:
                            keys.append(cleaned_en)
                    if row.get("name_jp"):
                        keys.append(row["name_jp"].lower())
                    if row.get("aliases"):
                        for alias in row["aliases"]:
                            keys.append(alias.lower())

                    for key in set(keys):
                        self.brewery_dict[key] = row
                logger.info(f"💾 Loaded {len(res.data)} breweries ({len(self.brewery_dict)} search keys) for local cache.")
        except Exception as e:
            logger.error(f"Failed to load brewery dictionary for cache: {e}")

    async def resolve_tier1_exact_match(self, product_name: str) -> Optional[GeminiExtraction]:
        """Tier 1: 商品名の完全一致キャッシュを検索"""
        try:
            # 1. Get URLs with the exact matching name
            res = self.supabase.table("scraped_beers").select("url").eq("name", product_name).execute()
            if not res.data:
                return None
            
            urls = [row["url"] for row in res.data if row.get("url")]
            if not urls:
                return None
            
            # 2. Find resolved gemini_data for those URLs
            res_gemini = self.supabase.table("gemini_data") \
                .select("*") \
                .in_("url", urls) \
                .not_.is_("brewery_name_en", "null") \
                .limit(1) \
                .execute()
            
            if res_gemini.data and len(res_gemini.data) > 0:
                gemini_data = res_gemini.data[0]
                raw_payload = gemini_data.get("payload")
                payload = {}
                if raw_payload:
                    if isinstance(raw_payload, str):
                        try:
                            import json
                            payload = json.loads(raw_payload)
                        except Exception:
                            payload = {}
                    elif isinstance(raw_payload, dict):
                        payload = raw_payload
                
                logger.info(f"  ⚡ [Cache Tier 1] Exact match found for '{product_name}'")
                return {
                    "brewery_name_jp": gemini_data.get("brewery_name_jp"),
                    "brewery_name_en": gemini_data.get("brewery_name_en"),
                    "beer_name_jp": gemini_data.get("beer_name_jp"),
                    "beer_name_en": gemini_data.get("beer_name_en"),
                    "beer_name_core": payload.get("beer_name_core") or gemini_data.get("beer_name_en") or "",
                    "search_hint": payload.get("search_hint") or f"{gemini_data.get('beer_name_en')} {gemini_data.get('brewery_name_en')}",
                    "product_type": gemini_data.get("product_type", "beer"),
                    "is_set": gemini_data.get("is_set", False),
                    "raw_response": f"RESOLVED_BY_TIER1_EXACT_MATCH: {gemini_data.get('url')}"
                }
        except Exception as e:
            logger.warning(f"Error in Tier 1 cache resolution: {e}")
        return None

    async def resolve_tier2_dictionary_match(self, product_name: str, shop: Optional[str]) -> Optional[GeminiExtraction]:
        """Tier 2: ショップ特有のルール分割 ＋ ブルワリー辞書マッチ"""
        if not shop or not self.brewery_dict:
            return None

        brewery_part = ""
        beer_part = ""

        try:
            # 各ショップ特有の切り出しパターン
            if shop == "ちょうせいや":
                # STRICTフォーマット: 【Beer Name / Brewery Name】
                match = re.search(r'【([^/]+)/([^】]+)】', product_name)
                if match:
                    beer_part = match.group(1).strip()
                    brewery_part = match.group(2).strip()
            elif shop == "アローム":
                # 典型的なフォーマット: Jp Brewery / Jp Beer [En Brewery / En Beer]
                match = re.search(r'\[([^/]+)/([^\]]+)\]', product_name)
                if match:
                    brewery_part = match.group(1).strip()
                    beer_part = match.group(2).strip()
            elif shop == "BEER VOLTA":
                # NEW format: Jp Brewery : Jp Beer | En Brewery: En Beer
                if "|" in product_name:
                    parts = product_name.split("|")
                    english_part = parts[1] if len(parts) > 1 else ""
                    if ":" in english_part:
                        b, b_name = english_part.split(":", 1)
                        brewery_part = b.strip()
                        beer_part = b_name.strip()
            
            # 分割できた場合、ブルワリーが既知かチェック
            if brewery_part and beer_part:
                # 入荷予定などの不要テキストやセール文字列を除去
                beer_part = re.sub(r'[≪《<＜【\[].*?(?:入荷|予約|予定|出荷|空輸|クール|SALE|売切|新着).*?[≫》>＞\]】]', '', beer_part, flags=re.IGNORECASE).strip()
                for ind in ['≪入荷予定≫', '《入荷予定》', '≪予約≫', '《予約》', '売切', 'SOLD OUT', 'SALE!!', 'SALE!']:
                    beer_part = re.sub(re.escape(ind), '', beer_part, flags=re.IGNORECASE).strip()
                beer_part = re.sub(r'\s+', ' ', beer_part).strip()

                brewery_key = brewery_part.lower()
                if brewery_key in self.brewery_dict:
                    brewery_info = self.brewery_dict[brewery_key]
                    
                    # コア名の簡易処理（容量やスタイル表示の削除）
                    beer_core = re.sub(
                        r'\b(330ml|350ml|355ml|440ml|500ml|缶|瓶|can|bottle|ipa|stout|pale ale|neipa|dipa)\b', 
                        '', beer_part, flags=re.IGNORECASE
                    ).strip()
                    beer_core = ' '.join(beer_core.split())
                    
                    logger.info(f"  ⚡ [Cache Tier 2] Dictionary match found for '{product_name}' (Shop: {shop}, Brewery: {brewery_info.get('name_en')})")
                    return {
                        "brewery_name_jp": brewery_info.get("name_jp") or brewery_part,
                        "brewery_name_en": brewery_info.get("name_en") or brewery_part,
                        "beer_name_jp": beer_part,
                        "beer_name_en": beer_part,
                        "beer_name_core": beer_core or beer_part,
                        "search_hint": f"{beer_core or beer_part} {brewery_info.get('name_en')}",
                        "product_type": "beer",
                        "is_set": False,
                        "raw_response": f"RESOLVED_BY_TIER2_DICTIONARY_MATCH: {brewery_info.get('name_en')}"
                    }
        except Exception as e:
            logger.warning(f"Error in Tier 2 cache resolution: {e}")
        return None
