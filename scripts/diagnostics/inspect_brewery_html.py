import requests
from bs4 import BeautifulSoup

url = "https://untappd.com/w/wakasaimo-honpo/12554"
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

resp = requests.get(url, headers=headers)
soup = BeautifulSoup(resp.text, 'lxml')

print("--- Searching for .logo img ---")
logo_legacy = soup.select_one('.logo img')
if logo_legacy:
    print(f"Legacy selector found: {logo_legacy}")

print("\n--- Searching for .label img ---")
label_img = soup.select_one('.label img')
if label_img:
    print(f"Label selector found: {label_img}")
    
print("\n--- Searching for images in .basic ---")
basic_imgs = soup.select('.basic img')
for img in basic_imgs:
    print(f"Basic img: {img}")

print("\n--- Searching for div.logo reference ---")
div_logos = soup.select('div.logo')
for div in div_logos:
    print(f"Div Logo: {div}")
