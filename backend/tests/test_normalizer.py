from scrapers.normalizer import (
    normalize, parse_price, parse_mileage, parse_year,
    normalize_fuel, normalize_transmission,
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
