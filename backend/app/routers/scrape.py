from fastapi import APIRouter

from app.scraper_runner import manager

router = APIRouter(prefix="/scrape", tags=["scrape"])


@router.post("/run", status_code=202)
async def run():
    return await manager.start()


@router.get("/status")
def status():
    return manager.status()
