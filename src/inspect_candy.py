import asyncio
from playwright.async_api import async_playwright

async def inspect_candy():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        print("🌐 Visiting Candy.ai...")
        try:
            await page.goto("https://candy.ai/", wait_until="networkidle", timeout=60000)
            print("✅ Candy.ai Loaded!")
            
            # Take a screenshot of the homepage/dashboard
            await page.screenshot(path="/home/faramix/candy_ai_landing.png")
            print("📸 Screenshot saved: candy_ai_landing.png")
            
            # Extract meta information
            title = await page.title()
            description = await page.get_attribute('meta[name="description"]', 'content')
            print(f"📄 Title: {title}")
            print(f"📄 Description: {description}")
            
            # Look for AI characters or chat interfaces
            chars = await page.query_selector_all(".character-card")
            print(f"👥 AI Characters found on landing: {len(chars)}")
            
            # Extract some visible text to understand their value prop
            body_text = await page.inner_text("body")
            print(f"📄 Visible Body Text (First 200 chars): {body_text[:200]}...")

        except Exception as e:
            print(f"❌ Failed to inspect Candy.ai: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(inspect_candy())
