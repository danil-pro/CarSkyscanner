from urllib.parse import unquote
from scrapers.olx import parse_html
from app.schemas import SearchFilters
from scrapers.base import ScrapeResult
from scrapers.providers import OLXProvider, OtomotoProvider, ProviderResult, _from_scrape
from scrapers.facebook import FacebookProvider

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
    assert "samochody/volkswagen/" in p.build_url()
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


def test_facebook_not_configured(tmp_path):
    import asyncio
    p = FacebookProvider(SearchFilters(brand="toyota"), storage_state_path=str(tmp_path / "missing.json"))
    res = asyncio.run(p.search(playwright=None))
    assert res.status == "session-not-configured"
    assert res.source == "facebook"


def test_facebook_parses_listings_from_json(tmp_path):
    # FB results live in embedded GraphQL JSON now, not <a> anchors.
    payload = {
        "data": {"marketplace_search": {"nodes": [
            {"__typename": "GroupCommerceProductItem", "id": "111",
             "marketplace_listing_title": "Toyota Yaris 2019",
             "listing_price": {"formatted_amount": "50 000 zł"},
             "primary_listing_photo": {"image": {"uri": "https://scontent.xx.fbcdn.net/a.jpg"}},
             "location": {"reverse_geocode": {"city": "Warszawa"}}},
            {"__typename": "GroupCommerceProductItem", "id": "222",
             "marketplace_listing_title": "Honda Civic",
             "listing_price": {"formatted_amount": "40 000 zł"},
             "primary_listing_photo": {"image": {"uri": "https://scontent.xx.fbcdn.net/b.jpg"}},
             "location": {"reverse_geocode": {"city": "Kraków"}}},
        ]}}
    }
    import json as _json
    html = f'<html><body><script type="application/json">{_json.dumps(payload)}</script></body></html>'
    p = FacebookProvider(SearchFilters(), storage_state_path=str(tmp_path / "x.json"))
    listings = p._parse(html)
    assert len(listings) == 2
    assert listings[0]["source"] == "facebook"
    assert listings[0]["url"] == "https://www.facebook.com/marketplace/item/111/"
    assert listings[0]["title"] == "Toyota Yaris 2019"
    assert listings[0]["location"] == "Warszawa"
    assert listings[0]["image_url"] == "https://scontent.xx.fbcdn.net/a.jpg"


def test_facebook_parse_then_normalize_price(tmp_path):
    # Regression: FB listings must go through normalize() so price is parsed
    # (raw "50 000 zł" string -> 50000.0 for the Numeric column).
    from scrapers.normalizer import normalize
    import json as _json
    payload = {"data": {"x": {"__typename": "GroupCommerceProductItem", "id": "9",
        "marketplace_listing_title": "Toyota Yaris 2019",
        "listing_price": {"formatted_amount": "50 000 zł"},
        "primary_listing_photo": {"image": {"uri": "https://scontent.xx.fbcdn.net/c.jpg"}}}}}
    html = f'<html><body><script type="application/json">{_json.dumps(payload)}</script></body></html>'
    p = FacebookProvider(SearchFilters(), storage_state_path=str(tmp_path / "x.json"))
    raw = p._parse(html)[0]
    n = normalize(raw)
    assert n is not None
    assert n["price"] == 50000.0
    assert n["source"] == "facebook"
    assert n["url"] == "https://www.facebook.com/marketplace/item/9/"


def test_olx_parse_year_ignores_listing_date():
    # Real OLX shape: a listing date "... 31 maja 2026" precedes the real "2019 - 110 480 km".
    html = """
    <html><body>
    <div data-cy="l-card">
      <a href="/d/oferta/vw-polo-ID1.html"><h6>VW Polo</h6></a>
      <span data-testid="ad-price">55 999 zł</span>
      <p>Przysucha - 31 maja 2026 2019 - 110 480 km Benzyna</p>
    </div>
    </body></html>
    """
    listings = parse_html(html)
    assert listings[0]["year"] == "2019"


def test_otomoto_parse_year_picks_year_not_price():
    from scrapers.otomoto import parse_html
    # dd[0] is the price; the bare year '2008' is later. dds[0] used to win with a stray token.
    html = """
    <html><body>
    <article>
      <a href="/osobowe/oferta/peugeot-207-ID1.html"></a>
      <h3>4 200</h3>
      <dd>4 200 PLN</dd><dd>2008</dd><dd>Benzyna</dd><dd>Manualna</dd><dd>150 tys. km</dd><dd>Warszawa</dd>
    </article>
    </body></html>
    """
    listings = parse_html(html)
    assert listings[0]["year"] == "2008"
