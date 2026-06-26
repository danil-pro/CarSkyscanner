from app.scraper_runner import ScrapeJobManager
from scrapers.base import ScrapeResult


class FakePlaywright:
    """Async context manager that mimics `async_playwright()` without launching a browser."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def test_status_starts_idle():
    m = ScrapeJobManager()
    assert m.status().status == "idle"


async def test_start_then_done_with_mock_scrapers(monkeypatch):
    m = ScrapeJobManager()

    def fake_make_scrapers():
        class S:
            source = "otomoto"

            async def run(self, pw):
                return ScrapeResult(
                    "otomoto",
                    listings=[
                        {
                            "title": "x",
                            "brand": "vw",
                            "model": "g",
                            "year": 2020,
                            "price": 1000,
                            "currency": "PLN",
                            "mileage": 1,
                            "fuel_type": "petrol",
                            "transmission": "manual",
                            "location": "W",
                            "source": "otomoto",
                            "url": "mock1",
                            "image_url": None,
                        }
                    ],
                )

        return [S()]

    monkeypatch.setattr(m, "_make_scrapers", fake_make_scrapers)
    monkeypatch.setattr(m, "_get_playwright", lambda: FakePlaywright())
    start = await m.start()
    assert start.status == "running"
    await m._task  # wait for the background scrape task to finish
    st = m.status()
    assert st.status == "done"
    assert st.per_source["otomoto"].saved == 1


async def test_start_raises_409_when_running():
    from fastapi import HTTPException

    m = ScrapeJobManager()
    m._status.status = "running"
    try:
        await m.start()
        assert False, "expected HTTPException 409"
    except HTTPException as e:
        assert e.status_code == 409
