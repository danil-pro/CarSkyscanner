import asyncio
from typing import Callable, Optional
from playwright.async_api import async_playwright
from scrapers.base import USER_AGENT, STEALTH_INIT
from scrapers.details import parse_detail
from app.config import settings

_BASE = {"olx": "https://www.olx.pl", "otomoto": "https://www.otomoto.pl", "facebook": "https://www.facebook.com"}

# A seam for tests: DEFAULT_FETCHER(car) -> {"description","images","status"} (may raise).
DEFAULT_FETCHER: Callable = None  # set below


async def _fetch_via_playwright(car) -> dict:
    base = _BASE.get((car.source or "").lower(), "https://example.com")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=[
            "--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"])
        ctx_kwargs = dict(user_agent=USER_AGENT, locale="pl-PL", viewport={"width": 1366, "height": 800})
        if car.source == "facebook":
            path = settings.FB_STORAGE_STATE_PATH
            if not path:
                return {"description": None, "images": [], "status": "unavailable"}
            ctx_kwargs["storage_state"] = path
        ctx = await browser.new_context(**ctx_kwargs)
        await ctx.add_init_script(STEALTH_INIT)
        page = await ctx.new_page()
        try:
            await page.goto(car.url, timeout=45000, wait_until="domcontentloaded")
            html = await page.content()
            return parse_detail(car.source, html, base)
        finally:
            await browser.close()


def _fetch(car) -> dict:
    return asyncio.run(_fetch_via_playwright(car))


DEFAULT_FETCHER = _fetch


def fetch_details(car, fetcher: Optional[Callable] = None) -> dict:
    f = fetcher or DEFAULT_FETCHER
    try:
        out = f(car)
        return {"description": out.get("description"), "images": out.get("images") or [],
                "specs": out.get("specs") or {}, "status": out.get("status", "ok")}
    except Exception:
        return {"description": None, "images": [], "status": "unavailable"}
