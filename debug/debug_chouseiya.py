import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

async def debug_chouseiya():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        print("Navigating...")
        await page.goto("https://beer-chouseiya.shop/shopbrand/all_items/")
        
        # Check title and charset
        title = await page.title()
        print(f"Title: {title}")
        
        content = await page.content()
        await browser.close()
        
        soup = BeautifulSoup(content, 'lxml')
        
        # Check regex '円'
        print(f"Test '円' in content: {'円' in content}")
        
        # Find first item
        image_links = soup.select("a[href^='/shopdetail/'] img")
        if not image_links:
            print("No items found.")
            return

        img = image_links[0]
        print(f"First image found: {img}")
        
        parent_a = img.find_parent('a')
        print(f"Parent A: {parent_a}")
        
        current = parent_a.next_sibling
        print("--- Siblings ---")
        for i in range(10):
            if not current: break
            
            node_type = type(current).__name__
            text = str(current).strip()
            print(f"Sibling {i} ({node_type}): {repr(text)}")
            
            current = current.next_sibling

if __name__ == "__main__":
    asyncio.run(debug_chouseiya())
