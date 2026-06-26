from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from playwright.async_api import Page, Playwright
from scrapers.normalizer import normalize

BLOCKED_MARKERS = ("access denied", "captcha", "unblock", "datadome",
                   "are you human", "weryfikacja", "zabezpieczenie")


@dataclass
class ScrapeResult:
    source: str
    listings: list[dict] = field(default_factory=list)
    blocked: bool = False
    reason: Optional[str] = None


async def _is_blocked(page: Page) -> tuple[bool, Optional[str]]:
    try:
        title = await page.title()
        body_text = await page.evaluate("() => document.body ? document.body.innerText.slice(0, 2000) : ''")
    except Exception as e:
        return True, f"page read failed: {e}"
    combined = f"{title} {body_text}".lower()
    for marker in BLOCKED_MARKERS:
        if marker in combined:
            return True, f"blocked-marker:{marker}"
    return False, None


class BaseScraper(ABC):
    source: str = "base"
    timeout_ms: int = 30000

    @abstractmethod
    def build_url(self) -> str: ...

    @abstractmethod
    async def parse_page(self, page: Page) -> list[dict]:
        """Return raw listing dicts (pre-normalize)."""

    async def run(self, playwright: Playwright) -> ScrapeResult:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            resp = await page.goto(self.build_url(), timeout=self.timeout_ms, wait_until="domcontentloaded")
            if resp and resp.status >= 400:
                return ScrapeResult(self.source, blocked=True, reason=f"http {resp.status}")
            blocked, reason = await _is_blocked(page)
            if blocked:
                return ScrapeResult(self.source, blocked=True, reason=reason)
            raw_items = await self.parse_page(page)
            listings = [n for n in (normalize(r) for r in raw_items) if n]
            return ScrapeResult(self.source, listings=listings)
        except Exception as e:
            return ScrapeResult(self.source, blocked=True, reason=f"error: {e}")
        finally:
            await browser.close()
