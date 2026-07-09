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


def test_parse_skips_dealer_showcase_cards():
    # "Wyróżniony Sprzedawca" cards bundle several listings (specs in <li>, no
    # <dd>, multiple /oferta/ links) — they must be skipped, not emitted as a
    # garbage entry with no year/fuel/transmission.
    html = """
    <html><body>
    <article>
      <h2><a href="/osobowe/oferta/real-ID1.html">Audi A4</a></h2>
      <h3>45 000</h3>
      <dd>210 000 km</dd><dd>Diesel</dd><dd>Automatyczna</dd><dd>2014</dd>
      <p>Kraków (Małopolskie)</p>
    </article>
    <article>
      <a href="/osobowe/oferta/showcase-ID2.html"></a>
      <span>Wyróżniony Sprzedawca</span>
      <a href="/osobowe/oferta/sub-ID3.html">Volkswagen California</a>
      <li>2025</li><li>11 km</li><li>Diesel</li>
      <p>339 990 PLN</p>
      <span>Zobacz ogłoszenia</span>
    </article>
    </body></html>
    """
    items = parse_html(html)
    assert len(items) == 1
    assert items[0]["title"] == "Audi A4"
    assert all("showcase" not in i["url"] for i in items)
