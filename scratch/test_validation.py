import asyncio
import re
from backend.src.services.untappd.text_utils import normalize_for_comparison, strip_for_core_comparison

def test_validation():
    brewery = "Kyoto Brewing x Iemori-do"
    beer = "Kitsunebi"
    
    title = "Kitsunebi - Kyoto Brewing Company - Untappd"
    
    b_norm = normalize_for_comparison(brewery)
    t_norm = normalize_for_comparison(title)
    
    print(f"Brewery Norm: {b_norm}")
    print(f"Title Norm: {t_norm}")
    print(f"Match? {b_norm in t_norm}")
    
    # Try splitting by 'x'
    primary = re.split(r'\s*[xX×]\s*', brewery)[0]
    p_norm = normalize_for_comparison(primary)
    print(f"Primary Norm: {p_norm}")
    print(f"Match Primary? {p_norm in t_norm}")

test_validation()
