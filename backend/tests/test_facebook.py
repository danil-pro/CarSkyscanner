import asyncio
from scrapers.facebook import FacebookScraper, FacebookProvider
from scrapers.base import ScrapeResult


def test_facebook_is_stub_blocked():
    scraper = FacebookScraper()

    class FakePlaywright:
        class chromium:
            @staticmethod
            async def launch(headless=True):
                raise AssertionError("stub must not launch a browser")

    res = asyncio.get_event_loop().run_until_complete(scraper.run(FakePlaywright()))
    assert isinstance(res, ScrapeResult)
    assert res.source == "facebook"
    assert res.blocked is True
    assert res.listings == []


def test_provider_summarize_empty_is_no_results():
    res = FacebookProvider._summarize([])
    assert res.status == "no-results"
    assert res.found == 0
    assert res.reason and "0 result links" in res.reason


def test_provider_summarize_some_is_ok():
    res = FacebookProvider._summarize([{"source": "facebook", "url": "u1", "price": 1.0}])
    assert res.status == "ok"
    assert res.found == 1
    assert res.listings and len(res.listings) == 1
