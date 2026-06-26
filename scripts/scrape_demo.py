import asyncio, os, sys
# scrapers/ lives at the repo root, not under backend/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scrapers.otomoto import OtomotoScraper
from scrapers.olx import OLXScraper
from scrapers.facebook import FacebookScraper
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as pw:
        for scraper in (OtomotoScraper(), OLXScraper(), FacebookScraper()):
            r = await scraper.run(pw)
            print(f"\n=== {r.source} ===  blocked={r.blocked} reason={r.reason}")
            for it in r.listings[:5]:
                print(f"  - {it.get('title')} | {it.get('price')} PLN | {it.get('url')}")
            if not r.listings and not r.blocked:
                print("  (no listings parsed — selectors may need updating)")


if __name__ == "__main__":
    asyncio.run(main())
