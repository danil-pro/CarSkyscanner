import asyncio
import pytest

from app.schemas import SearchFilters
from scrapers.providers import ProviderResult
from app.search_orchestrator import SearchOrchestrator


class FakeProvider:
    def __init__(self, source, result):
        self.source = source
        self._result = result

    async def search(self, playwright):
        return self._result


class FakePW:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *a):
        return False


def _orch(providers):
    return SearchOrchestrator(
        provider_factory=lambda filters: providers,
        acquire_playwright=lambda: FakePW(),
    )


# orch.start() schedules the job via asyncio.create_task, which requires a
# running event loop — so these tests are async and run under pytest-asyncio.
@pytest.mark.asyncio
async def test_run_collects_and_marks_done():
    orch = _orch([
        FakeProvider("olx", ProviderResult("olx", listings=[{"source": "olx", "url": "u1", "price": 1.0}], found=1)),
        FakeProvider("otomoto", ProviderResult("otomoto", status="blocked", reason="datadome")),
    ])
    job_id = orch.start(SearchFilters())
    await asyncio.sleep(0.1)
    job = orch.get(job_id)
    assert job.status == "done"
    assert job.per_source["olx"]["status"] == "ok"
    assert job.per_source["otomoto"]["status"] == "blocked"
    assert job.results is not None and len(job.results) == 1


def test_unknown_job_returns_none():
    orch = _orch([])
    assert orch.get("nope") is None


@pytest.mark.asyncio
async def test_provider_timeout_marks_error():
    class Slow:
        source = "olx"

        async def search(self, playwright):
            await asyncio.sleep(10)
            return ProviderResult("olx")

    orch = SearchOrchestrator(
        provider_factory=lambda f: [Slow()],
        acquire_playwright=lambda: FakePW(),
        provider_timeout_s=0.05,
    )
    job_id = orch.start(SearchFilters())
    await asyncio.sleep(0.3)
    job = orch.get(job_id)
    assert job.per_source["olx"]["status"] == "error"
