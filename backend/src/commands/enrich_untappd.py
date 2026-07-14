"""
Untappd-only enrichment command.
Enriches beers with Untappd data.
Modes:
- missing: Finds Untappd URLs for beers that don't have one.
- refresh: Updates details (rating, ABV, etc.) for beers that already have a URL.
"""
import asyncio
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any, Set

from backend.src.core.db import get_supabase_client, refresh_materialized_view
from backend.src.core.types import UntappdBeerDetails, UntappdSearchResult
from backend.src.services.untappd.searcher import get_untappd_url, scrape_beer_details, search_brewery_beer
from backend.src.services.untappd.validators import validate_beer_match, score_beer_match
from backend.src.services.gemini.extractor import GeminiExtractor
from backend.src.services.store.brewery_manager import BreweryManager
from backend.src.commands.failure_tracker import record_enrichment_failure, resolve_search_failure
from backend.src.core.utils import map_details_to_payload
from backend.src.services.untappd.db_queries import (
    fetch_beers,
    prefetch_gemini_untappd_urls,
    upsert_untappd_data,
    update_gemini_data_untappd_urls,
    update_scraped_beers_untappd_urls
)

logger: logging.Logger = logging.getLogger(__name__)


class UntappdEnricher:
    """Encapsulates the Untappd enrichment process and its state."""
    
    def __init__(
        self,
        mode: str = 'missing',
        shop_filter: Optional[str] = None,
        name_filter: Optional[str] = None,
        offline: bool = False,
        force: bool = False
    ):
        self.mode = mode
        self.shop_filter = shop_filter
        self.name_filter = name_filter
        self.offline = offline
        self.force = force
        self.supabase: Any = get_supabase_client()
        
        self.brewery_manager: Optional[BreweryManager] = None
        self.extractor: Optional[GeminiExtractor] = None
        
        if self.mode == 'missing':
            try:
                self.brewery_manager = BreweryManager()
                logger.info(f"  🏢 BreweryManager loaded ({len(self.brewery_manager.brewery_index)} breweries)")
            except Exception as e:
                logger.warning(f"  ⚠️  BreweryManager unavailable: {e}")

            try:
                self.extractor = GeminiExtractor()
                logger.info(f"  🤖 GeminiExtractor loaded (for Two-pass retry)")
            except Exception as e:
                logger.warning(f"  ⚠️  GeminiExtractor unavailable: {e}")

        self.gemini_cache: Dict[str, str] = {}
        self.untappd_cache: Dict[str, Dict[str, Any]] = {}
        self.processed_this_run: Set[str] = set()
        
        self.total_processed: int = 0
        self.total_success: int = 0
        self.collected_brewery_urls: Set[str] = set()
        self.skip_urls_for_backoff: Set[str] = set()

    async def run(self, limit: int = 50) -> Set[str]:
        """Runs the enrichment pipeline up to the specified limit."""
        logger.info("=" * 70)
        logger.info(f"🍺 Untappd Enrichment (Mode: {self.mode.upper()})")
        if self.shop_filter:
            logger.info(f"🏪 Shop Filter: {self.shop_filter}")
        if self.name_filter:
            logger.info(f"🔍 Name Filter: {self.name_filter}")
        logger.info("=" * 70)
        logger.info(f"Batch size: {limit}")

        if self.mode == 'missing':
            self._preload_failure_history()

        offset: int = 0
        db_fetch_limit: int = 200

        while True:
            beers: List[Dict[str, Any]] = self._fetch_beers(offset, db_fetch_limit)
            offset += db_fetch_limit
            
            # Remove already processed
            beers = [b for b in beers if b.get('url') not in self.processed_this_run]

            remaining_capacity: int = limit - self.total_processed
            beers_to_process: List[Dict[str, Any]] = beers[:remaining_capacity]

            logger.info(f"  Valid {len(beers_to_process)} beers to process in this batch")
            if not beers_to_process:
                logger.info("\n✨ No more beers to process!")
                break

            self._prefetch_caches(beers_to_process)

            # Accumulating payloads
            batch_untappd = []
            batch_gemini = []
            batch_scraped = []

            sem = asyncio.Semaphore(3)
            
            async def _process_with_sem(i: int, beer: Dict[str, Any]) -> Optional[Dict[str, Any]]:
                async with sem:
                    product_url_loop: Optional[str] = beer.get('url')
                    if not product_url_loop:
                        return None
                    self.processed_this_run.add(product_url_loop)

                    name_display: str = beer.get('name', beer.get('beer_name', 'Unknown'))
                    logger.info(f"[Batch {i}/{len(beers_to_process)} | Total {self.total_processed + i}] Processing: {name_display[:60]}")

                    result: Optional[Dict[str, Any]] = None
                    if self.mode in ('missing', 'retry-failures'):
                        if beer.get('untappd_url') and '/search?' not in beer['untappd_url']:
                            result = await self._process_beer_refresh(beer)
                            if result and product_url_loop:
                                resolve_search_failure(self.supabase, product_url_loop)
                        else:
                            result = await self._process_beer_missing(beer)
                    elif self.mode == 'refresh':
                        result = await self._process_beer_refresh(beer)
                    
                    return result

            tasks = [_process_with_sem(i, beer) for i, beer in enumerate(beers_to_process, 1)]
            results = await asyncio.gather(*tasks)

            for result in results:
                if result:
                    self.total_success += 1
                    b_url = result.get('untappd_brewery_url')
                    if b_url:
                        self.collected_brewery_urls.add(b_url)
                    
                    if result.get('untappd_payload'):
                        batch_untappd.append(result['untappd_payload'])
                    if result.get('gemini_payload') and result['gemini_payload'].get('url'):
                        batch_gemini.append(result['gemini_payload'])
                    if result.get('scraped_payload') and result['scraped_payload'].get('url'):
                        batch_scraped.append(result['scraped_payload'])

            # Commit batch
            if batch_untappd or batch_gemini or batch_scraped:
                self._commit_updates_batch(batch_untappd, batch_gemini, batch_scraped)

            self.total_processed += len(beers_to_process)
            if self.total_processed >= limit:
                break

        logger.info(f"\n{'='*70}")
        logger.info("✨ Untappd enrichment completed!")
        logger.info(f"{'='*70}")

        if not self.offline:
            refresh_materialized_view(self.supabase, logger)

        return list(self.collected_brewery_urls)


    def _preload_failure_history(self) -> None:
        """Pre-loads failure records for backoff filtering."""
        if self.name_filter or self.force:
            logger.info("  ⏭️ Name filter or Force active: Skipping backoff policy so targeted items are processed.")
            return
        logger.info("  🔍 Pre-loading failure history for backoff filtering...")
        from dateutil import parser as dateutil_parser
        cutoff: datetime = datetime.now(timezone.utc) - timedelta(days=3)
        failure_res: Any = self.supabase.table('untappd_search_failures') \
            .select('product_url, search_attempts, last_failed_at') \
            .eq('resolved', False) \
            .execute()
            
        for f in (failure_res.data or []):
            attempts: int = f.get('search_attempts', 0)
            last_failed_str: Optional[str] = f.get('last_failed_at')
            p_url: str = f.get('product_url', '')
            if attempts >= 3:
                self.skip_urls_for_backoff.add(p_url)
            elif last_failed_str:
                try:
                    last_failed: datetime = dateutil_parser.parse(last_failed_str)
                    if last_failed > cutoff:
                        self.skip_urls_for_backoff.add(p_url)
                except Exception:
                    pass
        if self.skip_urls_for_backoff:
            logger.info(f"  ⏭️ {len(self.skip_urls_for_backoff)} URLs will be skipped due to backoff policy.")

    def _fetch_beers(self, offset: int, db_fetch_limit: int) -> List[Dict[str, Any]]:
        """Fetches candidates based on current mode."""
        return fetch_beers(
            self.supabase,
            self.mode,
            offset,
            db_fetch_limit,
            self.shop_filter,
            self.name_filter,
            self.skip_urls_for_backoff,
            self.force,
        )

    def _prefetch_caches(self, beers_to_process: List[Dict[str, Any]]) -> None:
        """Prefetch gemini and untappd data to prevent N+1 queries."""
        urls_to_process = [b.get('url') for b in beers_to_process if b.get('url')]
        
        if urls_to_process:
            self.gemini_cache.update(prefetch_gemini_untappd_urls(self.supabase, urls_to_process))
            try:
                sb_res = self.supabase.table('scraped_beers').select('url, untappd_url').in_('url', urls_to_process).not_.is_('untappd_url', 'null').execute()
                for item in (sb_res.data or []):
                    if item.get('untappd_url') and '/search?' not in item['untappd_url']:
                        if item['url'] not in self.gemini_cache or not self.gemini_cache[item['url']]:
                            self.gemini_cache[item['url']] = item['untappd_url']
            except Exception as e:
                logger.warning(f"  ⚠️ Failed to prefetch scraped_beers untappd_url cache: {e}")

        known_untappd_urls = []
        for b in beers_to_process:
            u_url = b.get('untappd_url')
            if u_url and '/search?' not in u_url:
                known_untappd_urls.append(u_url)
            else:
                g_url = self.gemini_cache.get(b.get('url'))
                if g_url and '/search?' not in g_url:
                    known_untappd_urls.append(g_url)

        if known_untappd_urls:
            try:
                untappd_res = self.supabase.table('untappd_data').select('untappd_url, untappd_brewery_url').in_('untappd_url', known_untappd_urls).execute()
                self.untappd_cache.update({item['untappd_url']: item for item in (untappd_res.data or [])})
            except Exception as e:
                logger.warning(f"  ⚠️ Failed to prefetch untappd_data cache: {e}")

    async def _process_beer_missing(self, beer: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a beer in 'missing' mode."""
        brewery: Optional[str] = beer.get('brewery_name_en') or beer.get('brewery_name_jp')
        beer_name: Optional[str] = beer.get('beer_name_en') or beer.get('beer_name_jp')
        product_type: Optional[str] = beer.get('product_type')
        url: Optional[str] = beer.get('url')

        if product_type and product_type != 'beer':
            logger.info(f"  ⏭️ Item is a {product_type}. Skipping Untappd.")
            return None

        # Check if brewery was mistakenly identified as the bottle shop name
        shop_names = {'choseiya', 'ちょうせいや', 'arome', 'アローム', 'beervolta', 'beer volta', 'maruho', 'maruho saketen', 'マルホ酒店', '151l', '一期一会～る', 'antenna america', 'アンテナアメリカ'}
        if brewery and brewery.strip().lower() in shop_names:
            logger.info(f"  🔧 Brewery identified as shop name ('{brewery}'). Attempting to infer true brewery from product name...")
            brewery = None

        if (not brewery or not beer_name) and ("【" in beer.get('name', '') and "】" in beer.get('name', '')):
            match: Optional[re.Match] = re.search(r'【(.*?)[/／](.*?)】', beer.get('name', ''))
            if match:
                p1, p2 = match.group(1).strip(), match.group(2).strip()
                if self.brewery_manager and self.brewery_manager.find_breweries_in_text(p2):
                    beer_name, brewery = p1, p2
                elif self.brewery_manager and self.brewery_manager.find_breweries_in_text(p1):
                    brewery, beer_name = p1, p2
                elif not brewery:
                    beer_name, brewery = p1, p2
                logger.info(f"  🔧 Parsed from title: {brewery} - {beer_name}")

        if not brewery and self.brewery_manager:
            found_list = self.brewery_manager.find_breweries_in_text(beer.get('name', ''))
            if found_list:
                brewery = found_list[0].get('name_en') or found_list[0].get('name_jp')
                logger.info(f"  🔧 Inferred brewery from product text: {brewery}")

        if not beer_name and beer.get('name'):
            beer_name = beer.get('name')
            logger.info(f"  🔧 Fallback beer_name to shop title: {beer_name}")

        if not brewery or not beer_name:
            logger.warning(f"  ⚠️  Missing brewery or beer name - skipping")
            return None

        try:
            brewery_url_hint: Optional[str] = self._get_brewery_url_hint(brewery, beer_name)
            untappd_url: Optional[str] = None

            if self.offline:
                logger.info(f"  🔍 [Offline] Searching DB for: {brewery} - {beer_name}")
                db_res: Any = self.supabase.table('untappd_data').select('untappd_url') \
                    .ilike('beer_name', beer_name) \
                    .ilike('brewery_name', f"%{brewery}%") \
                    .limit(1).execute()
                if db_res.data:
                    untappd_url = db_res.data[0]['untappd_url']
                    logger.info(f"  ✅ [Offline] Found in DB: {untappd_url}")
                else:
                    logger.info(f"  ⏭️  [Offline] Not found in DB. Skipping.")
                    return None
            else:
                untappd_url = await self._resolve_untappd_url(beer, brewery, beer_name, brewery_url_hint)

            if not untappd_url:
                return None

            scraped_updates: Dict[str, Any] = {'url': url, 'untappd_url': untappd_url}
            gemini_updates: Dict[str, Any] = {'url': url, 'untappd_url': untappd_url}

            logger.info(f"  ✅ Found URL: {untappd_url}")

            untappd_payload: Dict[str, Any] = {}
            if not self.offline:
                untappd_payload = await self._scrape_and_save_details(untappd_url, beer, brewery, beer_name)
                if untappd_payload:
                    untappd_payload['untappd_url'] = untappd_url

            if url and (untappd_payload.get('beer_name') or untappd_payload.get('untappd_rating') or self.offline):
                resolve_search_failure(self.supabase, url)

            brewery_url_to_return = untappd_payload.get('untappd_brewery_url')
            if not brewery_url_to_return and untappd_url in self.untappd_cache:
                brewery_url_to_return = self.untappd_cache[untappd_url].get('untappd_brewery_url')

            return {
                'untappd_payload': untappd_payload,
                'gemini_payload': gemini_updates,
                'scraped_payload': scraped_updates,
                'untappd_brewery_url': brewery_url_to_return
            }

        except Exception as e:
            logger.error(f"  ❌ Untappd search error: {e}")
            return None

    async def _process_beer_refresh(self, beer: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a beer in 'refresh' mode: re-scrape details for existing URLs."""
        untappd_url: Optional[str] = beer.get('untappd_url')
        if not untappd_url or "untappd.com/b/" not in untappd_url:
            logger.warning(f"  ⚠️  Invalid Untappd URL: {untappd_url}")
            return None

        logger.info(f"  🔄 Refreshing: {beer.get('beer_name', 'Unknown')} ({untappd_url})")

        try:
            await asyncio.sleep(2)
            details: UntappdBeerDetails = await scrape_beer_details(untappd_url)
            untappd_payload: Dict[str, Any]
            if details:
                untappd_payload = map_details_to_payload(details)
                untappd_payload['untappd_url'] = untappd_url
                logger.info(f"  ✅ Details updated: Rating {details.get('untappd_rating', 'N/A')}")
                if beer.get('url'):
                    resolve_search_failure(self.supabase, beer.get('url'))
                
                self.untappd_cache[untappd_url] = {
                    'untappd_url': untappd_url,
                    'untappd_brewery_url': details.get('untappd_brewery_url')
                }
                
                # Self-Healing Dictionary Feedback Loop
                if self.brewery_manager:
                    u_b_name = details.get('untappd_brewery_name')
                    u_b_url = details.get('untappd_brewery_url')
                    b_hint = beer.get('brewery_name_en') or beer.get('brewery_name_jp')
                    if u_b_name and b_hint:
                        self.brewery_manager.learn_brewery_alias(brewery_name_en=u_b_name, new_alias=b_hint, untappd_url=u_b_url)
            else:
                logger.warning(f"  ⚠️  Could not scrape details")
                untappd_payload = {'untappd_url': untappd_url, 'fetched_at': datetime.now(timezone.utc).isoformat()}
            
            return {
                'untappd_payload': untappd_payload,
                'gemini_payload': {},
                'scraped_payload': {},
                'untappd_brewery_url': untappd_payload.get('untappd_brewery_url')
            }
        except Exception as e:
            logger.error(f"  ❌ Refresh error: {e}")
            return None

    def _get_brewery_url_hint(self, brewery: str, beer_name: Optional[str] = None) -> Optional[str]:
        """Looks up the known Untappd brewery URL from BreweryManager."""
        if not self.brewery_manager or not brewery:
            return None
        try:
            b_info: Optional[Dict[str, Any]] = self.brewery_manager.brewery_index.get(brewery.lower())
            if not b_info:
                found_list = self.brewery_manager.find_breweries_in_text(brewery)
                if found_list:
                    b_info = found_list[0]
            if not b_info and beer_name:
                found_list = self.brewery_manager.find_breweries_in_text(beer_name)
                if found_list:
                    b_info = found_list[0]
            if b_info:
                url: Optional[str] = b_info.get('untappd_url')
                if url:
                    logger.info(f"  🏢 Known brewery URL: {url} ({b_info.get('name_en')})")
                    return url
        except Exception as e:
            logger.warning(f"  ⚠️  BreweryManager lookup failed: {e}")
        return None

    def _validate_cached_url(self, cached_url: str, beer_name: str, brewery: str) -> bool:
        """Checks if a cached untappd_url actually matches the expected beer and brewery using score_beer_match."""
        try:
            if not self.supabase or self.offline or not cached_url or '/search?' in cached_url:
                return True
            res = self.supabase.table('untappd_data').select('beer_name, brewery_name, style').eq('untappd_url', cached_url).limit(1).execute()
            if not res.data:
                return True
            db_item = res.data[0]
            from bs4 import BeautifulSoup
            from backend.src.services.untappd.validators import score_beer_match
            html = f'<div class="beer-item"><p class="name"><a>{db_item.get("beer_name", "")}</a></p><p class="brewery"><a>{db_item.get("brewery_name", "")}</a></p><p class="style">{db_item.get("style", "")}</p></div>'
            soup = BeautifulSoup(html, 'lxml')
            item = soup.select_one('.beer-item')
            score = score_beer_match(item, beer_name, brewery)
            if score == 0:
                return False
            return True
        except Exception as e:
            logger.debug(f"  [Validation] Cached URL check error: {e}")
            return True

    async def _resolve_untappd_url(
        self,
        beer: Dict[str, Any],
        brewery: str,
        beer_name: str,
        brewery_url_hint: Optional[str],
    ) -> Optional[str]:
        """Core URL resolution logic."""
        untappd_url: Optional[str] = beer.get('untappd_url')
        url: Optional[str] = beer.get('url')

        # 1. Check persistence in gemini_cache
        if not untappd_url and url:
            p_url = self.gemini_cache.get(url)
            if p_url and '/search?' not in p_url:
                if self._validate_cached_url(p_url, beer_name, brewery):
                    logger.info(f"  ✅ [Persistence] Found link in gemini_cache: {p_url}")
                    return p_url
                else:
                    logger.warning(f"  ⚠️ [Persistence] Invalid/mismatched link in gemini_cache ({p_url}) for '{beer_name}'. Ignoring cache!")
                    self.gemini_cache[url] = None
                    try:
                        if self.supabase and not self.offline:
                            self.supabase.table('gemini_data').update({'untappd_url': None}).eq('url', url).execute()
                    except Exception as e:
                        logger.debug(f"  ⚠️ Could not null gemini_data untappd_url: {e}")

        if untappd_url and '/search?' not in untappd_url:
            if self._validate_cached_url(untappd_url, beer_name, brewery):
                return untappd_url
            else:
                logger.warning(f"  ⚠️ [Persistence] Invalid/mismatched existing untappd_url ({untappd_url}) for '{beer_name}'. Ignoring!")

        # 2. Search Untappd
        beer_name_jp: Optional[str] = beer.get('beer_name_jp')
        search_hint: Optional[str] = beer.get('search_hint')
        beer_name_core: Optional[str] = beer.get('beer_name_core')

        logger.info(f"  🔍 Searching Untappd for: {brewery} - {beer_name}")
        search_result: UntappdSearchResult = await get_untappd_url(
            brewery, beer_name,
            beer_name_jp=beer_name_jp,
            brewery_url=brewery_url_hint,
            search_hint=search_hint,
            beer_name_core=beer_name_core
        )

        # 3. Two-pass retry & inference when no_results
        if not search_result.get('success') and search_result.get('failure_reason') == 'no_results' and self.extractor:
            # Phase A: Gemini structured English translation & slug inference + self-healing learning loop
            logger.info(f"  🤖 [Phase A] Asking Gemini to infer English brewery & slug for self-healing loop...")
            try:
                full_name: str = beer.get('name', '')
                inferred = await self.extractor.infer_untappd_brewery_info(
                    product_name=full_name,
                    brewery=brewery,
                    beer_name=beer_name
                )
                if inferred:
                    eb_name = inferred.get("english_brewery_name", "")
                    b_slug = inferred.get("brewery_slug", "")
                    eb_beer = inferred.get("english_beer_name", "")
                    
                    candidate_brewery_urls = []
                    if b_slug:
                        candidate_brewery_urls.append(f"https://untappd.com/w/{b_slug}")
                    
                    for c_b_url in candidate_brewery_urls:
                        logger.info(f"  🔍 [Phase A] Testing inferred brewery slug: {c_b_url}")
                        b_found = await search_brewery_beer(
                            c_b_url,
                            eb_beer or beer_name,
                            validate_beer_fn=validate_beer_match,
                            validate_beer=(eb_beer or beer_name),
                            score_beer_fn=score_beer_match,
                            validate_brewery=(eb_name or brewery)
                        )
                        if b_found:
                            logger.info(f"  🎉 [Phase A] Found via inferred slug! {b_found}")
                            if self.brewery_manager and eb_name and brewery:
                                self.brewery_manager.learn_brewery_alias(brewery_name_en=eb_name, new_alias=brewery, untappd_url=c_b_url)
                            return b_found
                        await asyncio.sleep(1)

                    if eb_name and eb_beer:
                        logger.info(f"  🔍 [Phase A] Trying get_untappd_url with inferred English names: {eb_name} - {eb_beer}")
                        inf_result: UntappdSearchResult = await get_untappd_url(
                            brewery_name=eb_name,
                            beer_name=eb_beer,
                            search_hint=f"{eb_name} {eb_beer}"
                        )
                        if inf_result.get('success') and inf_result.get('url'):
                            logger.info(f"  🎉 [Phase A] Found via inferred English names: {inf_result.get('url')}")
                            if self.brewery_manager and eb_name and brewery:
                                self.brewery_manager.learn_brewery_alias(brewery_name_en=eb_name, new_alias=brewery)
                            return inf_result.get('url')
                        await asyncio.sleep(1)
            except Exception as inf_e:
                logger.warning(f"  ⚠️ [Phase A] Gemini inference failed: {inf_e}")

            # Phase B: Two-pass retry queries
            logger.info(f"  🔄 [Phase B] Asking Gemini for alternative queries...")
            try:
                full_name: str = beer.get('name', '')
                alt_queries: List[str] = await self.extractor.suggest_search_queries(
                    product_name=full_name,
                    brewery=brewery,
                    beer_name=beer_name
                )
                for alt_query in alt_queries:
                    logger.info(f"  🔍 [Phase B] Trying: '{alt_query}'")
                    retry_result: UntappdSearchResult = await get_untappd_url(
                        brewery_name=brewery,
                        beer_name=beer_name,
                        search_hint=alt_query,
                        beer_name_core=beer_name_core
                    )
                    if retry_result.get('success'):
                        logger.info(f"  ✅ [Phase B] Found: {retry_result.get('url')}")
                        return retry_result.get('url')
                    await asyncio.sleep(1)
            except Exception as e:
                logger.warning(f"  ⚠️ [Phase B] Gemini retry failed: {e}")

        # Record failure
        if not search_result.get('success'):
            if url:
                record_enrichment_failure(
                    self.supabase,
                    product_url=url,
                    brewery_name=brewery,
                    beer_name=beer_name,
                    beer_name_jp=beer_name_jp,
                    failure_reason=search_result.get('failure_reason', 'unknown'),
                    error_message=search_result.get('error_message') or "Unknown error"
                )
            if search_result.get('failure_reason') == 'no_results':
                logger.info(f"  ⏭️  No direct link found. Failure recorded.")
                return None

        return search_result.get('url')

    async def _scrape_and_save_details(
        self,
        untappd_url: str, 
        beer: Dict[str, Any], 
        brewery: str, 
        beer_name: str,
    ) -> Dict[str, Any]:
        """Scrapes beer details and returns untappd_payload. Returns {} if nothing to save."""
        url: str = beer.get('url', '')

        # Check if details already exist in local cache
        if untappd_url in self.untappd_cache:
            logger.info(f"  💾 Data already exists in untappd_cache. Linking only.")
            return {}

        if "untappd.com/b/" not in untappd_url:
            return {}

        await asyncio.sleep(2)  # Rate limiting
        logger.info(f"  🔄 Scraping beer details...")
        details: UntappdBeerDetails = await scrape_beer_details(untappd_url)
        if details:
            payload: Dict[str, Any] = map_details_to_payload(details)
            payload['untappd_url'] = untappd_url
            logger.info(f"  ✅ Details scraped: {details.get('untappd_style', 'N/A')}")
            
            # Add to local cache for subsequent items in this batch
            self.untappd_cache[untappd_url] = {
                'untappd_url': untappd_url,
                'untappd_brewery_url': details.get('untappd_brewery_url')
            }
            
            # Self-Healing Dictionary Feedback Loop
            if self.brewery_manager:
                u_b_name = details.get('untappd_brewery_name')
                u_b_url = details.get('untappd_brewery_url')
                if u_b_name and brewery:
                    self.brewery_manager.learn_brewery_alias(brewery_name_en=u_b_name, new_alias=brewery, untappd_url=u_b_url)
                    
            return payload
        else:
            logger.warning(f"  ⚠️  Could not scrape details")
            if url:
                record_enrichment_failure(
                    self.supabase,
                    product_url=url,
                    brewery_name=brewery,
                    beer_name=beer_name,
                    failure_reason='untappd_scrape_error',
                    error_message="Failed to scrape details from Untappd page."
                )
            return {'untappd_url': untappd_url, 'fetched_at': datetime.now(timezone.utc).isoformat()}

    def _commit_updates_batch(
        self,
        untappd_payloads: List[Dict[str, Any]],
        gemini_updates: List[Dict[str, Any]],
        scraped_updates: List[Dict[str, Any]],
    ) -> None:
        """Commits all accumulated updates to the database in batch."""
        upsert_untappd_data(self.supabase, untappd_payloads)
        update_gemini_data_untappd_urls(self.supabase, gemini_updates)
        update_scraped_beers_untappd_urls(self.supabase, scraped_updates)


# ── Main entry point ──────────────────────────────────────────────────────────

async def enrich_untappd(
    limit: int = 50,
    mode: str = 'missing',
    shop_filter: Optional[str] = None,
    name_filter: Optional[str] = None,
    offline: bool = False,
    force: bool = False,
) -> Set[str]:
    """
    Entry point: Enrich beers with Untappd data.
    """
    enricher = UntappdEnricher(
        mode=mode,
        shop_filter=shop_filter,
        name_filter=name_filter,
        offline=offline,
        force=force
    )
    return await enricher.run(limit=limit)
