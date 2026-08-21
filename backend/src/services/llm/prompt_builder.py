import os
import json
import logging
import re
from typing import Optional, Dict, Any, List, Tuple, cast
from ...core.types import GeminiExtraction

logger = logging.getLogger(__name__)

class PromptBuilder:
    """
    Encapsulates all logic for generating LLM prompts, parsing configurations, and enforcing formatting rules.
    
    ====================================================================================================
    SHOP-BY-SHOP TITLE FORMAT PATTERNS & EXTRACTION RULES (ショップ別表記パターン整理)
    ====================================================================================================
    1. Antenna America (アンテナアメリカ):
       Format: `{English Brewery} {English Beer} ({Volume}) / {Japanese Katakana} 【{Shipping Date}】`
       Example: `Lagunitas IPA (355ml) / ラグニタス IPA`, `Stone Go To IPA / ストーン ゴートゥー IPA`
       Notes: Portion BEFORE slash `/` has English Brewery + English Beer. Remove volume in parentheses `(355ml)`.
              Ignore shipping notes `【7/2出荷】`.

    2. Arôme (アローム):
       Format: `(空輸) {Japanese Brewery} / {Japanese Beer} ({Style}) {Volume}{Can/Bottle} [{English Brewery} / {English Beer}]`
       Example: `(空輸) ロアーブルーイング / エターナル・プランクスター (Hazy Double IPA) 473ml缶 [RaR Brewing / Eternal Prankster]`
       Notes: Square brackets `[...]` at the end contain exact English Brewery `/` English Beer.
              Prioritize extracting from `[...]`. Strip shipping `(空輸)` and volume `473ml缶`.

    3. BEER VOLTA (ビール ヴォルタ):
       Format 1 (NEW): `{Japanese Brewery} : {Japanese Beer} | {English Brewery}: {English Beer} {Volume}`
       Format 2 (OLD): `{Japanese Name} / {English Brewery} {English Beer} [Volume]`
       Example: `バテレ : ネモフィラ | VERTERE: Nemophila 350ml`, `トートピア : スピンフォビア | Totopia: Spinphobia`
       Notes: Pipe `|` separates Japanese & English. Colon `:` separates Brewery & Beer.
              Extract from English portion after `|`. MUST remove volume `350ml`, `568ml`.

    4. Maruho (マルホ酒店):
       Format: `{English Beer Name} {Volume|Collab Info}/{English Brewery Name}`
       Example: `Lion 473ml/Lolev Beer`, `Fir Mountain (collabo w Orebro) 375ml/Brekeriet`
       Notes: REVERSED ORDER: Portion BEFORE `/` is Beer Name (+ Volume), portion AFTER `/` is Brewery.
              Strip volume `473ml`, `375ml` from beer name.

    5. Chouseiya (ちょうせいや):
       Format: `{Discount}【{Beer Name}/{Brewery Name}({Expiration})】`
       Example: `【犬吠BLACK IPA/銚子ビール】`, `30%OFF【Pyotr/CRAFT BEER BASE(賞味期限/2026.07.28)】`
       Notes: REVERSED ORDER inside `【...】`: Text BEFORE `/` is Beer Name, text AFTER `/` is Brewery.
              Ignore discounts `30%OFF` and expiration notes `(賞味期限/...)`.

    6. Ichigo Ichie (一期一会～る):
       Format: `【{Arrival Date}】{Japanese Brewery} {Japanese Beer} ({English Brewery} {English Beer})`
       Example: `【7/29入荷予定】アドロイトセオリー オートアコースティックエミッションズ 空輸（Adroit Theory Otoacoustic Emissions）`
       Notes: Parentheses `(...)` contain English Brewery + Beer. Split brewery from beer name carefully.
    ====================================================================================================
    """
    
    def __init__(self) -> None:
        self.shop_rules: Dict[str, Any] = self._load_shop_rules()

    def _load_shop_rules(self) -> Dict[str, Any]:
        """Loads shop-specific rules from JSON file."""
        try:
            json_path: str = os.path.join(os.path.dirname(__file__), "shop_rules.json")
            if os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    return cast(Dict[str, Any], json.load(f))
            logger.warning(f"Shop rules file not found: {json_path}")
        except Exception as e:
            logger.error(f"Failed to load shop rules: {e}")
        return {}

    def get_shop_guidance(self, shop: Optional[str]) -> Tuple[str, str]:
        """Provides specific formatting rules and examples based on the shop."""
        guidance: str = ""
        examples: str = ""

        if shop and self.shop_rules:
            target: Optional[Dict[str, Any]] = self.shop_rules.get(shop)
            if not target:
                shop_lower = shop.lower()
                for k, v in self.shop_rules.items():
                    if k.lower() == shop_lower:
                        target = v
                        break
            if target:
                guidance = target.get("rule", "")
                examples = target.get("examples", "")

        return guidance, examples

    def clean_product_title(self, title: str, shop: Optional[str] = None) -> str:
        """Removes common shop-specific noise from the title before sending to LLM."""
        if not title:
            return ""
        
        # 1. 【】や《》や[]で囲まれた注意事項（予定、出荷、入荷、ご注文、本以上、クール便、限定、予約、空輸、冷蔵、常温、おひとり様、必須、同時購入、推しなど）を削除
        noise_keywords = r'予定|出荷|入荷|ご注文|本以上|合計|セット|限定|条件|注意|必須|おひとり様|同時購入|推し|対象|配送|発送|即納|ポイント|送料無料|クール便|予約|空輸|冷蔵|常温'
        bracket_patterns = [
            r'【[^】]*?(?:' + noise_keywords + r')[^】]*?】',
            r'《[^》]*?(?:' + noise_keywords + r')[^》]*?》',
            r'≪[^≫]*?(?:' + noise_keywords + r')[^≫]*?≫',
            r'\[[^\]]*?(?:' + noise_keywords + r')[^\]]*?\]',
            r'<[^>]*?(?:' + noise_keywords + r')[^>]*?>',
            r'＜[^＞]*?(?:' + noise_keywords + r')[^＞]*?＞',
        ]
        for pat in bracket_patterns:
            title = re.sub(pat, '', title, flags=re.IGNORECASE)

        # 2. 丸括弧付きの単独発送表記 (空輸), (冷蔵), (常温), (空輸便) などの削除
        title = re.sub(r'[\(（](?:空輸|冷蔵|常温|クール便|空輸便)[\)）]', '', title)

        # 3. 割引情報 (例: 30%OFF, 50% OFF) や 賞味期限表記 (例: (賞味期限/2026.07.08), 【賞味期限:2026/07/08】) の削除
        title = re.sub(r'\b\d+%\s*OFF\b', '', title, flags=re.IGNORECASE)
        title = re.sub(r'[\(（【]?賞味期限[/：:][^\)）】]+[\)）】]?', '', title)
        
        return title.strip()

    def apply_set_override(self, res: GeminiExtraction, original_title: str) -> GeminiExtraction:
        """Deterministic override: If title explicitly mentions set keywords, enforce set status."""
        set_pattern = re.compile(r'(\d+本(?:パック|セット|アソート|飲み比べ)|\d+\s*Cans?\s*(?:Set|Pack)|\d+\s*Bottles?\s*(?:Set|Pack)|飲み比べ|アソート|お試しセット|本セット|缶セット|Variety\s*Pack)', re.IGNORECASE)
        if set_pattern.search(original_title):
            if not res.get("is_set") or res.get("product_type") != "set":
                logger.info(f"  🔧 Enforcing SET classification due to explicit keywords in title: '{original_title}'")
                res["is_set"] = True
                res["product_type"] = "set"
        return self.apply_product_type_override(res, original_title)

    def apply_product_type_override(self, res: GeminiExtraction, original_title: str) -> GeminiExtraction:
        """Corrects false 'other' classifications when valid brewery/beer info or beverage indicators exist."""
        non_beverage_pattern = re.compile(
            r'(書籍|本|著者|出版|雑誌|ZINE|ガイドライン|テイスティングノート|解体新書|Tシャツ|トートバッグ|グラス|ステッカー|コースター|キーホルダー|服飾|新書|単行本)',
            re.IGNORECASE
        )
        # If title clearly indicates a non-beverage item, preserve "other" or "glass"
        if non_beverage_pattern.search(original_title):
            return res

        curr_type = res.get("product_type", "beer")
        if curr_type == "other":
            # If valid brewery or beer name was extracted, or title doesn't match non-beverage
            b_en = res.get("brewery_name_en") or ""
            b_jp = res.get("brewery_name_jp") or ""
            beer_en = res.get("beer_name_en") or ""
            beer_jp = res.get("beer_name_jp") or ""

            # Check if any valid name exists or title looks like a beer/beverage
            if (b_en and b_en.lower() != "none") or (b_jp and b_jp.lower() != "none") or (beer_en and beer_en.lower() != "none") or (beer_jp and beer_jp.lower() != "none"):
                corrected_type = "set" if res.get("is_set") else "beer"
                logger.info(f"  🔧 Correcting product_type from 'other' to '{corrected_type}' for beverage item: '{original_title}'")
                res["product_type"] = corrected_type

        return res

    def empty_result(self) -> GeminiExtraction:
        """Returns a default empty result structure."""
        return {
            "brewery_name_jp": None,
            "brewery_name_en": None,
            "beer_name_jp": None,
            "beer_name_en": None,
            "beer_name_core": None,
            "search_hint": None,
            "product_type": "beer",
            "is_set": False,
            "raw_response": None
        }

    def build_extract_prompt(self, product_name: str, known_brewery: Optional[str] = None, shop: Optional[str] = None) -> str:
        """Constructs the full extraction prompt."""
        clean_name = self.clean_product_title(product_name, shop)
        brewery_hint: str = f"Note: The brewery exists and is likely: '{known_brewery}'" if known_brewery else ""
        guidance, examples = self.get_shop_guidance(shop)

        return f"""
        Extract brewery and beer names from the product title.
        Identify product type: "beer", "set", "glass", or "other".
        Product Title: "{clean_name}"
        {brewery_hint}
 
        Rules:
        - **Format**: Follow shop-specific formatting if provided below.
        {guidance}
        - **Volume / Size Removal**: ABSOLUTELY DO NOT include volume/capacity numbers (e.g. "355ml", "473ml", "568ml", "750ml", "330ml", "12oz", "500ml", "缶", "瓶") in `beer_name_en` or `beer_name_core`. Strip volume completely!
        - **Collab**: If multiple breweries are involved (×, &, /), include all (e.g., "A x B").
        - **Product Type**: "beer" (single can/bottle only), "set" (multi-can/bottle sets like "4 Cans Set", "4本セット", variety packs, tasting sets), "glass", "other".
        - **Product Type Classification**: ALL consumable craft beverages (beers, ciders, meads, hard kombuchas, hard seltzers, gin sodas) MUST be classified as "beer" (or "set" if multi-pack). ONLY classify non-beverage merchandise, books, magazines, t-shirts, tote bags, or glassware accessories as "other" or "glass"! Note: Brewery names like "Other Half" containing "Other" are breweries, NOT product type "other"!
        - **is_set**: MUST be `true` if the product contains multiple cans/bottles (e.g. "4 Cans Set", "4本セット", "飲み比べ", "アソート").
        - **brewery_name_jp**: Preserve the original Japanese brewery name as-is (e.g., "ヨロッコ", "家守堂").
        - **brewery_name_en**: Use the brewery's OFFICIAL English/romanized name if known (e.g., "Yorocco Beer" for ヨロッコ, "Yamorido" for 家守堂). For Japanese-only breweries, use phonetic romanization (NOT semantic translation). WRONG: "Root + Branch Brewing" for ヨロッコ. RIGHT: "Yorocco Beer".
        - **beer_name_core**: The essential/searchable part of the beer name. Remove edition qualifiers ("Nth Anniversary", "Special Edition", "Limited", "Reserve"), volume suffixes ("355ml", "568ml"), and beer style suffixes (IPA, Stout, NE IPA, etc.). Example: "The Realm's Remedy 11th Anniversary IPA" → "The Realm's Remedy". "Casimiroa NE IPA" → "Casimiroa".
        - **search_hint**: A short, optimized Untappd search query (max ~4 words). Format: "[beer_name_core] [brewery_name_en]". If the beer name is in Japanese (e.g. 金鬼, 其の十, 鬼伝説), ALWAYS include its romanized/phonetic reading (e.g. "Kin-oni", "Sono 10", "Oni Densetsu") in `search_hint` and `beer_name_en` so Untappd can find it!
        - **Spelling Accuracy**: Be exact with brewery names (e.g. "Tamamura Honten", NOT "Tamamuro"; "Wakasaimo Honpo", NOT "Wakasaimo").
 
        Output JSON:
        {{
          "brewery_name_jp": "...", "brewery_name_en": "...",
          "beer_name_jp": "...", "beer_name_en": "...",
          "beer_name_core": "...",
          "search_hint": "...",
          "product_type": "...", "is_set": boolean
        }}
 
        Examples:
        {examples if examples else '''1. "Beer Name / Brewery" -> {{"brewery_name_en": "Brewery", "beer_name_en": "Beer Name", "beer_name_core": "Beer Name", "search_hint": "Beer Name Brewery", "product_type": "beer", "is_set": false}}
2. "【カシミロア/バテレ】(VERTERE Casimiroa NE IPA)" -> {{"brewery_name_jp": "バテレ", "brewery_name_en": "VERTERE", "beer_name_en": "Casimiroa NE IPA", "beer_name_core": "Casimiroa", "search_hint": "Casimiroa VERTERE", "product_type": "beer", "is_set": false}}
3. "テスト : 4本セット | TEST: 4 Cans Set《7/16-17入荷予定》" -> {{"brewery_name_jp": null, "brewery_name_en": null, "beer_name_en": "TEST", "beer_name_core": "TEST", "search_hint": "TEST", "product_type": "set", "is_set": true}}'''}
        """

    def build_suggest_search_queries_prompt(self, product_name: str, brewery: str, beer_name: str) -> str:
        """Constructs the prompt for suggesting alternative search queries."""
        return f"""
        An Untappd search for a craft beer has failed. Suggest 3 short, alternative search queries to find it.
 
        Product Title: "{product_name}"
        Brewery: "{brewery}"
        Beer Name: "{beer_name}"
 
        Rules:
        - Each query should be short (2-5 words)
        - Try different combinations: core beer name, brewery abbreviation, key unique words
        - Remove edition qualifiers (Anniversary, Edition, Limited, etc.)
        - Remove beer style suffixes (IPA, Stout, Pale Ale, etc.) if the name has other unique words
        - The goal is to find the beer on Untappd.com
 
        Output JSON only:
        {{"queries": ["query1", "query2", "query3"]}}
        """

    def build_infer_untappd_brewery_info_prompt(self, product_name: str, brewery: str, beer_name: str) -> str:
        """Constructs the prompt for inferring English brewery info and slug."""
        return f"""
        An Untappd search for a craft beer failed because the Japanese/Katakana text does not match Untappd's English database.
        Please infer the exact official English brewery name, its likely URL slug on Untappd (e.g. 'finback-brewery' or 'ise-kado-brewery'), and the official English beer name.

        Product Title: "{product_name}"
        Brewery Text: "{brewery}"
        Beer Name Text: "{beer_name}"

        Rules:
        - Convert Katakana names to their official English names (e.g. 'フィンバック' -> 'Finback Brewery', 'アザーハーフ' -> 'Other Half Brewing Co.', '箕面ビール' -> 'Minoh Beer').
        - 'brewery_slug' must be lowercase with hyphens, matching standard Untappd slug conventions (e.g. 'other-half-brewing-co', 'minoh-beer').
        - 'english_beer_name' should remove Japanese edition tags and style suffixes if redundant, giving the clean core English name on Untappd.

        Output JSON only:
        {{
            "english_brewery_name": "...",
            "brewery_slug": "...",
            "english_beer_name": "..."
        }}
        """

    def build_select_best_candidate_prompt(self, product_name: str, brewery: str, beer_name: str, candidates: List[Dict[str, Any]]) -> str:
        """Constructs the prompt for selecting the best Untappd match among candidates."""
        candidates_str_list = []
        for idx, c in enumerate(candidates):
            b_name = c.get('beer_name', 'Unknown Beer')
            br_name = c.get('brewery_name', 'Unknown Brewery')
            st_name = c.get('style', '')
            url = c.get('url', '')
            candidates_str_list.append(f"[{idx}] Beer: '{b_name}' | Brewery: '{br_name}' | Style: '{st_name}' | URL: {url}")
        candidates_text = "\n".join(candidates_str_list)

        return f"""
        We searched Untappd for a craft beer but got multiple candidate results.
        Please choose the single best matching candidate from the list below, or return -1 if none of them accurately match the target product.

        Target Product Info:
        - Product Title (Original Shop Product Name): "{product_name}"
        - Expected Brewery: "{brewery}"
        - Expected Beer Name: "{beer_name}"

        Candidate Results from Untappd:
{candidates_text}

        Rules:
        1. **Strict Variant & Title Matching**: Pay very close attention to "Product Title (Original Shop Product Name)" above, which contains the raw shop listing title. If it specifies a specific variant, hop, adjunct, or edition (e.g., DDH, Double Dry Hopped, Barrel Aged / BA, TIPA, Hazy, w/ lemon or fruit, batch number, Specific Vintage Year like 2023 or 2024), the selected candidate MUST exactly match that variant or vintage. Do not pick the regular version or a different vintage year if the specific one is requested. If the requested exact variant/vintage is NOT in the candidate list, return -1 (no match).
        2. **Collab Matching**: If the target is a collaboration beer (e.g., A x B or mentioned in Product Title), candidate names might list the breweries in a different order (e.g., B / A) or include both names. This is a valid match.
        3. **Japanese to English Mapping**: The target product info may be in Japanese or Katakana. Match them correctly to their English/Romanized equivalents on Untappd.
        4. **No Match Option**: If none of the candidates accurately represent the target product, you MUST output selected_index as -1. Do not guess or force a wrong match.

        Output JSON only:
        {{
            "selected_index": 0,
            "reason": "Clear brief explanation for why this candidate was selected or why none matched."
        }}
        """
