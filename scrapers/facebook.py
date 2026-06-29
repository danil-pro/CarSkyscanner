import os
import re
from typing import Optional

from bs4 import BeautifulSoup
from playwright.async_api import Playwright

from scrapers.base import (
    BaseScraper,
    ScrapeResult,
    USER_AGENT,
    STEALTH_INIT,
    resolve_url,
)
from scrapers.providers import ListingProvider, ProviderResult
from scrapers.filters import build_facebook_url

FB_BASE = "https://www.facebook.com/marketplace/"
_LOGIN_MARKERS = ("/login", "/checkpoint", "/two_step", "/recover")


class FacebookScraper(BaseScraper):
    """Legacy stub for the manual /scrape flow (no session) — reports blocked.

    Kept so scraper_runner.py keeps importing; the live-search flow uses
    FacebookProvider with a saved login session instead.
    """

    source = "facebook"

    def build_url(self) -> str:
        return FB_BASE

    async def parse_page(self, page):  # never reached
        return []

    async def run(self, playwright=None) -> ScrapeResult:
        return ScrapeResult(
            source=self.source,
            blocked=True,
            reason="login required (use /search/live with a saved session)",
        )


class FacebookProvider(ListingProvider):
    """Scrape FB Marketplace using a saved login session (storage_state.json)."""

    source = "facebook"

    def __init__(self, filters, storage_state_path: Optional[str] = None):
        self.filters = filters
        self.storage_state_path = storage_state_path or os.getenv("FB_STORAGE_STATE_PATH")

    def build_url(self) -> str:
        return build_facebook_url(self.filters)

    def _parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        out = []
        for a in soup.select('a[href*="/marketplace/item/"]'):
            href = a.get("href")
            url = resolve_url(FB_BASE, href)
            if not url:
                continue
            text = a.get_text(" ", strip=True)
            price = re.search(r"(\d[\d  ]*)\s*(zł|zl|PLN)?", text)
            year = re.search(r"(19|20)\d{2}", text)
            out.append({
                "title": text[:200] or None,
                "brand": "", "model": "",
                "year": year.group(0) if year else None,
                "price": price.group(1) if price else None,
                "mileage": None, "fuel_type": None, "transmission": None,
                "location": None,
                "source": "facebook",
                "url": url,
                "image_url": None,
            })
        return out

    async def search(self, playwright: Playwright) -> ProviderResult:
        if not self.storage_state_path or not os.path.exists(self.storage_state_path):
            return ProviderResult(self.source, status="session-not-configured",
                                  reason="no storage_state file")
        if playwright is None:
            return ProviderResult(self.source, status="error", reason="no playwright")
        browser = await playwright.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled",
                  "--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(
            storage_state=self.storage_state_path,
            user_agent=USER_AGENT,
            locale="pl-PL",
            viewport={"width": 1366, "height": 800},
        )
        await context.add_init_script(STEALTH_INIT)
        page = await context.new_page()
        try:
            await page.goto(self.build_url(), timeout=45000, wait_until="domcontentloaded")
            current = page.url
            if any(m in current for m in _LOGIN_MARKERS):
                return ProviderResult(self.source, status="session-invalid",
                                      reason=f"redirected to {current}")
            raw = self._parse(await page.content())
            return ProviderResult(self.source, listings=raw, status="ok", found=len(raw))
        except Exception as e:
            return ProviderResult(self.source, status="error", reason=f"error: {e}")
        finally:
            await browser.close()
