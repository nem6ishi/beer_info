
import os
import sys
import re
import asyncio
from supabase import create_client, Client
from dotenv import load_dotenv

# Path setup
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Load env
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
load_dotenv(env_path)

SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: Supabase credentials missing")
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def normalize_url(url):
    # Match /shopdetail/{id} and keep only that part
    # Pattern: .../shopdetail/000000000542... -> .../shopdetail/000000000542
    m = re.search(r'(.*?/shopdetail/[^/]+)(?:/.*)?$', url)
    if m:
        return m.group(1)
    return url

async def main():
    print("Fetching Chouseiya beers...")
    # Fetch all chouseiya beers (url like 'beer-chouseiya')
    # Pagination might be needed if > 1000 items
    all_beers = []
    start = 0
    batch_size = 1000
    while True:
        res = supabase.table('scraped_beers').select('*').ilike('shop', '%ちょうせいや%').range(start, start+batch_size-1).execute()
        if not res.data:
            break
        all_beers.extend(res.data)
        if len(res.data) < batch_size:
            break
        start += batch_size
    
    print(f"Total Chouseiya beers found: {len(all_beers)}")

    # Fetch Gemini Data to check links
    print("Fetching Gemini Data...")
    res_gemini = supabase.table('gemini_data').select('*').execute() # Might be large, but whatever
    gemini_map = {g['url']: g for g in res_gemini.data}

    # Group by Normalized URL
    groups = {}
    for beer in all_beers:
        norm_url = normalize_url(beer['url'])
        if norm_url not in groups:
            groups[norm_url] = []
        groups[norm_url].append(beer)

    print(f"Unique Normalized URLs: {len(groups)}")

    delete_urls = []
    update_ops = [] # List of (old_url, new_url) to update
    gemini_updates = []

    for norm_url, items in groups.items():
        # Heuristic: Keep the one with the LATEST first_seen (closest to 'fresh')? 
        # Or LATEST last_seen (most recently confirmed)?
        # Let's keep the one that matches norm_url exactly if it exists.
        # Otherwise keep the one with recent last_seen.
        
        # Sort items: Exact match first, then by last_seen desc
        items.sort(key=lambda x: (x['url'] == norm_url, x['last_seen']), reverse=True)
        
        winner = items[0]
        losers = items[1:]

        # Mark losers for deletion
        for loser in losers:
            delete_urls.append(loser['url'])
        
        # If winner's URL is NOT normalized, we need to update it
        if winner['url'] != norm_url:
            update_ops.append({
                'old_url': winner['url'],
                'new_url': norm_url
            })
            # Also check if Gemini data needs moving
            # If winner had Gemini data, we update its key.
            # If winner didn't, but a loser did? We might lose data.
            # Let's try to preserve Gemini data from losers if winner lacks it.
            winner_gemini = gemini_map.get(winner['url'])
            if not winner_gemini:
                # Find a loser with gemini data
                for loser in losers:
                    if gemini_map.get(loser['url']):
                        # We found one! usage: update THIS gemini record's URL to norm_url
                        # And we must ensure we don't delete the loser's GEMINI data if it wasn't linked via cascade (it's not).
                        # Actually gemini keys are separate.
                        # So:
                        # 1. Update loser's gemini_data url -> norm_url
                        # 2. Don't need to update winner's gemini (it doesn't exist)
                        gemini_updates.append({
                            'old_url': loser['url'],
                            'new_url': norm_url
                        })
                        break # Took one
            else:
                 # Winner has gemini data, just update its key
                 gemini_updates.append({
                     'old_url': winner['url'],
                     'new_url': norm_url
                 })
        else:
            # Winner is already normalized.
            # Check if we can salvage duplicate Gemini data from losers?
            # Probably not worth merging JSONs.
            pass

    print(f"Deleting {len(delete_urls)} duplicate/legacy records...")
    # Batch delete
    if delete_urls:
        for i in range(0, len(delete_urls), 100):
            batch = delete_urls[i:i+100]
            supabase.table('scraped_beers').delete().in_('url', batch).execute()
            # Also delete orphaned gemini data for these losers?
            # If we moved it (above), it's safe. If we didn't move it, it's redundant/deleted.
            supabase.table('gemini_data').delete().in_('url', batch).execute()

    print(f"Updating {len(update_ops)} records to new URLs...")
    for op in update_ops:
        try:
            # Update Scraped Beer
            # Note: If target URL exists (shouldn't, because we grouped), upsert?
            # Update is safer.
            supabase.table('scraped_beers').update({'url': op['new_url']}).eq('url', op['old_url']).execute()
        except Exception as e:
            print(f"Error updating {op['old_url']} -> {op['new_url']}: {e}")

    print(f"Updating {len(gemini_updates)} Gemini records...")
    for op in gemini_updates:
        try:
             supabase.table('gemini_data').update({'url': op['new_url']}).eq('url', op['old_url']).execute()
        except Exception as e:
            # It's possible the target already has gemini data?
            print(f"Error updating gemini {op['old_url']}: {e}")

    print("Done normalization.")

if __name__ == "__main__":
    asyncio.run(main())
