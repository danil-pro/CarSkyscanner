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


def test_parse_facebook_detail_description_and_gallery():
    html = """
    <html><body>
      <div><span>Написать продавцу</span></div>
      <div><span>Информация о транспортном средстве</span></div>
      <div><p>Sprzedam fajnego peugeota, auto zadbane godne polecenia, jestem pierwszym wlascicielem.
      Przeglad i oc aktualne, olej wymieniony niedawno. Auto uzytkowane na co dzien, w dobrym stanie.
      Wiecej info pod numerem telefonu, zapraszam.</p></div>
      <img src="https://scontent-waw2-1.xx.fbcdn.net/x.jpg" alt='Фото товара "Peugeot"'/>
      <img src="https://scontent-waw2-2.xx.fbcdn.net/y.jpg" alt="Фото товара"/>
      <img src="https://scontent-waw2-1.xx.fbcdn.net/avatar.jpg" alt="Wojciech Serwin"/>
    </body></html>
    """
    out = parse_detail("facebook", html, "https://www.facebook.com")
    assert out["description"] and "Sprzedam" in out["description"]
    assert "Написать продавцу" not in (out["description"] or "")
    # gallery = 2 product photos (alt "Фото товара"), not the seller avatar
    assert len(out["images"]) == 2
    assert all("fbcdn.net" in u for u in out["images"])


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
    # Otomoto's description is in [data-testid="textWrapper"]; the section
    # wrapper also contains the "Pokaż pełny opis" button, which must be excluded.
    html = """
    <html><body>
      <div data-testid="content-description-section"><h3>Opis</h3><button>Pokaż pełny opis</button></div>
      <div data-testid="textWrapper"><p>Na sprzedaz oferuje samochod w bardzo dobrym stanie. Pierwszy wlasciciel,
      bezwypadkowy, regularnie serwisowany w autoryzowanym serwisie. Komplet kluczykow
      oraz dokumentow. Opony zimowe w komplecie. Mozliwosc finansowania.</p></div>
    </body></html>
    """
    out = parse_detail("otomoto", html, "https://www.otomoto.pl")
    assert out["description"] and "Na sprzedaz" in out["description"]
    assert "Pokaż pełny opis" not in (out["description"] or "")


def test_parse_otomoto_detail_gallery_excludes_similar_ads():
    # Gallery photos are in [data-testid="main-gallery"]; the similar-ads
    # section must not leak into the gallery.
    html = """
    <html><body>
      <div data-testid="main-gallery">
        <img data-src="https://ireland.apollo.olxcdn.com/m1.jpg"/>
        <img data-src="https://ireland.apollo.olxcdn.com/m2.jpg"/>
      </div>
      <div data-testid="similar-ads-section">
        <img data-src="https://ireland.apollo.olxcdn.com/similar1.jpg"/>
        <img data-src="https://ireland.apollo.olxcdn.com/similar2.jpg"/>
      </div>
    </body></html>
    """
    out = parse_detail("otomoto", html, "https://www.otomoto.pl")
    assert out["images"] == [
        "https://ireland.apollo.olxcdn.com/m1.jpg",
        "https://ireland.apollo.olxcdn.com/m2.jpg",
    ]
