import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import stealth

async def scrape():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        # Gebruik stealth om niet geblokkeerd te worden
        try:
            from playwright_stealth import stealth
            await stealth(page)
        except: pass
        
        print("🚀 Navigeren naar Candy.ai Live-sectie...")
        await page.goto("https://candy.ai/ai-girlfriend/olivia-carter/live-actions")
        await asyncio.sleep(5) # Wacht op animaties
        
        # Neem screenshot voor visuele analyse
        await page.screenshot(path="/home/faramix/candy_analysis.png", full_page=True)
        
        # Analyseer de knoppen en structuur
        buttons = await page.eval_on_selector_all("button", "elements => elements.map(e => e.innerText)")
        print(f"✅ Gevonden knoppen: {buttons}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape())
