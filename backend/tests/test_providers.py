from urllib.parse import unquote
from scrapers.olx import parse_html
from app.schemas import SearchFilters
from scrapers.base import ScrapeResult
from scrapers.providers import OLXProvider, OtomotoProvider, ProviderResult, _from_scrape

OLX_CARD_OTOMOTO_LINK = """
<html><body>
<div data-cy="l-card">
  <a href="/d/oferta/vw-golf-CID5-ID1.html"><h6>VW Golf</h6></a>
  <span data-testid="ad-price">50 000 zł</span>
  <img data-src="https://ireland.apollo.olxcdn.com:443/v1/files/abc/image"/>
  <p>2018 · 150 000 km · Benzyna</p>
</div>
<div data-cy="l-card">
  <a href="https://www.otomoto.pl/osobowe/vw-golf-ID123.html"><h6>VW Golf</h6></a>
  <span data-testid="ad-price">60 000 zł</span>
  <img data-src="https://ireland.apollo.olxcdn.com:443/v1/files/def/image"/>
  <p>2019 · 120 000 km · Diesel</p>
</div>
</body></html>
"""


def test_olx_parse_source_by_domain():
    listings = parse_html(OLX_CARD_OTOMOTO_LINK)
    assert len(listings) == 2
    assert listings[0]["source"] == "olx"
    assert listings[1]["source"] == "otomoto"  # cross-listed otomoto ad
    assert listings[1]["url"].startswith("https://www.otomoto.pl/")


def test_olx_provider_builds_filtered_url():
    p = OLXProvider(SearchFilters(brand="volkswagen"))
    assert "search[filter_enum_make]=Volkswagen" in unquote(p.build_url())
    assert p.source == "olx"


def test_otomoto_provider_builds_filtered_url():
    p = OtomotoProvider(SearchFilters(brand="audi", model="a4"))
    assert "/osobowe/audi/a4" in p.build_url()


def test_from_scrape_blocked():
    r = _from_scrape("otomoto", ScrapeResult("otomoto", blocked=True, reason="blocked-marker:datadome"))
    assert r.status == "blocked" and r.source == "otomoto" and r.found == 0


def test_from_scrape_ok():
    r = _from_scrape("olx", ScrapeResult("olx", listings=[{"x": 1}]))
    assert r.status == "ok" and r.found == 1
