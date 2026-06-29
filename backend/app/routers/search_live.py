from fastapi import APIRouter, Depends, HTTPException

from app import schemas
from app.search_orchestrator import SearchOrchestrator, orchestrator

router = APIRouter()


def get_orchestrator() -> SearchOrchestrator:
    return orchestrator


@router.post("/search/live")
async def start_live(filters: schemas.SearchFilters, orch: SearchOrchestrator = Depends(get_orchestrator)):
    # async so orch.start()'s asyncio.create_task has a running event loop
    job_id = orch.start(filters)
    return {"job_id": job_id, "status": "running"}


@router.get("/search/live/{job_id}")
def get_live(job_id: str, orch: SearchOrchestrator = Depends(get_orchestrator)):
    job = orch.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job.to_dict()
