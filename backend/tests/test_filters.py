from urllib.parse import unquote
from app.schemas import SearchFilters
from scrapers.filters import build_olx_url, build_otomoto_url, build_facebook_url


def test_olx_brand_and_price():
    url = build_olx_url(SearchFilters(brand="volkswagen", price_max=50000))
    dec = unquote(url)
    assert url.startswith("https://www.olx.pl/motoryzacja/samochody/?")
    assert "search[filter_enum_make]=Volkswagen" in dec
    assert "search[filter_float_price:to]=50000" in dec


def test_olx_empty_returns_base():
    assert build_olx_url(SearchFilters()) == "https://www.olx.pl/motoryzacja/samochody/"


def test_otomoto_brand_model_in_path():
    url = build_otomoto_url(SearchFilters(brand="bmw", model="x3", year_min=2018))
    dec = unquote(url)
    assert "/osobowe/bmw/x3" in url
    assert "search[filter_float_year:from]=2018" in dec


def test_facebook_query_and_price():
    url = build_facebook_url(SearchFilters(brand="toyota", model="yaris", price_min=10000))
    assert "query=toyota+yaris" in url
    assert "minPrice=10000" in url
