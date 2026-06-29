from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urljoin
from playwright.async_api import Page, Playwright
from scrapers.normalizer import normalize

BLOCKED_MARKERS = ("access denied", "captcha", "unblock", "datadome",
                   "are you human", "weryfikacja", "zabezpieczenie")

# Best-effort anti-bot hardening. NOTE: commercial bot-protection (e.g. the
# DataDome layer used by otomoto.pl) fingerprints TLS/canvas/behaviour and is
# hard to defeat with these tweaks alone — reliable access needs a partner/data
# agreement. This only removes the most obvious automation signals.
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")

STEALTH_INIT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['pl-PL', 'pl', 'en'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
window.chrome = { runtime: {} };
"""

_PLACEHOLDER_FRAGMENTS = ("no_thumbnail", "no-thumbnail", "blank.gif",
                          "placeholder", "1x1.gif")


def resolve_url(base: str, href: Optional[str]) -> Optional[str]:
    """Turn a possibly-relative href into an absolute URL, dropping junk."""
    if not href:
        return None
    href = href.strip().split(" ")[0]
    if href.startswith("data:") or any(p in href for p in _PLACEHOLDER_FRAGMENTS):
        return None
    if href.startswith("//"):
        return "https:" + href
    return urljoin(base.rstrip("/") + "/", href)


def extract_image_url(card, base: str) -> Optional[str]:
    """Pick a real <img> source from a card, preferring lazy-load attributes."""
    img = card.select_one("img")
    if not img:
        return None
    for attr in ("src", "data-src", "data-lazy-src"):
        val = img.get(attr)
        if val:
            url = resolve_url(base, val.split(",")[0])
            if url:
                return url
    srcset = img.get("srcset") or img.get("data-srcset")
    if srcset:
        return resolve_url(base, srcset.split(",")[0])
    return None


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
        browser = await playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )
        context = await browser.new_context(
            user_agent=USER_AGENT,
            locale="pl-PL",
            timezone_id="Europe/Warsaw",
            viewport={"width": 1366, "height": 800},
            extra_http_headers={"Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8"},
        )
        await context.add_init_script(STEALTH_INIT)
        page = await context.new_page()
        try:
            resp = await page.goto(self.build_url(), timeout=self.timeout_ms,
                                   wait_until="domcontentloaded")
            if resp and resp.status >= 400:
                return ScrapeResult(self.source, blocked=True, reason=f"http {resp.status}")
            try:
                await page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            blocked, reason = await _is_blocked(page)
            if blocked:
                return ScrapeResult(self.source, blocked=True, reason=reason)
            # Scroll to trigger lazy-loaded thumbnails (and any infinite scroll).
            try:
                for _ in range(8):
                    await page.evaluate("window.scrollBy(0, window.innerHeight)")
                    await page.wait_for_timeout(300)
                await page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            raw_items = await self.parse_page(page)
            listings = [n for n in (normalize(r) for r in raw_items) if n]
            return ScrapeResult(self.source, listings=listings)
        except Exception as e:
            return ScrapeResult(self.source, blocked=True, reason=f"error: {e}")
        finally:
            await browser.close()
