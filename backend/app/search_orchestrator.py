import asyncio
import uuid
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

from app.config import settings
from app.crud import upsert_car
from app.database import SessionLocal
from app.schemas import CarOut, SearchFilters
from scrapers.providers import OLXProvider, OtomotoProvider, ProviderResult
from scrapers.facebook import FacebookProvider


def default_provider_factory(filters: SearchFilters):
    providers = []
    for src in settings.enabled_sources:
        if src == "olx":
            providers.append(OLXProvider(filters))
        elif src == "otomoto":
            providers.append(OtomotoProvider(filters))
        elif src == "facebook":
            providers.append(FacebookProvider(filters, settings.FB_STORAGE_STATE_PATH))
    return providers


def _default_acquire_playwright():
    from playwright.async_api import async_playwright
    return async_playwright()


class LiveSearchJob:
    def __init__(self, job_id: str, filters: SearchFilters):
        self.job_id = job_id
        self.filters = filters
        self.status = "running"
        self.per_source: dict[str, dict] = {}
        self.results: Optional[list[dict]] = None
        self.error: Optional[str] = None
        self.started_at = datetime.now(timezone.utc)
        self.finished_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "per_source": self.per_source,
            "results": self.results,
            "error": self.error,
        }


class SearchOrchestrator:
    def __init__(
        self,
        provider_factory: Callable[[SearchFilters], list] = default_provider_factory,
        acquire_playwright: Callable[[], Awaitable] = _default_acquire_playwright,
        provider_timeout_s: Optional[int] = None,
        job_timeout_s: Optional[int] = None,
    ):
        self._provider_factory = provider_factory
        self._acquire_playwright = acquire_playwright
        self._provider_timeout_s = provider_timeout_s or settings.SEARCH_PROVIDER_TIMEOUT_S
        self._job_timeout_s = job_timeout_s or settings.SEARCH_JOB_TIMEOUT_S
        self._jobs: dict[str, LiveSearchJob] = {}

    def start(self, filters: SearchFilters) -> str:
        job_id = str(uuid.uuid4())
        job = LiveSearchJob(job_id, filters)
        for p in self._provider_factory(filters):
            job.per_source[p.source] = {"status": "pending", "found": 0, "reason": None}
        self._jobs[job_id] = job
        asyncio.create_task(self._run(job))
        return job_id

    def get(self, job_id: str) -> Optional[LiveSearchJob]:
        return self._jobs.get(job_id)

    async def _run(self, job: LiveSearchJob):
        providers = self._provider_factory(job.filters)
        try:
            async def scrape():
                async with self._acquire_playwright() as pw:
                    async def run_one(p):
                        try:
                            res = await asyncio.wait_for(p.search(pw), timeout=self._provider_timeout_s)
                        except asyncio.TimeoutError:
                            res = ProviderResult(p.source, status="error", reason="timeout")
                        except Exception as e:  # never let one provider sink the job
                            res = ProviderResult(p.source, status="error", reason=f"error: {e}")
                        job.per_source[p.source] = {
                            "status": res.status, "found": res.found,
                            "reason": res.reason, "saved": 0,
                        }
                        return res
                    return await asyncio.gather(*(run_one(p) for p in providers))

            try:
                results = await asyncio.wait_for(scrape(), timeout=self._job_timeout_s)
            except asyncio.TimeoutError:
                job.status = "error"
                job.error = "job timeout"
                return

            collected = []
            db = SessionLocal()
            try:
                for res in results:
                    for listing in res.listings:
                        try:
                            saved = upsert_car(db, listing)
                        except Exception:
                            # Un-savable listing: skip it. It has no DB id, so the
                            # frontend couldn't open it anyway (this was producing
                            # /cars/undefined links -> 404).
                            continue
                        if res.source in job.per_source:
                            slot = job.per_source[res.source]
                            slot["saved"] = slot.get("saved", 0) + 1
                        # Return the saved Car (with id), not the raw listing dict
                        # (which lacks id and produced /cars/undefined links).
                        collected.append(CarOut.model_validate(saved).model_dump(mode="json"))
            finally:
                db.close()
            job.results = collected
            job.status = "done"
        except Exception as e:
            job.status = "error"
            job.error = str(e)
        finally:
            job.finished_at = datetime.now(timezone.utc)


orchestrator = SearchOrchestrator()
