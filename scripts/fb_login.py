"""One-time Facebook login to capture a Playwright storage_state.json.

Run on the HOST (needs a visible browser):
    pip install playwright && playwright install chromium
    FB_STORAGE_STATE_PATH=backend/secrets/fb_storage_state.json python scripts/fb_login.py

Log into Facebook in the window that opens, then return to the terminal and
press Enter. The resulting cookies are reused by FacebookProvider; the password
is never stored.
"""
import asyncio
import os

from playwright.async_api import async_playwright


async def main():
    out = os.getenv("FB_STORAGE_STATE_PATH", "backend/secrets/fb_storage_state.json")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        ctx = await browser.new_context()
        page = await ctx.new_page()
        await page.goto("https://www.facebook.com/login")
        print("Log into Facebook in the browser, then press Enter here.")
        input()
        await ctx.storage_state(path=out)
        print(f"Saved session -> {out}")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
