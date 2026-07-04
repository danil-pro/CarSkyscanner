import re
from playwright.async_api import Page
from bs4 import BeautifulSoup
from scrapers.base import BaseScraper, resolve_url, extract_image_url

BASE_URL = "https://www.olx.pl"


def _location(card) -> str | None:
    # OLX renders "<city> - Odświeżono/Dodane <when>" in a location-date element.
    el = card.select_one('[data-testid="location-date"]')
    if el:
        return el.get_text(" ", strip=True).split(" - ")[0].strip() or None
    for p in card.select("p"):
        t = p.get_text(" ", strip=True)
        if " - " in t and ("Odświeżono" in t or "Dodane" in t):
            return t.split(" - ")[0].strip() or None
    return None


def parse_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for card in soup.select('[data-cy="l-card"]'):
        a = card.select_one("a[href]")
        price = card.select_one('[data-testid="ad-price"]')
        meta = card.get_text(" ", strip=True)
        # Anchor the year to the spec line "YEAR - MILEAGE km" (or "YEAR · MILEAGE km").
        # Without this, a listing date like "31 maja 2026" is grabbed before the real year.
        year = re.search(r"((?:19|20)\d{2})\D{0,3}\d[\d ]*?km", meta)
        mileage = re.search(r"([\d  ]+)\s*km", meta)
        href = a["href"] if a else None
        url = resolve_url(BASE_URL, href)
        if not url:
            continue
        # h4 holds just the title; [data-cy="ad-card-title"] is a wrapper that also
        # includes the price ("... 52 300 zł do negocjacji"), so prefer h4.
        title_el = card.select_one("h4") or card.select_one('[data-cy="ad-card-title"]') or card.select_one("h6")
        out.append({
            "title": title_el.get_text(" ", strip=True) if title_el else meta[:200],
            "brand": "", "model": "",
            "year": year.group(1) if year else None,
            "price": price.get_text(strip=True) if price else None,
            "mileage": mileage.group(1).replace(" ", " ") if mileage else None,
            "fuel_type": next((t for t in ("Benzyna", "Diesel", "Hybryda", "Elektryczny", "LPG") if t in meta), None),
            "transmission": None,
            "location": _location(card),
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
