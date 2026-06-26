from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app import crud, schemas

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
