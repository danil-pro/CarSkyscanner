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


def _location(art) -> str | None:
    # Otomoto renders "<city> (<region>)" in a <p>/<li>, separate from the <dd> specs.
    for el in art.select("p, li"):
        t = el.get_text(" ", strip=True)
        if "(" in t and ")" in t and len(t) < 60:
            return t
    return None


def parse_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    # Current Otomoto listing cards are plain <article> with an /oferta/ link
    # (the old [data-testid="listing-ad"] only matches a handful now -> 0 results).
    for art in soup.select("article"):
        a = art.select_one('a[href*="/oferta/"]')
        if not a:
            continue
        url = resolve_url(BASE_URL, a["href"])
        if not url:
            continue
        dds = [d.get_text(strip=True) for d in art.select("dd")]
        if not dds:
            # "Wyróżniony Sprzedawca" dealer-showcase cards bundle several listings
            # with specs in <li> (no <dd>) and multiple /oferta/ links — not a single
            # listing. Skip them rather than emit a garbage entry (title+price from
            # the first sub-listing, no year/fuel/transmission).
            continue
        h2 = art.select_one("h2")
        h3 = art.select_one("h3")          # price lives in an <h3> on current Otomoto cards
        # The offer link's own text is the clean listing title; <h2> on some
        # (promoted) cards also bundles the model line + price, so prefer the link.
        title = a.get_text(" ", strip=True) or (h2.get_text(" ", strip=True) if h2 else "")
        out.append({
            "title": title[:200],
            "brand": "", "model": "",
            "year": _pick_year(dds),
            "price": h3.get_text(strip=True) if h3 else None,
            "mileage": next((d for d in dds if "km" in d.lower()), None),
            "fuel_type": next((d for d in dds if d.lower() in ("benzyna", "diesel", "hybryda", "elektryczny", "lpg")), None),
            "transmission": next((d for d in dds if d.lower() in ("manualna", "automatyczna")), None),
            "location": _location(art),
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
