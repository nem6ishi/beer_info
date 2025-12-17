
import os
import sys
from supabase import create_client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from dotenv import load_dotenv

# Load env
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
load_dotenv(env_path)

SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

STOP_WORDS = {
    'black', 'white', 'red', 'blue', 'green', 'yellow', 'gold', 'silver',
    'west', 'east', 'north', 'south', 'central',
    'company', 'co.', 'corp.', 'ltd.', 'inc.',
    'the', 'a', 'an', 'my', 'our', 'your',
    'new', 'old', 'big', 'small', 'great', 'best',
    'beer', 'brewery', 'brewing', 'craft', 'ale', 'lager', 'ipa',
    'top', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',
    'el', 'la', 'le', 'les', 'de', 'du', 'des', 'van', 'von',
    'st.', 'saint', 'mt.', 'mount',
    '8' # explicit bad alias found
}

def clean_aliases():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Fetch all breweries with aliases
    res = supabase.table('breweries').select('id, name_en, aliases').execute()
    
    updated_count = 0
    
    for b in res.data:
        aliases = b.get('aliases') or []
        original_aliases = list(aliases)
        name = b.get('name_en')
        
        new_aliases = []
        changed = False
        
        for a in aliases:
            is_bad = False
            # Check length and specific character content
            if len(a) < 3:
                # Keep if it's Japanese (simplistic check: broad unicode range?)
                # Or just assume short English lookalikes are bad.
                # Let's filter strict matches to our known bad pattern (English words)
                # But allow "21st" or similar?
                # For safety, strictly remove if single char or 2 chars that are also likely bad.
                # Actually, check against STOP_WORDS first.
                pass
            
            if a.lower() in STOP_WORDS:
                is_bad = True
            
            # Remove single digit string "8" (from 8 bit brewing)
            if a.isdigit() and len(a) < 2:
                is_bad = True

            # General rule: if it looks like English and length < 3, suspicious.
            # But let's stick to the generated list for now.
            
            if not is_bad:
                new_aliases.append(a)
            else:
                changed = True
                print(f"  Removing bad alias '{a}' from {name}")

        if changed:
            # Update DB
            try:
                supabase.table('breweries').update({'aliases': new_aliases}).eq('id', b['id']).execute()
                updated_count += 1
            except Exception as e:
                print(f"Error updating {name}: {e}")

    print(f"Cleaned aliases for {updated_count} breweries.")

if __name__ == "__main__":
    clean_aliases()
