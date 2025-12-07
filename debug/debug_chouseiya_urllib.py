import urllib.request
import re
from bs4 import BeautifulSoup

def debug_chouseiya_urllib():
    url = "https://beer-chouseiya.shop/shopbrand/all_items/"
    print(f"Fetching {url}...")
    
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        content_bytes = response.read()
        
    print(f"Downloaded {len(content_bytes)} bytes.")
    
    # Try decoding
    try:
        content_str = content_bytes.decode('shift_jis')
        print("Decoded as Shift_JIS successfully.")
    except UnicodeDecodeError:
        print("Shift_JIS decode failed. Trying EUC-JP.")
        try:
            content_str = content_bytes.decode('euc-jp')
            print("Decoded as EUC-JP successfully.")
        except UnicodeDecodeError:
             print("EUC-JP decode failed. Trying UTF-8.")
             content_str = content_bytes.decode('utf-8', errors='replace')
    
    soup = BeautifulSoup(content_str, 'lxml')
    
    # Check '円'
    print(f"'円' in content: {'円' in content_str}")
    
    # Parse items
    image_links = soup.select("a[href^='/shopdetail/'] img")
    print(f"Found {len(image_links)} image links.")
    
    if image_links:
        img = image_links[0]
        parent_a = img.find_parent('a')
        
    if image_links:
        img = image_links[0]
        parent_a = img.find_parent('a')
        imgWrap = parent_a.parent
        
        grandparent = imgWrap.parent
        print(f"Grandparent Tag: {grandparent.name}, Class: {grandparent.get('class')}")
        
        detail_div = grandparent.find('div', class_='detail')
        if detail_div:
            print("--- Detail Div Children ---")
            for child in detail_div.children:
                if child.name:
                    print(f"  [{child.name} class={child.get('class')}] Text: {child.get_text(strip=True)}")
                elif child.strip():
                    print(f"  [Text] {child.strip()}")

if __name__ == "__main__":
    debug_chouseiya_urllib()
