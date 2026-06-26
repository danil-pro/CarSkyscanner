from pathlib import Path
from scrapers.olx import OLXScraper, parse_html

FIX = Path(__file__).parent / "fixtures" / "olx_list.html"


def test_build_url():
    assert "olx.pl" in OLXScraper().build_url()


def test_parse_fixture():
    items = parse_html(FIX.read_text())
    assert len(items) == 2
    assert items[0]["url"].endswith("ID123.html")
    assert "65 000" in items[0]["price"]
    assert items[0]["source"] == "olx"
