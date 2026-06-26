import asyncio
from scrapers.facebook import FacebookScraper
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
