from urllib.parse import quote
import re
from playwright.async_api import Page
from bs4 import BeautifulSoup
from scrapers.base import BaseScraper, resolve_url, extract_image_url

BASE_URL = "https://www.otomoto.pl"


def _pick_year(dds: list[str]) -> str | None:
    """Return the first <dd> that is a bare plausible year (e.g. '2018'), not a price/date slot."""
    for d in dds:
        s = d.strip()
        if re.fullmatch(r"(19|20)\d{2}", s):
            y = int(s)
            if 1950 <= y <= 2030:  # loose bound; parse_year re-checks against today
                return s
    return None


def parse_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for art in soup.select('[data-testid="listing-ad"]'):
        a = art.select_one("a[href]")
        if not a:
            continue
        url = resolve_url(BASE_URL, a["href"])
        if not url:
            continue
        dds = [d.get_text(strip=True) for d in art.select("dd")]
        price_dd = art.select_one('[data-testid="ad-price"]')
        out.append({
            "title": art.get_text(" ", strip=True)[:200],
            "brand": "", "model": "",
            "year": _pick_year(dds),
            "price": price_dd.get_text(strip=True) if price_dd else None,
            "mileage": next((d for d in dds if "km" in d.lower()), None),
            "fuel_type": next((d for d in dds if d.lower() in ("benzyna", "diesel", "hybryda", "elektryczny", "lpg")), None),
            "transmission": next((d for d in dds if d.lower() in ("manualna", "automatyczna")), None),
            "location": dds[-1] if dds else None,
            "source": "otomoto",
            "url": url,
            "image_url": extract_image_url(art, BASE_URL),
        })
    return out


class OtomotoScraper(BaseScraper):
    source = "otomoto"

    def __init__(self, brand: str | None = None, model: str | None = None):
        self.brand = brand
        self.model = model

    def build_url(self) -> str:
        path = "osobowe"
        if self.brand:
            path = f"osobowe/{quote(self.brand)}"
        return f"{BASE_URL}/{path}"

    async def parse_page(self, page: Page) -> list[dict]:
        return parse_html(await page.content())
