import re
from datetime import date
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

# Sources expose the brand/model only inside the free-text title, not as a
# structured field. Used to derive brand+model so filters actually work.
BRAND_MODELS = {
    "volkswagen": ["golf", "passat", "tiguan", "polo", "caddy", "touran"],
    "audi": ["a4", "a6", "q5", "a3", "a5", "q7"],
    "bmw": ["320i", "320", "x3", "520", "e60", "m3"],
    "toyota": ["corolla", "yaris", "rav4", "auris", "camry", "avensis"],
    "skoda": ["octavia", "superb", "kodiaq", "fabia", "scala"],
    "mercedes": ["c-class", "e-class", "a-class", "gle"],
    "fiat": ["punto", "panda", "500", "126p", "tipo"],
    "opel": ["astra", "corsa", "zafira", "mokka"],
    "ford": ["focus", "fiesta", "mondeo", "kuga"],
    "renault": ["clio", "megane", "captur", "scenic"],
    "peugeot": ["208", "308", "3008", "partner"],
    "citroen": ["c3", "c4", "c5"],
    "mitsubishi": ["outlander", "lancer", "pajero", "asx"],
    "nissan": ["qashqai", "micra", "x-trail", "juke"],
    "kia": ["ceed", "sportage", "rio", "sportswagon"],
    "hyundai": ["i30", "i20", "tucson", "elantra"],
    "mazda": ["mazda3", "mazda6", "cx-5"],
    "volvo": ["xc60", "v40", "s60"],
    "honda": ["civic", "accord", "cr-v"],
    "seat": ["leon", "ibiza", "ateca"],
    "dacia": ["sandero", "duster", "logan"],
}

BRAND_ALIASES = {
    "vw": "volkswagen",
    "merc": "mercedes",
    "mb": "mercedes",
    "bmw": "bmw",
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


def parse_year(value, now_year: Optional[int] = None) -> Optional[int]:
    if not value:
        return None
    m = re.search(r"(19|20)\d{2}", str(value))
    if not m:
        return None
    y = int(m.group())
    if now_year is None:
        now_year = date.today().year
    return y if y <= now_year + 1 else None


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


def extract_brand_model(title: Optional[str]) -> tuple[str, str]:
    t = _clean(title).lower()
    if not t:
        return "", ""
    # Common abbreviations first (word-bounded so "vw" doesn't match inside other words).
    for alias, canon in BRAND_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", t):
            models = BRAND_MODELS.get(canon, [])
            model = next((m for m in models if m in t), "")
            return canon, model
    for brand, models in BRAND_MODELS.items():
        if brand in t:
            model = next((m for m in models if m in t), "")
            return brand, model
    return "", ""


def normalize(raw: dict) -> Optional[dict]:
    url = _clean(raw.get("url"))
    price = parse_price(raw.get("price"))
    if not url or price is None:
        return None
    brand = _clean(raw.get("brand")).lower()
    model = _clean(raw.get("model")).lower()
    if not brand:
        eb, em = extract_brand_model(raw.get("title"))
        brand = brand or eb
        model = model or em
    title = _clean(raw.get("title")) or f"{brand} {model}".strip()
    return {
        "title": title,
        "brand": brand,
        "model": model,
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
