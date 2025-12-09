import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: credentials missing")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

print("Checking for persisted Gemini data in beer_info_view...")
try:
    # Select count of rows with brewery_name_en (which comes from gemini_data)
    res = supabase.table('beer_info_view') \
        .select('*', count='exact') \
        .not_.is_('brewery_name_en', 'null') \
        .execute()
    
    count = res.count
    print(f"✅ Found {count} enriched beers in the view.")
    
    if count > 0:
        print("🎉 SUCCESS: Gemini data persisted and linked automatically!")
        # Show a sample
        sample = res.data[0]
        print(f"Sample: {sample.get('name')} -> {sample.get('brewery_name_en')} / {sample.get('beer_name_en')}")
    else:
        print("❌ FAILURE: No enriched data found. Persistence failed.")

except Exception as e:
    print(f"❌ Error checking view: {e}")
