import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(url, key)

SQL = """
-- 8. get_available_filters: Optimized aggregation for SSR
-- Returns top 100 styles and all breweries in a single call
CREATE OR REPLACE FUNCTION get_available_filters()
RETURNS TABLE (
    styles JSONB,
    breweries JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        (SELECT jsonb_agg(d) FROM (
            SELECT untappd_style as style, count(*) as count 
            FROM public.beer_info_view 
            WHERE untappd_style IS NOT NULL 
            GROUP BY untappd_style 
            ORDER BY count DESC 
            LIMIT 100
        ) d) as styles,
        (SELECT jsonb_agg(d) FROM (
            SELECT name_en, name_jp 
            FROM public.breweries 
            ORDER BY name_en ASC
        ) d) as breweries;
END;
$$ LANGUAGE plpgsql SECURITY INVOKER SET search_path = '';
"""

def apply_rpc():
    print(f"Applying RPC to {url}...")
    # Using the undocumented execute_sql if available, or just printing instructions
    # Note: Supabase python client doesn't have a direct 'execute_sql' method for raw SQL.
    # Usually we recommend using the SQL Editor in Supabase UI for DDL changes.
    # But I can try to use a dummy RPC or something if I had one.
    
    # Since I cannot easily run raw DDL via the standard client without a specific helper function,
    # and the user previously ran migration via my advice, I'll ask them to check if they can run it
    # or I will try to use a 'postgres' role if I have direct access (which I don't).
    
    print("Please run the following SQL in your Supabase SQL Editor:")
    print(SQL)

if __name__ == "__main__":
    apply_rpc()
