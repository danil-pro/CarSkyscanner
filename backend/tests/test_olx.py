from pathlib import Path
from scrapers.olx import OLXScraper, parse_html

FIX = Path(__file__).parent / "fixtures" / "olx_list.html"


def test_build_url():
    assert "olx.pl" in OLXScraper().build_url()


def test_parse_fixture():
    items = parse_html(FIX.read_text())
    assert len(items) == 2
    first = items[0]
    assert first["url"].endswith("ID123.html")
    assert "65 000" in first["price"]
    assert first["source"] == "olx"
    # Title now comes from [data-cy="ad-card-title"]: clean, without the
    # "Odświeżono ... km Obserwuj" chrome the old h6 fallback produced.
    assert first["title"] == "Opel Astra 2017"
    # Location parsed from the location-date element.
    assert first["location"] == "Warszawa"
    # Only a real car photo (apollo.olxcdn) is kept.
    assert "apollo.olxcdn" in first["image_url"]
