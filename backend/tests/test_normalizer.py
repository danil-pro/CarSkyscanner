from scrapers.normalizer import (
    normalize, parse_price, parse_mileage, parse_year,
    normalize_fuel, normalize_transmission, extract_body_type,
)


def test_parse_price_handles_polish_format():
    assert parse_price("89 900 PLN") == 89900.0
    assert parse_price("1 234 567,99 zł") == 1234567.99
    assert parse_price(None) is None


def test_parse_mileage_handles_tys():
    assert parse_mileage("150 tys. km") == 150000
    assert parse_mileage("12 345 km") == 12345
    assert parse_mileage(None) is None


def test_parse_year():
    assert parse_year("2018") == 2018
    assert parse_year("Rok produkcji: 2015") == 2015
    assert parse_year("abc") is None


def test_normalize_fuel_maps_variants():
    assert normalize_fuel("Benzyna") == "petrol"
    assert normalize_fuel("Diesel") == "diesel"
    assert normalize_fuel("Elektryczny") == "electric"
    assert normalize_fuel("Hybryda") == "hybrid"
    assert normalize_fuel("LPG") == "lpg"
    assert normalize_fuel("Cosmic") == "other"


def test_normalize_transmission():
    assert normalize_transmission("Skrzynia manualna") == "manual"
    assert normalize_transmission("Automatyczna") == "automatic"
    assert normalize_transmission(None) is None


def test_normalize_produces_canonical_dict():
    raw = {
        "title": "VW Golf", "brand": " Volkswagen ", "model": "GOLF",
        "year": "2018", "price": "89 900 PLN", "mileage": "150 tys. km",
        "fuel_type": "Benzyna", "transmission": "Manualna",
        "location": "Warszawa", "source": "otomoto",
        "url": "https://otomoto.pl/x", "image_url": "https://img/x.jpg",
    }
    out = normalize(raw)
    assert out["brand"] == "volkswagen"
    assert out["model"] == "golf"
    assert out["price"] == 89900.0
    assert out["mileage"] == 150000
    assert out["year"] == 2018
    assert out["fuel_type"] == "petrol"
    assert out["transmission"] == "manual"
    assert out["currency"] == "PLN"


def test_normalize_rejects_missing_url_or_price():
    assert normalize({"title": "x", "price": "10", "source": "olx", "url": ""}) is None
    assert normalize({"title": "x", "price": None, "source": "olx", "url": "u"}) is None


def test_parse_year_rejects_future_years():
    # Guard rejects years beyond next model year (now_year + 1): 2028 and 2099 are future.
    assert parse_year("2028", now_year=2026) is None
    assert parse_year("2099", now_year=2026) is None
    # now_year + 1 (2027) is allowed — a plausible next-year model. now_year (2026) is allowed too.
    # (This proves the guard alone does NOT fix the 2026 date bug — anchoring in Tasks 2-3 does.)
    assert parse_year("2027", now_year=2026) == 2027
    assert parse_year("2026", now_year=2026) == 2026
    assert parse_year("2019", now_year=2026) == 2019
    assert parse_year(None) is None


def test_extract_body_type_from_title():
    assert extract_body_type("Volkswagen Golf kombi 2018") == "kombi"
    assert extract_body_type("Audi Q5 SUV") == "suv"
    assert extract_body_type("Mazda MX-5 cabrio") == "cabrio"
    assert extract_body_type("Toyota Yaris hatchback") == "hatchback"
    assert extract_body_type("Skoda Octavia sedan") == "sedan"
    assert extract_body_type("Toyota Yaris 2018") is None


def test_normalize_includes_body_type():
    n = normalize({"title": "Golf kombi 1.6", "url": "u", "price": "1000"})
    assert n and n["body_type"] == "kombi"


def test_normalize_body_type_value():
    from scrapers.normalizer import normalize_body_type_value
    assert normalize_body_type_value("Kompakt") == "hatchback"
    assert normalize_body_type_value("SUV") == "suv"
    assert normalize_body_type_value("Kombi") == "kombi"
    assert normalize_body_type_value("Cabrio") == "cabrio"
    assert normalize_body_type_value(None) is None
