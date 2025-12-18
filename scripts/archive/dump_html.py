import os
import sys
import requests

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scripts.utils.script_utils import setup_script

def dump_html(url):
    _, logger = setup_script("DumpHTML")
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'}
    logger.info(f"Fetching: {url}")
    res = requests.get(url, headers=headers)
    
    with open('akizuki_dump.html', 'w') as f:
        f.write(res.text)
    
    logger.info("Dumped to akizuki_dump.html")
    # Print first few lines of title or something
    if "<title>" in res.text:
       print(f"Title: {res.text.split('<title>')[1].split('</title>')[0]}")

if __name__ == "__main__":
    dump_html("https://untappd.com/b/yorocco-beer-akizuki-hoppy-farmhouse-ale/5536411")
