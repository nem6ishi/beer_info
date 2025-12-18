import sys
import os

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.append(project_root)

from scripts.utils.script_utils import setup_script

def cleanup_breweries():
    supabase, logger = setup_script("cleanup_breweries")
    
    # 1. Identify common wrongly mapped Japanese names
    wrong_mappings = {
        "ウェストコーストブルーイング": "West Coast Brewing",
        "バテレ": "VERTERE",
        "クラフトロックブルーイング": "Craftrock Brewing",
        "京都醸造": "Kyoto Brewing Co.",
        "忽布古丹": "Hop Kotan Brewing"
    }
    
    # Load all breweries 
    res = supabase.table('breweries').select('*').execute()
    breweries = res.data
    print(f"Loaded {len(breweries)} breweries for inspection.")

    for item in breweries:
        name_en = item['name_en']
        name_jp = item.get('name_jp')
        aliases = item.get('aliases') or []
        
        updated_data = {}
        
        # Check name_jp
        if name_jp in wrong_mappings:
            correct_en = wrong_mappings[name_jp]
            if name_en.lower() != correct_en.lower():
                print(f"  Removing wrong name_jp '{name_jp}' from: {name_en}")
                updated_data['name_jp'] = None
                
        # Check aliases
        new_aliases = aliases.copy()
        for alias in aliases:
            if alias in wrong_mappings:
                correct_en = wrong_mappings[alias]
                if name_en.lower() != correct_en.lower():
                    print(f"  Removing wrong alias '{alias}' from: {name_en}")
                    new_aliases = [a for a in new_aliases if a != alias]
        
        if len(new_aliases) != len(aliases):
            updated_data['aliases'] = new_aliases
            
        if updated_data:
            supabase.table('breweries').update(updated_data).eq('id', item['id']).execute()

    print("Cleanup complete.")

if __name__ == '__main__':
    cleanup_breweries()
