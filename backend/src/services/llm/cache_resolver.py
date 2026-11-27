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
        if not product_name or not product_name.strip():
            return None
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
                .select("url, brewery_name_en, brewery_name_jp, beer_name_en, beer_name_jp, product_type, is_set, payload") \
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

    def _match_leading_brewery(self, text: str) -> Optional[tuple[str, str]]:
        """
        テキスト先頭から既知ブルワリー辞書に最長一致するブルワリー名を切り出す。
        誤分割防止のため、キー長3文字以上かつ直後が空白/区切り文字で、残りのビール名が空でない場合のみマッチさせる。
        """
        if not text or not self.brewery_dict:
            return None
        text_stripped = text.strip()
        text_lower = text_stripped.lower()
        # 最長一致を優先（例: "Other Half Brewing" を "Other" より先に評価）
        sorted_keys = sorted(
            (k for k in self.brewery_dict.keys() if len(k) >= 3),
            key=len,
            reverse=True,
        )
        for key in sorted_keys:
            if text_lower.startswith(key) and len(text_lower) > len(key):
                next_char = text_lower[len(key)]
                if next_char in (' ', '\t', '\u3000', ':', '-', '/'):
                    remainder = text_stripped[len(key):].lstrip(' \t\u3000:-/')
                    if remainder:
                        return key, remainder
        return None

    async def resolve_tier2_dictionary_match(self, product_name: str, shop: Optional[str]) -> Optional[GeminiExtraction]:
        """
        Tier 2: ショップ特有のルール分割 ＋ ブルワリー辞書マッチ。
        LLM API 呼び出しを回避しつつ、構造化されたショップタイトルから高精度にブルワリー・ビール名を抽出する。
        対応ショップ:
          - ちょうせいや / Chouseiya: 【Beer Name / Brewery Name】
          - アローム / Arôme: ... [En Brewery / En Beer]
          - BEER VOLTA / BeerVolta: Jp Brewery : Jp Beer | En Brewery: En Beer
          - マルホ酒店 / Maruho: En Beer [(collab ...)] 473ml/En Brewery（スラッシュ右側が本家ブルワリー）
          - Antenna America / アンテナアメリカ: En Brewery En Beer (473ml) / Katakana（先頭最長一致）
          - 一期一会～る / Ichigo Ichie: 日本語（En Brewery En Beer）（括弧内英語の先頭最長一致）
          - WITCH CRAFT MARKET: [Brewery Name] En Beer / Katakana
        """
        if not product_name or not product_name.strip():
            return None
        if not shop or not self.brewery_dict:
            return None

        brewery_part = ""
        beer_part = ""
        shop_norm = shop.strip()
        shop_lower = shop_norm.lower()

        try:
            # 各ショップ特有の切り出しパターン
            if shop_norm in ("ちょうせいや",) or shop_lower == "chouseiya":
                # STRICTフォーマット: 【Beer Name / Brewery Name】
                match = re.search(r'【(.*?)/(.*?)】', product_name)
                if match:
                    beer_part = match.group(1).strip()
                    brewery_part = match.group(2).strip()
                    # 賞味期限や付加情報の括弧を除去
                    brewery_part = re.sub(r'[\(（].*?[\)）]', '', brewery_part).strip()
            elif shop_norm in ("アローム", "Arôme") or shop_lower == "arome":
                # 典型的なフォーマット: Jp Brewery / Jp Beer [En Brewery / En Beer]
                match = re.search(r'\[([^/]+)/([^\]]+)\]', product_name)
                if match:
                    brewery_part = match.group(1).strip()
                    beer_part = match.group(2).strip()
            elif shop_lower in ("beer volta", "beervolta"):
                # NEW format: Jp Brewery : Jp Beer | En Brewery: En Beer
                if "|" in product_name:
                    parts = product_name.split("|")
                    english_part = parts[1] if len(parts) > 1 else ""
                    if ":" in english_part:
                        b, b_name = english_part.split(":", 1)
                        brewery_part = b.strip()
                        beer_part = b_name.strip()
            elif shop_norm in ("マルホ酒店",) or shop_lower == "maruho":
                # Format: English Beer Name [(collab w/...)] 473ml/Brewery Name
                # 意図: スラッシュ右側が必ず本家ブルワリーのため、コラボ表記があっても本家ブルワリーを正しく保持する
                match = re.match(r'^(.+?)\s+\d{3,4}\s*ml\s*[/／]\s*(.+)$', product_name.strip(), flags=re.IGNORECASE)
                if match:
                    beer_part = match.group(1).strip()
                    brewery_part = match.group(2).strip()
            elif shop_lower in ("antenna america", "アンテナアメリカ"):
                # Format: English Brewery English Beer (473ml) / Japanese Katakana 【出荷日】
                left_side = product_name.split('/', 1)[0].strip()
                left_side = re.sub(r'【[^】]*】', ' ', left_side)
                left_side = re.sub(r'[\(（]\s*\d{3,4}\s*ml\s*[\)）]', ' ', left_side, flags=re.IGNORECASE)
                left_side = re.sub(r'[\(（]\s*\d+(?:\.\d+)?\s*oz\s*[\)）]', ' ', left_side, flags=re.IGNORECASE)
                left_side = re.sub(r'\s+', ' ', left_side).strip()
                matched = self._match_leading_brewery(left_side)
                if matched:
                    brewery_part, beer_part = matched
            elif shop_norm in ("一期一会～る",) or shop_lower in ("ichigo ichie", "151l"):
                # Format: 【入荷予定】日本語ブルワリー 日本語ビール名（English Brewery English Beer）
                paren_matches = re.findall(r'[（(]([^）)]+)[）)]', product_name)
                for p_text in reversed(paren_matches):
                    if re.search(r'[A-Za-z]{2,}', p_text):
                        matched = self._match_leading_brewery(p_text)
                        if matched:
                            brewery_part, beer_part = matched
                            break
            elif shop_lower == "witch craft market":
                # Format: [Brewery Name] English Beer Name / Japanese Katakana
                match = re.match(r'^\[([^\]]+)\]\s*(.+)$', product_name.strip())
                if match:
                    b_cand = match.group(1).strip()
                    rest = match.group(2).strip()
                    if b_cand.lower() != "witch craft market":
                        brewery_part = b_cand
                        beer_part = rest.split('/', 1)[0].strip() if '/' in rest else rest
            
            # 分割できた場合、ブルワリーが既知かチェック
            if brewery_part and beer_part:
                # 入荷予定などの不要テキストやセール文字列を除去
                noise_keywords = r'入荷|予約|予定|出荷|空輸|クール|SALE|売切|新着|ご注文|本以上|合計|セット|限定|条件|注意|必須|おひとり様|同時購入|推し|対象|配送|発送|即納|ポイント|送料無料'
                bracket_patterns = [
                    r'【[^】]*?(?:' + noise_keywords + r')[^】]*?】',
                    r'《[^》]*?(?:' + noise_keywords + r')[^》]*?》',
                    r'≪[^≫]*?(?:' + noise_keywords + r')[^≫]*?≫',
                    r'\[[^\]]*?(?:' + noise_keywords + r')[^\]]*?\]',
                    r'<[^>]*?(?:' + noise_keywords + r')[^>]*?>',
                    r'＜[^＞]*?(?:' + noise_keywords + r')[^＞]*?＞',
                    r'\([^)]*?(?:' + noise_keywords + r')[^)]*?\)',
                    r'（[^）]*?(?:' + noise_keywords + r')[^）]*?）',
                ]
                for pat in bracket_patterns:
                    beer_part = re.sub(pat, '', beer_part, flags=re.IGNORECASE).strip()
                for ind in ['≪入荷予定≫', '《入荷予定》', '≪予約≫', '《予約》', '売切', 'SOLD OUT', 'SALE!!', 'SALE!']:
                    beer_part = re.sub(re.escape(ind), '', beer_part, flags=re.IGNORECASE).strip()
                # 容量・コラボ注記を beer_part / beer_core から整理
                beer_part = re.sub(r'\b\d{3,4}\s*ml\b', '', beer_part, flags=re.IGNORECASE).strip()
                beer_part = re.sub(r'\s+', ' ', beer_part).strip()

                brewery_key = brewery_part.lower()
                if brewery_key in self.brewery_dict:
                    brewery_info = self.brewery_dict[brewery_key]
                    
                    # コア名の簡易処理（コラボ注記・容量・スタイル表示の削除）
                    beer_core = re.sub(r'[\(（]\s*collabo?\b[^\)）]*[\)）]', '', beer_part, flags=re.IGNORECASE).strip()
                    beer_core = re.sub(r'\bw/\s*[^/\(\)]+$', '', beer_core, flags=re.IGNORECASE).strip()
                    beer_core = re.sub(
                        r'\b(330ml|350ml|355ml|375ml|440ml|473ml|500ml|568ml|650ml|750ml|缶|瓶|can|bottle|wc\s*ipa|ne\s*dipa|ne\s*ipa|hazy\s*ipa|ipa|dipa|tipa|neipa|stout|pale ale)\b', 
                        '', beer_core, flags=re.IGNORECASE
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
