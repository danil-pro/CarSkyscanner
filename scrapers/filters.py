from urllib.parse import urlencode, quote

FUEL_PL = {
    "petrol": "benzyna", "diesel": "diesel", "hybrid": "hybryda",
    "electric": "elektryczny", "lpg": "lpg",
}

OLX_BASE = "https://www.olx.pl/motoryzacja/samochody/"
OTOMOTO_BASE = "https://www.otomoto.pl/osobowe"
FB_BASE = "https://www.facebook.com/marketplace/search/"


def _fuel_pl(value):
    return FUEL_PL.get(value, value) if value else None


def build_olx_url(f) -> str:
    # OLX encodes make/model as path segments (e.g. .../samochody/volkswagen/golf/),
    # not query params; price/year/fuel stay as search[...] params.
    parts = [OLX_BASE.rstrip("/")]
    if getattr(f, "brand", None):
        parts.append(quote(f.brand))
    if getattr(f, "model", None):
        parts.append(quote(f.model))
    path = "/".join(parts) + "/"
    p = {}
    if f.price_min is not None:
        p["search[filter_float_price:from]"] = int(f.price_min)
    if f.price_max is not None:
        p["search[filter_float_price:to]"] = int(f.price_max)
    if f.year_min is not None:
        p["search[filter_float_year:from]"] = f.year_min
    if f.year_max is not None:
        p["search[filter_float_year:to]"] = f.year_max
    if getattr(f, "fuel_type", None):
        p["search[filter_enum_fuel]"] = _fuel_pl(f.fuel_type)
    return f"{path}?{urlencode(p)}" if p else path


def build_otomoto_url(f) -> str:
    parts = [OTOMOTO_BASE]
    if getattr(f, "brand", None):
        parts.append(quote(f.brand))
    if getattr(f, "model", None):
        parts.append(quote(f.model))
    path = "/".join(parts)
    p = {}
    if f.price_min is not None:
        p["search[filter_float_price:from]"] = int(f.price_min)
    if f.price_max is not None:
        p["search[filter_float_price:to]"] = int(f.price_max)
    if f.year_min is not None:
        p["search[filter_float_year:from]"] = f.year_min
    if f.year_max is not None:
        p["search[filter_float_year:to]"] = f.year_max
    if getattr(f, "fuel_type", None):
        p["search[filter_enum_fuel_type]"] = _fuel_pl(f.fuel_type)
    return f"{path}?{urlencode(p)}" if p else path + "/"


def build_facebook_url(f) -> str:
    q = " ".join(x for x in (getattr(f, "brand", None), getattr(f, "model", None)) if x).strip()
    p = {"exact": "false"}
    if q:
        p["query"] = q
    if f.price_min is not None:
        p["minPrice"] = int(f.price_min)
    if f.price_max is not None:
        p["maxPrice"] = int(f.price_max)
    return f"{FB_BASE}?{urlencode(p)}"
