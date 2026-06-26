from pathlib import Path
from scrapers.otomoto import OtomotoScraper

FIX = Path(__file__).parent / "fixtures" / "otomoto_list.html"


def test_build_url_with_brand():
    url = OtomotoScraper(brand="volkswagen").build_url()
    assert "otomoto.pl" in url and "volkswagen" in url


def test_parse_fixture_extracts_two_listings():
    # parse_html is a sync pure helper extracted from parse_page for testability
    from scrapers.otomoto import parse_html
    items = parse_html(FIX.read_text())
    assert len(items) == 2
    first = items[0]
    assert first["url"].endswith("/id/1")
    assert "89 900 PLN" in first["price"]
    assert first["source"] == "otomoto"
