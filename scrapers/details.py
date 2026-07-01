from typing import Optional
from bs4 import BeautifulSoup
from scrapers.base import resolve_url


def _images(soup, base_url: str) -> list[str]:
    seen, out = set(), []
    for img in soup.select("img"):
        for attr in ("src", "data-src", "data-lazy-src"):
            val = img.get(attr)
            if val:
                u = resolve_url(base_url, val.split(",")[0])
                if u and u not in seen:
                    seen.add(u)
                    out.append(u)
                    break
    return out


def _description(soup, selectors: tuple[str, ...]) -> Optional[str]:
    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            txt = el.get_text(" ", strip=True)
            if len(txt) >= 20:
                return txt[:5000]
    return None


def _parse_olx(html: str, base_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    return {
        "description": _description(soup, ('[data-cy="ad_description"]', 'div[aria-label="Opis"]', ".descriptioncontent")),
        "images": _images(soup, base_url),
    }


def _parse_otomoto(html: str, base_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    return {
        "description": _description(soup, ('[data-testid="content-container"]', 'div[data-role="offer-description"]', "#description")),
        "images": _images(soup, base_url),
    }


def _parse_facebook(html: str, base_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    return {
        "description": _description(soup, ('[data-singular="true"]', 'div[role="main"]', "span")),
        "images": _images(soup, base_url),
    }


_PARSERS = {"olx": _parse_olx, "otomoto": _parse_otomoto, "facebook": _parse_facebook}


def parse_detail(source: str, html: str, base_url: str) -> dict:
    """Best-effort extraction of {description, images}. Never raises."""
    parser = _PARSERS.get((source or "").lower())
    if parser is None:
        return {"description": None, "images": []}
    try:
        return parser(html, base_url)
    except Exception:
        return {"description": None, "images": []}
