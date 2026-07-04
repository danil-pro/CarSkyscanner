from pathlib import Path
from scrapers.otomoto import OtomotoScraper, parse_html

FIX = Path(__file__).parent / "fixtures" / "otomoto_list.html"


def test_build_url_with_brand():
    url = OtomotoScraper(brand="volkswagen").build_url()
    assert "otomoto.pl" in url and "volkswagen" in url


def test_parse_fixture_extracts_two_listings():
    items = parse_html(FIX.read_text())
    assert len(items) == 2
    first = items[0]
    assert "/oferta/" in first["url"]
    assert first["source"] == "otomoto"
    # Current Otomoto cards: title in <h2>, price in <h3>, params in <dd>.
    assert first["title"] == "Hyundai Veloster 1.6 Turbo"
    assert first["price"] == "89 900"
    assert first["year"] == "2019"
    assert first["fuel_type"] == "Benzyna"
    assert first["transmission"] == "Manualna"
    assert first["mileage"] == "99 995 km"
    assert "Warszawa" in first["location"]
    assert "apollo.olxcdn" in first["image_url"]
