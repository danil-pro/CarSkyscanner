import re
from playwright.async_api import Page
from bs4 import BeautifulSoup
from scrapers.base import BaseScraper, resolve_url, extract_image_url

BASE_URL = "https://www.olx.pl"


def parse_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for card in soup.select('[data-cy="l-card"]'):
        a = card.select_one("a[href]")
        price = card.select_one('[data-testid="ad-price"]')
        meta = card.get_text(" ", strip=True)
        year = re.search(r"(19|20)\d{2}", meta)
        mileage = re.search(r"([\d  ]+)\s*km", meta)
        href = a["href"] if a else None
        url = resolve_url(BASE_URL, href)
        if not url:
            continue
        out.append({
            "title": (card.select_one("h6").get_text(strip=True) if card.select_one("h6") else meta[:200]),
            "brand": "", "model": "",
            "year": year.group(0) if year else None,
            "price": price.get_text(strip=True) if price else None,
            "mileage": mileage.group(1).replace(" ", " ") if mileage else None,
            "fuel_type": next((t for t in ("Benzyna", "Diesel", "Hybryda", "Elektryczny", "LPG") if t in meta), None),
            "transmission": None,
            "location": None,
            "source": "otomoto" if "otomoto.pl" in (href or "") else "olx",
            "url": url,
            "image_url": extract_image_url(card, BASE_URL),
        })
    return out


class OLXScraper(BaseScraper):
    source = "olx"

    def build_url(self) -> str:
        return "https://www.olx.pl/motoryzacja/samochody/"

    async def parse_page(self, page: Page) -> list[dict]:
        return parse_html(await page.content())
