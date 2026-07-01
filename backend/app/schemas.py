from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict
from typing import Optional


class SearchFilters(BaseModel):
    brand: Optional[str] = None
    model: Optional[str] = None
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    mileage_max: Optional[int] = None
    fuel_type: Optional[str] = None
    transmission: Optional[str] = None


class CarOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    title: Optional[str]
    brand: str
    model: str
    year: Optional[int]
    price: Optional[float]
    currency: str
    mileage: Optional[int]
    fuel_type: Optional[str]
    transmission: Optional[str]
    location: Optional[str]
    source: str
    url: str
    image_url: Optional[str]
    created_at: datetime


class SearchResponse(BaseModel):
    items: list[CarOut]
    total: int
    limit: int
    offset: int


class ScrapeStart(BaseModel):
    job_id: str
    status: str


class SourceResult(BaseModel):
    found: int = 0
    saved: int = 0
    blocked: int = 0
    errors: int = 0


class ScrapeStatus(BaseModel):
    status: str  # idle | running | done | error
    job_id: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    total_saved: int = 0
    per_source: dict[str, SourceResult] = {}


class CarDetailsOut(BaseModel):
    description: Optional[str] = None
    images: list[str] = []
    status: str
    fetched_at: Optional[datetime] = None
