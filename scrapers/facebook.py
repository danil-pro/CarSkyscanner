import json
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
from scrapers.normalizer import normalize

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
        # FB no longer renders search results as <a href="/marketplace/item/">;
        # the listings live in embedded GraphQL/relay JSON. Mine the <script>
        # blobs for listing objects and build normalized-ish dicts from them.
        soup = BeautifulSoup(html, "html.parser")
        raw: list[dict] = []
        for s in soup.find_all("script"):
            t = s.string or ""
            if '"listing_price"' not in t and "GroupCommerceProductItem" not in t:
                continue
            try:
                self._collect_listings(json.loads(t), raw)
            except Exception:
                continue
            if len(raw) >= 50:
                break
        seen, out = set(), []
        for l in raw:
            lid = str(l.get("id") or "")
            if not lid or lid in seen:
                continue
            seen.add(lid)
            out.append(self._listing_to_dict(l))
        return out

    @staticmethod
    def _collect_listings(obj, out, depth=0):
        if depth > 25 or len(out) >= 50:
            return
        if isinstance(obj, dict):
            if "listing_price" in obj or obj.get("__typename") in (
                "MarketplaceListing", "GroupCommerceProductItem"
            ):
                out.append(obj)
                if len(out) >= 50:
                    return
            for v in obj.values():
                FacebookProvider._collect_listings(v, out, depth + 1)
        elif isinstance(obj, list):
            for v in obj[:80]:
                FacebookProvider._collect_listings(v, out, depth + 1)

    @staticmethod
    def _listing_to_dict(l: dict) -> dict:
        lid = str(l.get("id") or "")
        title = (l.get("marketplace_listing_title") or l.get("custom_title") or "").strip()
        price = (l.get("listing_price") or {}).get("formatted_amount")
        photo = (((l.get("primary_listing_photo") or {}).get("image") or {}).get("uri"))
        geo = (l.get("location") or {}).get("reverse_geocode") or {}
        location = geo.get("city") or ((geo.get("city_page") or {}).get("display_name"))
        year = re.search(r"(19|20)\d{2}", title)
        return {
            "title": title[:200] or None,
            "brand": "", "model": "",
            "year": year.group(0) if year else None,
            "price": price,
            "mileage": None, "fuel_type": None, "transmission": None,
            "location": location,
            "source": "facebook",
            "url": f"https://www.facebook.com/marketplace/item/{lid}/",
            "image_url": photo,
        }

    @staticmethod
    def _summarize(raw: list[dict]) -> ProviderResult:
        # A valid session that yields zero item links almost always means FB
        # changed its DOM or returned nothing for this location/query. Surface
        # that as a distinct status instead of a bare, ambiguous "ok / found 0".
        if raw:
            return ProviderResult("facebook", listings=raw, status="ok", found=len(raw))
        return ProviderResult(
            "facebook", status="no-results",
            reason="0 result links parsed — FB layout changed or no results for this location/query",
        )

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
            # Scroll to render lazy-loaded Marketplace items (otherwise found=0).
            try:
                for _ in range(6):
                    await page.evaluate("window.scrollBy(0, window.innerHeight)")
                    await page.wait_for_timeout(400)
                await page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            raw = [n for n in (normalize(r) for r in self._parse(await page.content())) if n]
            return self._summarize(raw)
        except Exception as e:
            return ProviderResult(self.source, status="error", reason=f"error: {e}")
        finally:
            await browser.close()
