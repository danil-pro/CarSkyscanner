from scrapers.details import parse_detail


def test_parse_olx_detail():
    html = """
    <html><body>
      <div data-cy="ad_description"><p>Auto w stanie idealnym. Pierwszy właściciel.</p></div>
      <div class="swiper-zoom-container"><img data-src="https://ireland.apollo.olxcdn.com/a.jpg"/></div>
      <div class="swiper-zoom-container"><img data-src="https://ireland.apollo.olxcdn.com/b.jpg"/></div>
      <div class="css-gl6djm"><img data-src="https://ireland.apollo.olxcdn.com/recommended.jpg"/></div>
    </body></html>
    """
    out = parse_detail("olx", html, "https://www.olx.pl")
    assert "idealnym" in (out["description"] or "").lower()
    # Only the gallery images — not the "Zobacz też" recommended-section one.
    assert out["images"] == ["https://ireland.apollo.olxcdn.com/a.jpg", "https://ireland.apollo.olxcdn.com/b.jpg"]


def test_parse_unknown_source_returns_empty_without_raising():
    out = parse_detail("mysource", "<html></html>", "https://x")
    assert out == {"description": None, "images": [], "specs": {}}


def test_parse_olx_detail_filters_non_car_images():
    # App Store / Google Play badges and site logos live on other hosts; only
    # real car photos (apollo.olxcdn) must end up in the gallery.
    html = """
    <html><body>
      <div data-cy="ad_description"><p>Piekny samochod w stanie idealnym, pierwszy wlasciciel.</p></div>
      <img src="https://ireland.apollo.olxcdn.com/real1.jpg"/>
      <img src="/static/app-store-badge.png"/>
      <img src="https://play.google.com/store/badge.png"/>
      <img src="https://ireland.apollo.olxcdn.com/real2.jpg"/>
    </body></html>
    """
    out = parse_detail("olx", html, "https://www.olx.pl")
    assert out["images"] == [
        "https://ireland.apollo.olxcdn.com/real1.jpg",
        "https://ireland.apollo.olxcdn.com/real2.jpg",
    ]


def test_parse_olx_detail_extracts_specs():
    html = """
    <html><body>
      <p>Skrzynia biegów: Manualna</p>
      <p>Paliwo: Diesel</p>
      <p>Przebieg: 187 000 km</p>
      <p>Moc silnika: 110 KM</p>
      <script type="application/ld+json">{"@type":"Vehicle","brand":"Opel","color":"Czerwony"}</script>
    </body></html>
    """
    out = parse_detail("olx", html, "https://www.olx.pl")
    s = out["specs"]
    assert s.get("Skrzynia biegów") == "Manualna"
    assert s.get("Paliwo") == "Diesel"
    assert s.get("Moc silnika") == "110 KM"
    assert s.get("Marka") == "Opel"
    assert s.get("Kolor") == "Czerwony"


def test_parse_otomoto_detail_description_fallback():
    # Otomoto's description has no stable selector; fall back to the longest
    # text block when the known selectors miss.
    html = """
    <html><body>
      <div data-testid="content-container"></div>
      <div><p>Na sprzedaz oferuje samochod w bardzo dobrym stanie. Pierwszy wlasciciel,
      bezwypadkowy, regularnie serwisowany w autoryzowanym serwisie. Komplet kluczykow
      oraz dokumentow. Opony zimowe w komplecie. Mozliwosc finansowania.</p></div>
    </body></html>
    """
    out = parse_detail("otomoto", html, "https://www.otomoto.pl")
    assert out["description"] and "Na sprzedaz" in out["description"]
