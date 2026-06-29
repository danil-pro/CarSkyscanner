from scrapers.olx import parse_html

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
