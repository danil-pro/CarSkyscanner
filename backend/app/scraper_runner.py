import asyncio
import uuid
from datetime import datetime, timezone

from app import schemas
from app.crud import upsert_car
from app.database import SessionLocal
from scrapers.base import BaseScraper
from scrapers.otomoto import OtomotoScraper
from scrapers.olx import OLXScraper
from scrapers.facebook import FacebookScraper


def _now():
    return datetime.now(timezone.utc)


class ScrapeJobManager:
    """In-memory scrape job lifecycle + orchestration."""

    def __init__(self):
        self._status = schemas.ScrapeStatus(status="idle", per_source={})
        self._task: asyncio.Task | None = None

    def status(self) -> schemas.ScrapeStatus:
        return self._status

    def _make_scrapers(self) -> list[BaseScraper]:
        return [OtomotoScraper(), OLXScraper(), FacebookScraper()]

    def _get_playwright(self):
        from playwright.async_api import async_playwright

        return async_playwright()

    async def start(self) -> schemas.ScrapeStart:
        from fastapi import HTTPException

        if self._status.status == "running":
            raise HTTPException(status_code=409, detail="a scrape is already running")
        job_id = str(uuid.uuid4())
        self._status = schemas.ScrapeStatus(
            status="running",
            job_id=job_id,
            started_at=_now(),
            per_source={
                s.source: schemas.SourceResult() for s in self._make_scrapers()
            },
        )
        self._task = asyncio.create_task(self._run(job_id))
        return schemas.ScrapeStart(job_id=job_id, status="running")

    async def _run(self, job_id: str):
        try:
            scrapers = self._make_scrapers()
            async with self._get_playwright() as pw:
                for scraper in scrapers:
                    result = await scraper.run(pw)
                    sr = self._status.per_source.setdefault(
                        scraper.source, schemas.SourceResult()
                    )
                    if result.blocked:
                        sr.blocked += 1
                        if "error" in (result.reason or ""):
                            sr.errors += 1
                        continue
                    sr.found += len(result.listings)
                    db = SessionLocal()
                    try:
                        for listing in result.listings:
                            upsert_car(db, listing)
                            sr.saved += 1
                    finally:
                        db.close()
            self._status.status = "done"
        except Exception:
            self._status.status = "error"
        finally:
            self._status.finished_at = _now()
            self._status.total_saved = sum(
                s.saved for s in self._status.per_source.values()
            )


manager = ScrapeJobManager()
