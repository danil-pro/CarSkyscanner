from datetime import datetime, timezone
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models import Car, CarDetail


def upsert_car(db: Session, data: dict) -> Car:
    existing = db.execute(
        select(Car).where(Car.source == data["source"], Car.url == data["url"])
    ).scalar_one_or_none()
    if existing:
        for k, v in data.items():
            if hasattr(existing, k):
                setattr(existing, k, v)
        db.commit()
        db.refresh(existing)
        return existing
    car = Car(**data)
    db.add(car)
    db.commit()
    db.refresh(car)
    return car


def get_car(db: Session, car_id) -> Car | None:
    return db.get(Car, car_id)


def get_detail(db: Session, car_id) -> CarDetail | None:
    return db.get(CarDetail, car_id)


def upsert_detail(db: Session, car_id, data: dict) -> CarDetail:
    d = db.get(CarDetail, car_id)
    if d is None:
        d = CarDetail(car_id=car_id, description=data.get("description"),
                      images=data.get("images"), status=data.get("status", "ok"))
        db.add(d)
    else:
        d.description = data.get("description")
        d.images = data.get("images")
        d.status = data.get("status", "ok")
        d.fetched_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(d)
    return d


def _apply(filters, q):
    if filters.brand:
        b = f"%{filters.brand.strip()}%"
        q = q.where(Car.brand.ilike(b) | Car.title.ilike(b))
    if filters.model:
        m = f"%{filters.model.strip()}%"
        q = q.where(Car.model.ilike(m) | Car.title.ilike(m))
    if filters.year_min is not None:
        q = q.where(Car.year >= filters.year_min)
    if filters.year_max is not None:
        q = q.where(Car.year <= filters.year_max)
    if filters.price_min is not None:
        q = q.where(Car.price >= filters.price_min)
    if filters.price_max is not None:
        q = q.where(Car.price <= filters.price_max)
    if filters.mileage_max is not None:
        q = q.where(Car.mileage <= filters.mileage_max)
    if filters.fuel_type:
        q = q.where(func.lower(Car.fuel_type) == filters.fuel_type.lower())
    if filters.transmission:
        q = q.where(func.lower(Car.transmission) == filters.transmission.lower())
    return q


def get_cars(db: Session, limit: int = 100, offset: int = 0):
    total = db.scalar(select(func.count()).select_from(Car))
    rows = db.execute(
        select(Car).order_by(Car.created_at.desc()).limit(limit).offset(offset)
    ).scalars().all()
    return rows, total


def search_cars(db: Session, filters, limit: int = 100, offset: int = 0):
    base = select(Car)
    base = _apply(filters, base)
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    rows = db.execute(
        base.order_by(Car.created_at.desc()).limit(limit).offset(offset)
    ).scalars().all()
    return rows, total
