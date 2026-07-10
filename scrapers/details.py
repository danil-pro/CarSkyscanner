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


def _gallery_images(soup, base_url: str, gallery_selectors: tuple[str, ...]) -> list[str]:
    """Photos scoped to the listing's gallery. The detail page also shows a
    'similar/recommended' section (Otomoto: similar-ads-section; OLX: Zobacz też)
    whose apollo images are unrelated listings — scope to the gallery only,
    falling back to the whole page when no gallery container is found."""
    for sel in gallery_selectors:
        nodes = soup.select(sel)
        if nodes:
            images, seen = [], set()
            for node in nodes:
                for u in _images(node, base_url):
                    if u not in seen:
                        seen.add(u)
                        images.append(u)
            if images:
                return images
    return _images(soup, base_url)


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
        "images": _gallery_images(soup, base_url, (".swiper-zoom-container",)),
        "specs": _specs_olx(soup),
    }


def _longest_text_block(soup, min_len: int = 200, max_len: int = 6000) -> Optional[str]:
    """Fallback description: the longest leaf-ish text block on the page."""
    best = ""
    for el in soup.find_all(["div", "section", "article"]):
        t = el.get_text(" ", strip=True)
        if min_len <= len(t) <= max_len and len(el.find_all(["div", "section"])) < 4 and len(t) > len(best):
            best = t
    return best[:5000] if best else None


def _parse_otomoto(html: str, base_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    # Description lives in [data-testid="textWrapper"]; content-description-section
    # also bundles the "Opis"/"Zgłoś" headings and the "Pokaż pełny opis" button,
    # so prefer textWrapper. Longest-block is a last resort (it can grab legal/
    # cookie text), hence last.
    desc = _description(soup, (
        '[data-testid="textWrapper"]',
        '[data-testid="content-description-section"]',
        '[data-testid="content-container"]',
        'div[data-role="offer-description"]',
        '#description',
    )) or _longest_text_block(soup)
    return {
        "description": desc,
        "images": _gallery_images(soup, base_url, ('[data-testid="main-gallery"]', '[data-testid="photo-gallery"]')),
        "specs": _specs_otomoto(soup),
    }


_FB_UI_MARKERS = (
    "написать продавцу", "подробнее о покупке", "сохранить", "поделиться",
    "выбор дня", "информация о продавце", "на facebook", "реклама",
    "отправить сообщение", "показать перевод", "информация о транспортном средстве",
)


def _fb_description(soup) -> Optional[str]:
    """Seller description: longest leaf-ish block with offer language, no UI chrome."""
    best = ""
    for el in soup.find_all(["div", "span"]):
        t = el.get_text(" ", strip=True)
        if (120 < len(t) < 3000 and len(el.find_all(["div"])) < 4
                and any(w in t.lower() for w in
                        ["sprzed", "samoch", "auto", "olej", "przegl", "stanie",
                         "rozrząd", "kup", "rasz", "więcej info", "первый влад"])
                and not any(u in t.lower() for u in _FB_UI_MARKERS)):
            if len(t) > len(best):
                best = t
    return best[:5000] if best else None


def _fb_gallery_images(soup) -> list[str]:
    """FB listing photos: fbcdn images whose alt marks them as product photos
    (avoids seller avatars, icons and 'Выбор дня' thumbnails, which are also fbcdn)."""
    seen, out = set(), []
    for im in soup.select("img"):
        src = im.get("src") or im.get("data-src") or ""
        alt = (im.get("alt") or "").lower()
        if "fbcdn.net" in src and ("фото" in alt or "photo" in alt):
            if src not in seen:
                seen.add(src)
                out.append(src)
    return out


def _parse_facebook(html: str, base_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    return {
        "description": _fb_description(soup),
        "images": _fb_gallery_images(soup),
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
