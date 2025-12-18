import os
import sys
import argparse

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.utils.script_utils import setup_script

def inspect_gemini(url):
    supabase, logger = setup_script("InspectGemini")
    
    res = supabase.table('gemini_data').select('*').eq('url', url).execute()
    if res.data:
        print(res.data[0])
    else:
        print("No data found")

if __name__ == "__main__":
    inspect_gemini("https://beer-chouseiya.shop/shopdetail/000000002216")
