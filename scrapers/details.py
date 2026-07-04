import json
import re
from typing import Optional
from bs4 import BeautifulSoup
from scrapers.base import resolve_url, is_car_image

# A detail-page spec line, e.g. "Skrzynia biegów: Manualna" / "Przebieg: 187 000 km".
_SPEC_LABEL_RE = re.compile(r"^([A-ZĄĆĘŁŃÓŚŹŻ][^:]{1,40}?):\s+(\S.{0,60})$")


def _images(soup, base_url: str) -> list[str]:
    # Keep only real car photos (apollo.olxcdn) — filters out App Store / Google
    # Play badges, site logos and UI icons present on the detail page.
    seen, out = set(), []
    for img in soup.select("img"):
        for attr in ("src", "data-src", "data-lazy-src"):
            val = img.get(attr)
            if val:
                u = resolve_url(base_url, val.split(",")[0])
                if u and u not in seen and is_car_image(u):
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


def _specs_olx(soup) -> dict:
    """OLX renders specs as <p>Label: Value</p>; ld+json Vehicle adds a few more."""
    specs: dict[str, str] = {}
    for p in soup.select("p"):
        t = p.get_text(" ", strip=True)
        if len(t) > 80:
            continue
        m = _SPEC_LABEL_RE.match(t)
        if m:
            specs[m.group(1).strip()] = m.group(2).strip()
    for s in soup.select('script[type="application/ld+json"]'):
        try:
            d = json.loads(s.string or "")
        except Exception:
            continue
        if not isinstance(d, dict) or d.get("@type") != "Vehicle":
            continue
        for src, dst in (("brand", "Marka"), ("model", "Model"),
                         ("color", "Kolor"), ("productionDate", "Rok produkcji")):
            v = d.get(src)
            if v and dst not in specs:
                specs[dst] = str(v)
    return specs


def _specs_otomoto(soup) -> dict:
    """Otomoto detail specs are <dt>label</dt><dd>value</dd> pairs (best-effort)."""
    specs: dict[str, str] = {}
    for dt in soup.select("dt"):
        dd = dt.find_next_sibling("dd")
        if dd:
            k, v = dt.get_text(" ", strip=True), dd.get_text(" ", strip=True)
            if k and v and len(k) < 40 and len(v) < 60:
                specs[k] = v
    return specs


def _parse_olx(html: str, base_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    return {
        "description": _description(soup, ('[data-cy="ad_description"]', 'div[aria-label="Opis"]', ".descriptioncontent")),
        "images": _images(soup, base_url),
        "specs": _specs_olx(soup),
    }


def _parse_otomoto(html: str, base_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    return {
        "description": _description(soup, ('[data-testid="content-container"]', 'div[data-role="offer-description"]', "#description")),
        "images": _images(soup, base_url),
        "specs": _specs_otomoto(soup),
    }


def _parse_facebook(html: str, base_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    return {
        "description": _description(soup, ('[data-singular="true"]', 'div[role="main"]', "span")),
        "images": _images(soup, base_url),
        "specs": {},
    }


_PARSERS = {"olx": _parse_olx, "otomoto": _parse_otomoto, "facebook": _parse_facebook}


def parse_detail(source: str, html: str, base_url: str) -> dict:
    """Best-effort extraction of {description, images, specs}. Never raises."""
    parser = _PARSERS.get((source or "").lower())
    if parser is None:
        return {"description": None, "images": [], "specs": {}}
    try:
        out = parser(html, base_url)
        out.setdefault("images", [])
        out.setdefault("specs", {})
        return out
    except Exception:
        return {"description": None, "images": [], "specs": {}}
