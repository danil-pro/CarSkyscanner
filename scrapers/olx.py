import re
from playwright.async_api import Page
from bs4 import BeautifulSoup
from scrapers.base import BaseScraper


def parse_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for card in soup.select('[data-cy="l-card"]'):
        a = card.select_one("a[href]")
        img = card.select_one("img")
        price = card.select_one('[data-testid="ad-price"]')
        meta = card.get_text(" ", strip=True)
        year = re.search(r"(19|20)\d{2}", meta)
        mileage = re.search(r"([\d ]+) km", meta)
        if not a or not price:
            continue
        out.append({
            "title": (card.select_one("h6").get_text(strip=True) if card.select_one("h6") else meta[:200]),
            "brand": "", "model": "",
            "year": year.group(0) if year else None,
            "price": price.get_text(strip=True),
            "mileage": mileage.group(0) if mileage else None,
            "fuel_type": next((t for t in ("Benzyna", "Diesel", "Hybryda", "Elektryczny", "LPG") if t in meta), None),
            "transmission": None,
            "location": None,
            "source": "olx",
            "url": a["href"],
            "image_url": img["src"] if img and img.get("src") else None,
        })
    return out


class OLXScraper(BaseScraper):
    source = "olx"

    def build_url(self) -> str:
        return "https://www.olx.pl/motoryzacja/samochody/"

    async def parse_page(self, page: Page) -> list[dict]:
        return parse_html(await page.content())
