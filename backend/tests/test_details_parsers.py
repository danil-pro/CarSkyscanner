from scrapers.details import parse_detail


def test_parse_olx_detail():
    html = """
    <html><body>
      <div data-cy="ad_description"><p>Auto w stanie idealnym. Pierwszy właściciel.</p></div>
      <img data-src="https://ireland.apollo.olxcdn.com/a.jpg"/>
      <img data-src="https://ireland.apollo.olxcdn.com/b.jpg"/>
    </body></html>
    """
    out = parse_detail("olx", html, "https://www.olx.pl")
    assert "idealnym" in (out["description"] or "").lower()
    assert out["images"] == ["https://ireland.apollo.olxcdn.com/a.jpg", "https://ireland.apollo.olxcdn.com/b.jpg"]


def test_parse_unknown_source_returns_empty_without_raising():
    out = parse_detail("mysource", "<html></html>", "https://x")
    assert out == {"description": None, "images": []}
