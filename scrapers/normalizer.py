import re
from typing import Optional

FUEL_MAP = {
    "benzyna": "petrol", "benzynowy": "petrol", "petrol": "petrol",
    "diesel": "diesel", "olej napędowy": "diesel",
    "lpg": "lpg", "autogas": "lpg",
    "hybryda": "hybrid", "hybrid": "hybrid", "hybrydowy": "hybrid",
    "elektryczny": "electric", "elektryczne": "electric", "electric": "electric",
}
TRANSMISSION_MAP = {
    "manual": "manual", "manualna": "manual", "skrzynia manualna": "manual",
    "automat": "automatic", "automatyczna": "automatic", "automatic": "automatic",
}


def parse_price(value) -> Optional[float]:
    if not value:
        return None
    s = str(value).lower().replace("\xa0", " ").replace("zł", "").replace("pln", "")
    s = s.replace(" ", "").replace(",", ".")
    m = re.search(r"\d+(?:\.\d+)?", s)
    return float(m.group()) if m else None


def parse_mileage(value) -> Optional[int]:
    if not value:
        return None
    s = str(value).lower().replace("\xa0", " ").replace("km", "").strip()
    if "tys" in s:
        m = re.search(r"[\d.,]+", s)
        return int(float(m.group().replace(",", ".")) * 1000) if m else None
    m = re.search(r"\d+", s.replace(" ", ""))
    return int(m.group()) if m else None


def parse_year(value) -> Optional[int]:
    if not value:
        return None
    m = re.search(r"(19|20)\d{2}", str(value))
    return int(m.group()) if m else None


def normalize_fuel(value) -> str:
    key = str(value or "").strip().lower()
    return FUEL_MAP.get(key, "other")


def normalize_transmission(value) -> Optional[str]:
    if not value:
        return None
    key = str(value).strip().lower()
    for k, v in TRANSMISSION_MAP.items():
        if k in key:
            return v
    return None


def _clean(s) -> str:
    return str(s or "").strip()


def normalize(raw: dict) -> Optional[dict]:
    url = _clean(raw.get("url"))
    price = parse_price(raw.get("price"))
    if not url or price is None:
        return None
    return {
        "title": _clean(raw.get("title")) or None,
        "brand": _clean(raw.get("brand")).lower(),
        "model": _clean(raw.get("model")).lower(),
        "year": parse_year(raw.get("year")),
        "price": price,
        "currency": "PLN",
        "mileage": parse_mileage(raw.get("mileage")),
        "fuel_type": normalize_fuel(raw.get("fuel_type")),
        "transmission": normalize_transmission(raw.get("transmission")),
        "location": _clean(raw.get("location")) or None,
        "source": _clean(raw.get("source")).lower(),
        "url": url,
        "image_url": _clean(raw.get("image_url")) or None,
    }
