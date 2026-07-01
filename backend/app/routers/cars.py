import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app import crud, detail_service, schemas
from app.config import settings

router = APIRouter()


@router.get("/cars", response_model=schemas.SearchResponse)
def list_cars(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
              db: Session = Depends(get_db)):
    rows, total = crud.get_cars(db, limit=limit, offset=offset)
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


@router.post("/search", response_model=schemas.SearchResponse)
def search(filters: schemas.SearchFilters,
           limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
           db: Session = Depends(get_db)):
    rows, total = crud.search_cars(db, filters, limit=limit, offset=offset)
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


@router.get("/cars/{car_id}", response_model=schemas.CarOut)
def get_car(car_id: uuid.UUID, db: Session = Depends(get_db)):
    car = crud.get_car(db, car_id)
    if car is None:
        raise HTTPException(status_code=404, detail="car not found")
    return car


# Sync (not async): detail_service.fetch_details() calls asyncio.run() internally,
# which cannot run inside an already-running event loop. FastAPI runs sync
# endpoints in a threadpool (no running loop), so asyncio.run works here.
@router.get("/cars/{car_id}/details", response_model=schemas.CarDetailsOut)
def car_details(car_id: uuid.UUID, db: Session = Depends(get_db)):
    car = crud.get_car(db, car_id)
    if car is None:
        raise HTTPException(status_code=404, detail="car not found")
    cached = crud.get_detail(db, car_id)
    if cached and cached.fetched_at:
        fetched = cached.fetched_at
        if fetched.tzinfo is None:          # SQLite may drop tzinfo; normalize before subtract
            fetched = fetched.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - fetched <= timedelta(seconds=settings.DETAILS_TTL_S):
            return cached
    data = detail_service.fetch_details(car)  # graceful: never raises
    return crud.upsert_detail(db, car_id, data)
