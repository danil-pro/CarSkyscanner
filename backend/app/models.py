import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Numeric, Index, Uuid, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Car(Base):
    __tablename__ = "cars"

    # Portable UUID: native in Postgres, CHAR(36) in SQLite (tests).
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String, nullable=False)
    brand: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=True)
    price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="PLN")
    mileage: Mapped[int] = mapped_column(Integer, nullable=True)
    fuel_type: Mapped[str] = mapped_column(String(32), nullable=True)
    transmission: Mapped[str] = mapped_column(String(32), nullable=True)
    body_type: Mapped[str] = mapped_column(String(32), nullable=True)
    location: Mapped[str] = mapped_column(String, nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)
    image_url: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_now, nullable=False)

    details: Mapped["CarDetail"] = relationship(back_populates="car", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_cars_brand", "brand"),
        Index("ix_cars_model", "model"),
        Index("ix_cars_price", "price"),
        Index("ix_cars_year", "year"),
        Index("uq_cars_source_url", "source", "url", unique=True),
    )


class CarDetail(Base):
    __tablename__ = "car_details"
    car_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("cars.id"), primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    images: Mapped[list] = mapped_column(JSON, nullable=True)
    specs: Mapped[dict] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ok")
    fetched_at: Mapped[datetime] = mapped_column(default=_now, nullable=False)

    car: Mapped["Car"] = relationship(back_populates="details")
