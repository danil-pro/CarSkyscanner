# Car Aggregator MVP — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working car-listing aggregator MVP for the Polish market (Otomoto + OLX + Facebook stub) with search, scraping, and a unified UI, runnable via `docker compose up --build`.

**Architecture:** Monorepo. FastAPI backend (sync SQLAlchemy + Postgres) imports `scrapers/` as a package; scraping runs in-process via `asyncio` with a status endpoint. Next.js frontend (client-side, App Router) talks to the API. Three Docker containers (postgres/backend/frontend). Seed data guarantees a working UI regardless of live-scrape blocks.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, PostgreSQL 15, Playwright, Next.js 14 (App Router), TailwindCSS, Docker Compose v2.

## Global Constraints

- Python runtime pinned to **3.11** in the backend Docker image (`python:3.11-slim`); Playwright browsers installed in that image.
- Database is **PostgreSQL 15**; `cars.id` is UUID via `gen_random_uuid()`. Tests use **SQLite in-memory** via SQLAlchemy 2.0 (UUID stored as CHAR(36) there — handled by SQLAlchemy's `Uuid` type).
- **Sync SQLAlchemy** (not async) — simpler for MVP; scraping uses async Playwright but persists via sync `Session`.
- Currency is always **`PLN`**; no conversion.
- **No** auth, payments, AI/ML/ranking, recommendations. MVP scope only.
- Each scraper returns the normalized dict shape defined in the spec; the normalizer is the single source of parsing truth.
- Deduplication key: **`(source, url)` UNIQUE** → upsert on re-scrape.
- Scrape is **async** (`POST /scrape/run` → 202, poll `GET /scrape/status`); one active job at a time (second start → 409).
- `facebook.py` is a **stub** reporting `blocked`; no mock listings injected.
- Frontend is **client-side** (no SSR), reads `NEXT_PUBLIC_API_URL`.

---

## File Structure

```
CarSkyscanner/
├── .gitignore
├── .env.example
├── README.md
├── PDR.md
├── backend/
│   ├── requirements.txt
│   ├── seed.py
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py            # FastAPI app, CORS, router wiring, /health
│   │   ├── config.py          # Settings (DATABASE_URL, etc.)
│   │   ├── database.py        # engine, SessionLocal, Base, get_db
│   │   ├── models.py          # Car
│   │   ├── schemas.py         # CarOut, SearchFilters, SearchResponse, ScrapeStatus
│   │   ├── crud.py            # upsert_car, get_cars, search_cars
│   │   ├── scraper_runner.py  # ScrapeJobManager (in-memory, async)
│   │   └── routers/
│   │       ├── __init__.py
│   │       ├── cars.py        # GET /cars, POST /search
│   │       └── scrape.py      # POST /scrape/run, GET /scrape/status
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py        # sqlite engine/session fixtures, client
│       ├── test_models.py
│       ├── test_normalizer.py
│       ├── test_crud.py
│       ├── test_cars_api.py
│       ├── test_scrape_api.py
│       └── fixtures/
│           ├── otomoto_list.html
│           └── olx_list.html
├── scrapers/
│   ├── __init__.py
│   ├── base.py               # BaseScraper, blocked-detection, parse helpers
│   ├── normalizer.py         # normalize(raw) -> dict, parse helpers
│   ├── otomoto.py
│   ├── olx.py
│   └── facebook.py
├── frontend/
│   ├── package.json
│   ├── next.config.mjs
│   ├── tailwind.config.ts
│   ├── postcss.config.mjs
│   ├── tsconfig.json
│   ├── .env.local.example
│   ├── Dockerfile
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   └── globals.css
│   ├── components/
│   │   ├── SearchForm.tsx
│   │   ├── ResultsList.tsx
│   │   ├── CarCard.tsx
│   │   ├── SourceBadge.tsx
│   │   └── ScrapePanel.tsx
│   └── lib/
│       └── api.ts
├── docker/
│   ├── docker-compose.yml
│   ├── Dockerfile.backend
│   └── Dockerfile.frontend
└── scripts/
    ├── seed_demo.py
    └── scrape_demo.py
```

**Responsibility notes:** `scrapers/normalizer.py` owns all string→typed parsing (price/mileage/year/fuel/transmission) so scrapers stay thin. `app/scraper_runner.py` owns job lifecycle and is the only thing that calls scrapers. `app/crud.py` is the only thing that touches `Car` rows. `frontend/lib/api.ts` is the only thing that knows the backend URL.

---

## Task 1: Repo skeleton, git, env, gitignore

**Files:**
- Create: `.gitignore`, `.env.example`, `README.md`, `backend/app/__init__.py`, `backend/app/routers/__init__.py`, `scrapers/__init__.py`, `backend/tests/__init__.py`
- Create: all directories from the structure above (empty `.gitkeep` where needed)

**Interfaces:** Produces the directory layout every later task assumes.

- [ ] **Step 1: Create directory tree**

```bash
cd /Users/danilshevchuk/PycharmProjects/CarSkyscanner
mkdir -p backend/app/routers backend/tests/fixtures scrapers frontend/app frontend/components frontend/lib docker scripts
touch backend/app/__init__.py backend/app/routers/__init__.py scrapers/__init__.py backend/tests/__init__.py
```

- [ ] **Step 2: Write `.gitignore`**

```gitignore
# Python
__pycache__/
*.py[cod]
.venv/
venv/
*.egg-info/
.pytest_cache/

# Node / Next
node_modules/
.next/
out/
frontend/.env.local

# Playwright / secrets
storage_state.json
.env

# OS
.DS_Store

# Editor
.idea/
.vscode/
```

- [ ] **Step 3: Write `.env.example`**

```env
# Backend
DATABASE_URL=postgresql+psycopg2://carsky:carsky@postgres:5432/carsky
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
# Auto-seed the DB on startup if empty (true/false)
AUTO_SEED=true

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
```

- [ ] **Step 4: Write `README.md` stub**

```markdown
# CarSkyscanner

Car listing aggregator MVP (Poland): Otomoto + OLX + Facebook (stub).

See `docs/superpowers/specs/2026-06-26-car-aggregator-mvp-design.md` for design.

## Quickstart
cp .env.example .env
cd docker && docker compose up --build
# Frontend: http://localhost:3000  API: http://localhost:8000/docs
```

- [ ] **Step 5: Init git and commit**

```bash
git init
git add -A
git commit -m "chore: repo skeleton and env scaffolding

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: Backend dependencies and config

**Files:**
- Create: `backend/requirements.txt`, `backend/app/config.py`

**Interfaces:**
- Produces: `app.config.Settings` (Pydantic Settings) with `DATABASE_URL: str`, used by `database.py` (Task 3).

- [ ] **Step 1: Write `backend/requirements.txt`**

```txt
fastapi==0.110.3
uvicorn[standard]==0.29.0
SQLAlchemy==2.0.30
pydantic==2.7.1
pydantic-settings==2.2.1
psycopg2-binary==2.9.9
playwright==1.44.0
httpx==0.27.0
python-multipart==0.0.9
pytest==8.2.0
pytest-asyncio==0.23.7
```

- [ ] **Step 2: Write `backend/app/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+psycopg2://carsky:carsky@localhost:5432/carsky"
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    AUTO_SEED: bool = True


settings = Settings()
```

- [ ] **Step 3: Verify it imports**

```bash
cd backend && python3 -m pip install -q pydantic-settings && python3 -c "from app.config import settings; print(settings.DATABASE_URL)"
```
Expected: prints the default DATABASE_URL string.

- [ ] **Step 4: Commit**

```bash
git add backend/requirements.txt backend/app/config.py
git commit -m "feat(backend): dependencies and settings

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 3: Database engine and Car model (TDD)

**Files:**
- Create: `backend/app/database.py`, `backend/app/models.py`, `backend/tests/conftest.py`, `backend/tests/test_models.py`

**Interfaces:**
- Produces: `app.database.Base`, `app.database.SessionLocal`, `app.database.get_db` (generator yielding a `Session`); `app.models.Car` (columns exactly per spec §3).

- [ ] **Step 1: Write the failing test**

`backend/tests/test_models.py`:
```python
from datetime import datetime
from app.database import Base, SessionLocal
from app.models import Car


def test_car_can_be_inserted_and_queried():
    Base.metadata.create_all(bind=SessionLocal.kw["bind"])  # sqlite from conftest
    db = SessionLocal()
    try:
        db.query(Car).delete()
        car = Car(
            title="VW Golf", brand="volkswagen", model="golf", year=2018,
            price=65000, currency="PLN", mileage=120000, fuel_type="petrol",
            transmission="manual", location="Warszawa", source="otomoto",
            url="https://otomoto.pl/x", image_url="https://img/x.jpg",
        )
        db.add(car); db.commit(); db.refresh(car)
        assert car.id is not None
        assert isinstance(car.created_at, datetime)
        rows = db.query(Car).all()
        assert len(rows) == 1
        assert rows[0].brand == "volkswagen"
    finally:
        db.close()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python3 -m pytest tests/test_models.py -v
```
Expected: FAIL — `ModuleNotFoundError: app.database`.

- [ ] **Step 3: Write `backend/app/database.py`**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.config import settings

engine = create_engine(settings.DATABASE_URL, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    import app.models  # noqa: F401  ensure model is registered
    Base.metadata.create_all(bind=engine)
```

- [ ] **Step 4: Write `backend/app/models.py`**

```python
import uuid
from sqlalchemy import String, Integer, Numeric, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone
from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Car(Base):
    __tablename__ = "cars"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True, server_default=func_uuid()), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    brand: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=True)
    price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="PLN")
    mileage: Mapped[int] = mapped_column(Integer, nullable=True)
    fuel_type: Mapped[str] = mapped_column(String(32), nullable=True)
    transmission: Mapped[str] = mapped_column(String(32), nullable=True)
    location: Mapped[str] = mapped_column(String, nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)
    image_url: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_now, nullable=False)

    __table_args__ = (
        Index("ix_cars_brand", "brand"),
        Index("ix_cars_model", "model"),
        Index("ix_cars_price", "price"),
        Index("ix_cars_year", "year"),
        Index("uq_cars_source_url", "source", "url", unique=True),
    )
```

Note: `func_uuid`/`server_default` differ per dialect. Add the import + helper at the top of `models.py`:

```python
from sqlalchemy import func as sa_func
from sqlalchemy import TypeDecorator
from sqlalchemy.types import CHAR

# Portable UUID: native in Postgres, CHAR(36) in SQLite (tests).
from sqlalchemy import Uuid

# Replace PG_UUID column with SQLAlchemy 2.0 portable Uuid:
# id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
```

**Implementation decision (use this, not the PG_UUID above):** Use SQLAlchemy 2.0's portable `Uuid` type so the same model works on Postgres (native) and SQLite (tests). Final column:

```python
id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
```
and drop `PG_UUID`/`func_uuid`. The `created_at` default stays. Remove unused imports (`PG_UUID`, `sa_func`, `TypeDecorator`, `CHAR`).

- [ ] **Step 5: Write `backend/tests/conftest.py` (sqlite engine for tests)**

```python
import pytest
from sqlalchemy import create_engine
from app.database import Base, SessionLocal, engine as prod_engine
import app.models  # noqa

@pytest.fixture(scope="function", autouse=True)
def sqlite_db(tmp_path):
    test_engine = create_engine(f"sqlite:///{tmp_path}/test.db", future=True)
    Base.metadata.create_all(bind=test_engine)
    import app.database as dbmod
    real = SessionLocal.kw["bind"]
    SessionLocal.configure(bind=test_engine)
    yield
    SessionLocal.configure(bind=real)
    Base.metadata.drop_all(bind=test_engine)
```

- [ ] **Step 6: Run test to verify it passes**

```bash
cd backend && python3 -m pytest tests/test_models.py -v
```
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/database.py backend/app/models.py backend/tests/conftest.py backend/tests/test_models.py
git commit -m "feat(backend): database engine and Car model

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: Normalizer (TDD)

**Files:**
- Create: `scrapers/normalizer.py`, `backend/tests/test_normalizer.py`

**Interfaces:**
- Produces: `scrapers.normalizer.normalize(raw: dict) -> dict | None` (returns a cleaned car dict in spec shape, or `None` if invalid — missing `url`/`price`); plus parse helpers `parse_price`, `parse_mileage`, `parse_year`, `normalize_fuel`, `normalize_transmission`. `normalize` must run without a DB.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_normalizer.py`:
```python
from scrapers.normalizer import (
    normalize, parse_price, parse_mileage, parse_year,
    normalize_fuel, normalize_transmission,
)


def test_parse_price_handles_polish_format():
    assert parse_price("89 900 PLN") == 89900.0
    assert parse_price("1 234 567,99 zł") == 1234567.99
    assert parse_price(None) is None


def test_parse_mileage_handles_tys():
    assert parse_mileage("150 tys. km") == 150000
    assert parse_mileage("12 345 km") == 12345
    assert parse_mileage(None) is None


def test_parse_year():
    assert parse_year("2018") == 2018
    assert parse_year("Rok produkcji: 2015") == 2015
    assert parse_year("abc") is None


def test_normalize_fuel_maps_variants():
    assert normalize_fuel("Benzyna") == "petrol"
    assert normalize_fuel("Diesel") == "diesel"
    assert normalize_fuel("Elektryczny") == "electric"
    assert normalize_fuel("Hybryda") == "hybrid"
    assert normalize_fuel("LPG") == "lpg"
    assert normalize_fuel("Cosmic") == "other"


def test_normalize_transmission():
    assert normalize_transmission("Skrzynia manualna") == "manual"
    assert normalize_transmission("Automatyczna") == "automatic"
    assert normalize_transmission(None) is None


def test_normalize_produces_canonical_dict():
    raw = {
        "title": "VW Golf", "brand": " Volkswagen ", "model": "GOLF",
        "year": "2018", "price": "89 900 PLN", "mileage": "150 tys. km",
        "fuel_type": "Benzyna", "transmission": "Manualna",
        "location": "Warszawa", "source": "otomoto",
        "url": "https://otomoto.pl/x", "image_url": "https://img/x.jpg",
    }
    out = normalize(raw)
    assert out["brand"] == "volkswagen"
    assert out["model"] == "golf"
    assert out["price"] == 89900.0
    assert out["mileage"] == 150000
    assert out["year"] == 2018
    assert out["fuel_type"] == "petrol"
    assert out["transmission"] == "manual"
    assert out["currency"] == "PLN"


def test_normalize_rejects_missing_url_or_price():
    assert normalize({"title": "x", "price": "10", "source": "olx", "url": ""}) is None
    assert normalize({"title": "x", "price": None, "source": "olx", "url": "u"}) is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python3 -m pytest tests/test_normalizer.py -v
```
Expected: FAIL — `ModuleNotFoundError: scrapers.normalizer`.

- [ ] **Step 3: Write `scrapers/normalizer.py`**

```python
import re
from typing import Optional

FUEL_MAP = {
    "benzyna": "petrol", "benzynowy": "petrol", "petrol": "petrol",
    "diesel": "diesel", "olej napędowy": "diesel",
    "lpg": "lpg", "autogas": "lpg",
    "hybryda": "hybrid", "hybrid": "hybrid", "hybrydowy": "hybrid",
    "elektryczny": "electric", "elektryczne": "electric", "electric": "electric",
}
TRANSMISSION_MAP = {
    "manual": "manual", "manualna": "manual", "skrzynia manualna": "manual",
    "automat": "automatic", "automatyczna": "automatic", "automatic": "automatic",
}


def parse_price(value) -> Optional[float]:
    if not value:
        return None
    s = str(value).lower().replace("\xa0", " ").replace("zł", "").replace("pln", "")
    s = s.replace(" ", "").replace(",", ".")
    m = re.search(r"\d+(?:\.\d+)?", s)
    return float(m.group()) if m else None


def parse_mileage(value) -> Optional[int]:
    if not value:
        return None
    s = str(value).lower().replace("\xa0", " ").replace("km", "").strip()
    if "tys" in s:
        m = re.search(r"[\d.,]+", s)
        return int(float(m.group().replace(",", ".")) * 1000) if m else None
    m = re.search(r"\d+", s.replace(" ", ""))
    return int(m.group()) if m else None


def parse_year(value) -> Optional[int]:
    if not value:
        return None
    m = re.search(r"(19|20)\d{2}", str(value))
    return int(m.group()) if m else None


def normalize_fuel(value) -> str:
    key = str(value or "").strip().lower()
    return FUEL_MAP.get(key, "other")


def normalize_transmission(value) -> Optional[str]:
    if not value:
        return None
    key = str(value).strip().lower()
    for k, v in TRANSMISSION_MAP.items():
        if k in key:
            return v
    return None


def _clean(s) -> str:
    return str(s or "").strip()


def normalize(raw: dict) -> Optional[dict]:
    url = _clean(raw.get("url"))
    price = parse_price(raw.get("price"))
    if not url or price is None:
        return None
    return {
        "title": _clean(raw.get("title")) or None,
        "brand": _clean(raw.get("brand")).lower(),
        "model": _clean(raw.get("model")).lower(),
        "year": parse_year(raw.get("year")),
        "price": price,
        "currency": "PLN",
        "mileage": parse_mileage(raw.get("mileage")),
        "fuel_type": normalize_fuel(raw.get("fuel_type")),
        "transmission": normalize_transmission(raw.get("transmission")),
        "location": _clean(raw.get("location")) or None,
        "source": _clean(raw.get("source")).lower(),
        "url": url,
        "image_url": _clean(raw.get("image_url")) or None,
    }
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && python3 -m pytest tests/test_normalizer.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scrapers/normalizer.py backend/tests/test_normalizer.py
git commit -m "feat(scrapers): normalizer with parse helpers

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 5: CRUD — upsert, get, search (TDD)

**Files:**
- Create: `backend/app/crud.py`, `backend/tests/test_crud.py`

**Interfaces:**
- Consumes: `app.models.Car`, `app.database.SessionLocal`.
- Produces: `crud.upsert_car(db, data: dict) -> Car`, `crud.get_cars(db, limit, offset) -> tuple[list[Car], int]`, `crud.search_cars(db, filters: SearchFilters, limit, offset) -> tuple[list[Car], int]`. `SearchFilters` comes from Task 6; for this task test against a minimal duck-typed object or import it after Task 6 — **see ordering note**.

> **Ordering note:** `crud.search_cars` references `schemas.SearchFilters`. Write `crud.py` to import `SearchFilters` lazily inside the function (`from app.schemas import SearchFilters`) OR define Task 6 (schemas) before this task. Recommended: do **Task 6 first, then Task 5**. The tests below pass `SearchFilters(...)` objects.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_crud.py`:
```python
from app.database import SessionLocal
from app.crud import upsert_car, get_cars, search_cars
from app.schemas import SearchFilters


def _seed(db, **over):
    base = dict(title="VW Golf", brand="volkswagen", model="golf", year=2018,
                price=65000, currency="PLN", mileage=120000, fuel_type="petrol",
                transmission="manual", location="Warszawa", source="otomoto",
                url="u1", image_url="i")
    base.update(over)
    return upsert_car(db, base)


def test_upsert_is_idempotent_on_source_url():
    db = SessionLocal()
    try:
        _seed(db, url="dup", price=1000)
        _seed(db, url="dup", price=2000)  # same source+url -> update
        cars, total = get_cars(db)
        assert total == 1
        assert float(cars[0].price) == 2000.0
    finally:
        db.close()


def test_search_filters():
    db = SessionLocal()
    try:
        _seed(db, url="a", brand="volkswagen", price=50000, year=2020, mileage=10000)
        _seed(db, url="b", brand="audi", price=150000, year=2015, mileage=200000)
        cars, total = search_cars(db, SearchFilters(brand="volkswagen", price_max=100000))
        assert total == 1
        assert cars[0].brand == "volkswagen"
    finally:
        db.close()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python3 -m pytest tests/test_crud.py -v
```
Expected: FAIL — `ModuleNotFoundError: app.crud` (and `app.schemas` — confirm Task 6 is done first).

- [ ] **Step 3: Write `backend/app/crud.py`**

```python
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models import Car


def upsert_car(db: Session, data: dict) -> Car:
    existing = db.execute(
        select(Car).where(Car.source == data["source"], Car.url == data["url"])
    ).scalar_one_or_none()
    if existing:
        for k, v in data.items():
            if hasattr(existing, k):
                setattr(existing, k, v)
        db.commit(); db.refresh(existing)
        return existing
    car = Car(**data)
    db.add(car); db.commit(); db.refresh(car)
    return car


def _apply(filters, q):
    if filters.brand:
        q = q.where(func.lower(Car.brand) == filters.brand.lower())
    if filters.model:
        q = q.where(Car.model.ilike(f"%{filters.model}%"))
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
    rows = db.execute(base.order_by(Car.created_at.desc()).limit(limit).offset(offset)).scalars().all()
    return rows, total
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && python3 -m pytest tests/test_crud.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/crud.py backend/tests/test_crud.py
git commit -m "feat(backend): crud upsert/get/search

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 6: Pydantic schemas

**Files:**
- Create: `backend/app/schemas.py`

**Interfaces:**
- Produces: `schemas.SearchFilters` (all-optional fields: `brand, model, year_min, year_max, price_min, price_max, mileage_max, fuel_type, transmission`), `schemas.CarOut` (all Car columns + `id`, `created_at`), `schemas.SearchResponse` (`items: list[CarOut], total: int, limit: int, offset: int`), `schemas.ScrapeStatus` (`status, job_id, started_at, finished_at, total_saved, per_source: dict`), `schemas.ScrapeStart` (`job_id, status`).

- [ ] **Step 1: Write `backend/app/schemas.py`**

```python
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
```

- [ ] **Step 2: Verify it imports and validates**

```bash
cd backend && python3 -c "from app.schemas import SearchFilters, CarOut, ScrapeStatus; print(SearchFilters().model_dump())"
```
Expected: prints all-None filter dict.

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas.py
git commit -m "feat(backend): pydantic schemas

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 7: Cars router + main app + /health (TDD)

**Files:**
- Create: `backend/app/routers/cars.py`, `backend/app/main.py`, `backend/tests/test_cars_api.py`

**Interfaces:**
- Consumes: `crud.get_cars`, `crud.search_cars`, `schemas.*`, `database.get_db`.
- Produces: FastAPI app `app.main.app` with routes `GET /health`, `GET /cars`, `POST /search`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_cars_api.py`:
```python
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.crud import upsert_car


def test_health():
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_get_cars_and_search():
    db = SessionLocal()
    try:
        db.query(type(db.query.__self__.query(app=None) and None))  # placeholder cleanup below
    except Exception:
        pass
    # seed via crud
    upsert_car(db, dict(title="VW Golf", brand="volkswagen", model="golf", year=2020,
                        price=60000, currency="PLN", mileage=50000, fuel_type="petrol",
                        transmission="manual", location="Wawa", source="otomoto",
                        url="h1", image_url="i"))
    db.close()
    client = TestClient(app)
    allr = client.get("/cars")
    assert allr.status_code == 200
    assert allr.json()["total"] >= 1
    sr = client.post("/search", json={"brand": "volkswagen", "price_max": 100000})
    assert sr.status_code == 200
    assert sr.json()["total"] == 1
    assert sr.json()["items"][0]["brand"] == "volkswagen"
```

(Delete the `try/except placeholder cleanup` block before running — it is illustrative only. Final test should simply seed via `upsert_car` then query.)

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python3 -m pytest tests/test_cars_api.py -v
```
Expected: FAIL — `ModuleNotFoundError: app.main`.

- [ ] **Step 3: Write `backend/app/routers/cars.py`**

```python
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
```

- [ ] **Step 4: Write `backend/app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import cars, scrape
from app.database import init_db

app = FastAPI(title="CarSkyscanner API", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

@app.on_event("startup")
def _startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(cars.router)
app.include_router(scrape.router)
```

> Note: `main.py` imports `scrape` router (Task 13). Until Task 13, create a temporary empty `backend/app/routers/scrape.py` containing just `from fastapi import APIRouter\nrouter = APIRouter()` so `main` imports cleanly. Replace it in Task 13.

- [ ] **Step 5: Create temporary `backend/app/routers/scrape.py`** (placeholder until Task 13)

```python
from fastapi import APIRouter
router = APIRouter()
```

- [ ] **Step 6: Run test to verify it passes**

```bash
cd backend && python3 -m pytest tests/test_cars_api.py -v
```
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/cars.py backend/app/main.py backend/app/routers/scrape.py backend/tests/test_cars_api.py
git commit -m "feat(backend): cars router, main app, health

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 8: BaseScraper (Playwright wrapper + blocked detection)

**Files:**
- Create: `scrapers/base.py`

**Interfaces:**
- Produces: `scrapers.base.ScrapeResult` (dataclass: `source: str, listings: list[dict], blocked: bool, reason: str | None`), `scrapers.base.BaseScraper` (abstract async class; subclass sets `source`, `build_url()`, and `parse_page(page) -> list[dict]` of raw dicts; `run(playwright)` returns `ScrapeResult`). Subclasses use `normalize()` from the normalizer before returning listings.

- [ ] **Step 1: Write `scrapers/base.py`**

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from playwright.async_api import Page, Playwright


BLOCKED_MARKERS = ("access denied", "captcha", "unblock", "zabezpieczenie",
                   "datadome", "are you human", "weryfikacja")


@dataclass
class ScrapeResult:
    source: str
    listings: list[dict] = field(default_factory=list)
    blocked: bool = False
    reason: Optional[str] = None


def is_blocked(page: Page) -> bool:
    try:
        title = (page.title() or "") if False else ""  # title() is sync? see note
    except Exception:
        title = ""
    return False  # replaced below by async helper
```

> **Note (replace the stub above):** `page.title()` is a coroutine in async Playwright. Implement an `async` helper and call it inside `run()`. Final `base.py`:

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from playwright.async_api import Page, Playwright
from scrapers.normalizer import normalize

BLOCKED_MARKERS = ("access denied", "captcha", "unblock", "datadome",
                   "are you human", "weryfikacja", "zabezpieczenie")


@dataclass
class ScrapeResult:
    source: str
    listings: list[dict] = field(default_factory=list)
    blocked: bool = False
    reason: Optional[str] = None


async def _is_blocked(page: Page) -> tuple[bool, Optional[str]]:
    try:
        title = await page.title()
        body_text = await page.evaluate("() => document.body ? document.body.innerText.slice(0, 2000) : ''")
    except Exception as e:
        return True, f"page read failed: {e}"
    combined = f"{title} {body_text}".lower()
    for marker in BLOCKED_MARKERS:
        if marker in combined:
            return True, f"blocked-marker:{marker}"
    return False, None


class BaseScraper(ABC):
    source: str = "base"
    timeout_ms: int = 30000

    @abstractmethod
    def build_url(self) -> str: ...

    @abstractmethod
    async def parse_page(self, page: Page) -> list[dict]:
        """Return raw listing dicts (pre-normalize)."""

    async def run(self, playwright: Playwright) -> ScrapeResult:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            resp = await page.goto(self.build_url(), timeout=self.timeout_ms, wait_until="domcontentloaded")
            if resp and resp.status >= 400:
                return ScrapeResult(self.source, blocked=True, reason=f"http {resp.status}")
            blocked, reason = await _is_blocked(page)
            if blocked:
                return ScrapeResult(self.source, blocked=True, reason=reason)
            raw_items = await self.parse_page(page)
            listings = [n for n in (normalize(r) for r in raw_items) if n]
            return ScrapeResult(self.source, listings=listings)
        except Exception as e:
            return ScrapeResult(self.source, blocked=True, reason=f"error: {e}")
        finally:
            await browser.close()
```

- [ ] **Step 2: Smoke-import (Playwright may not be installed locally; verify syntax only)**

```bash
cd /Users/danilshevchuk/PycharmProjects/CarSkyscanner
python3 -m py_compile scrapers/base.py && echo OK
```
Expected: prints `OK`.

- [ ] **Step 3: Commit**

```bash
git add scrapers/base.py
git commit -m "feat(scrapers): BaseScraper with blocked detection

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 9: Otomoto scraper

**Files:**
- Create: `scrapers/otomoto.py`, `backend/tests/fixtures/otomoto_list.html`, `backend/tests/test_otomoto.py`

**Interfaces:**
- Consumes: `scrapers.base.BaseScraper`, `scrapers.normalizer.normalize`.
- Produces: `scrapers.otomoto.OtomotoScraper` with `source="otomoto"`; `build_url()` builds a search URL from optional filters; `parse_page()` returns raw dicts. The runner (Task 12) instantiates `OtomotoScraper(brand=...)`.

> **Selectors note:** Real Otomoto `data-testid`/class names change. The test uses a frozen HTML fixture so parsing logic is stable; real selectors must be confirmed against live markup at run time and are easy to update in one place.

- [ ] **Step 1: Create HTML fixture `backend/tests/fixtures/otomoto_list.html`**

A minimal page with two article cards using `data-testid="listing-ad"`:
```html
<!DOCTYPE html><html><head><title>Otomoto</title></head><body>
<article data-testid="listing-ad">
  <a href="https://www.otomoto.pl/osobowe/id/1"><h2>Volkswagen Golf 2018</h2></a>
  <img src="https://img/golf.jpg"/>
  <dd data-testid="ad-price">89 900 PLN</dd>
  <dd>2018</dd>
  <dd>Benzyna</dd>
  <dd>Manualna</dd>
  <dd>150 tys. km</dd>
  <dd>Warszawa</dd>
</article>
<article data-testid="listing-ad">
  <a href="https://www.otomoto.pl/osobowe/id/2"><h2>Audi A4 2020</h2></a>
  <img src="https://img/a4.jpg"/>
  <dd data-testid="ad-price">120 000 PLN</dd>
  <dd>2020</dd>
  <dd>Diesel</dd>
  <dd>Automatyczna</dd>
  <dd>80 tys. km</dd>
  <dd>Kraków</dd>
</article>
</body></html>
```

- [ ] **Step 2: Write the failing test**

`backend/tests/test_otomoto.py` (parse logic tested against the fixture via a small synchronous helper that mirrors `parse_page`'s DOM access):
```python
from pathlib import Path
from scrapers.otomoto import OtomotoScraper

FIX = Path(__file__).parent / "fixtures" / "otomoto_list.html"


def test_build_url_with_brand():
    url = OtomotoScraper(brand="volkswagen").build_url()
    assert "otomoto.pl" in url and "volkswagen" in url


def test_parse_fixture_extracts_two_listings():
    # parse_html is a sync pure helper extracted from parse_page for testability
    from scrapers.otomoto import parse_html
    items = parse_html(FIX.read_text())
    assert len(items) == 2
    first = items[0]
    assert first["url"].endswith("/id/1")
    assert "89 900 PLN" in first["price"]
    assert first["source"] == "otomoto"
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd backend && python3 -m pytest tests/test_otomoto.py -v
```
Expected: FAIL — `ModuleNotFoundError: scrapers.otomoto`.

- [ ] **Step 4: Write `scrapers/otomoto.py`**

```python
from urllib.parse import quote
from playwright.async_api import Page
from scrapers.base import BaseScraper
from bs4 import BeautifulSoup  # NOTE: add beautifulsoup4==4.12.3 to requirements.txt


def parse_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for art in soup.select('[data-testid="listing-ad"]'):
        a = art.select_one("a[href]")
        img = art.select_one("img")
        dds = [d.get_text(strip=True) for d in art.select("dd")]
        price_dd = art.select_one('[data-testid="ad-price"]')
        if not a:
            continue
        out.append({
            "title": art.get_text(" ", strip=True)[:200],
            "brand": "", "model": "",
            "year": dds[0] if len(dds) > 0 else None,
            "price": price_dd.get_text(strip=True) if price_dd else None,
            "mileage": next((d for d in dds if "km" in d), None),
            "fuel_type": next((d for d in dds if d.lower() in ("benzyna", "diesel", "hybryda", "elektryczny", "lpg")), None),
            "transmission": next((d for d in dds if d.lower() in ("manualna", "automatyczna")), None),
            "location": dds[-1] if dds else None,
            "source": "otomoto",
            "url": a["href"],
            "image_url": img["src"] if img and img.get("src") else None,
        })
    return out


class OtomotoScraper(BaseScraper):
    source = "otomoto"

    def __init__(self, brand: str | None = None, model: str | None = None):
        self.brand = brand
        self.model = model

    def build_url(self) -> str:
        path = "osobowe"
        if self.brand:
            path = f"osobowe/{quote(self.brand)}"
        return f"https://www.otomoto.pl/{path}"

    async def parse_page(self, page: Page) -> list[dict]:
        html = await page.content()
        return parse_html(html)
```

Add `beautifulsoup4==4.12.3` to `backend/requirements.txt`.

- [ ] **Step 5: Run test to verify it passes**

```bash
cd backend && python3 -m pip install -q beautifulsoup4 && python3 -m pytest tests/test_otomoto.py -v
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scrapers/otomoto.py backend/tests/fixtures/otomoto_list.html backend/tests/test_otomoto.py backend/requirements.txt
git commit -m "feat(scrapers): otomoto scraper with fixture test

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 10: OLX scraper

**Files:**
- Create: `scrapers/olx.py`, `backend/tests/fixtures/olx_list.html`, `backend/tests/test_olx.py`

**Interfaces:** mirror Task 9. Produces `scrapers.olx.OLXScraper` (`source="olx"`) and sync `parse_html(html)`.

- [ ] **Step 1: Create fixture `backend/tests/fixtures/olx_list.html`**

```html
<!DOCTYPE html><html><head><title>OLX</title></head><body>
<div data-cy="l-card">
  <a href="https://www.olx.pl/d/oferta/golf-2018-ID123.html"><h6>Volkswagen Golf</h6></a>
  <img src="https://img/golf.jpg"/>
  <p data-testid="ad-price">65 000 zł</p>
  <p>2018 • 150 000 km • Benzyna</p>
</div>
<div data-cy="l-card">
  <a href="https://www.olx.pl/d/oferta/a4-2020-ID456.html"><h6>Audi A4</h6></a>
  <img src="https://img/a4.jpg"/>
  <p data-testid="ad-price">99 000 zł</p>
  <p>2020 • 80 000 km • Diesel</p>
</div>
</body></html>
```

- [ ] **Step 2: Write the failing test** `backend/tests/test_olx.py`

```python
from pathlib import Path
from scrapers.olx import OLXScraper, parse_html

FIX = Path(__file__).parent / "fixtures" / "olx_list.html"


def test_build_url():
    assert "olx.pl" in OLXScraper().build_url()


def test_parse_fixture():
    items = parse_html(FIX.read_text())
    assert len(items) == 2
    assert items[0]["url"].endswith("ID123.html")
    assert "65 000" in items[0]["price"]
    assert items[0]["source"] == "olx"
```

- [ ] **Step 3: Run to verify it fails**

```bash
cd backend && python3 -m pytest tests/test_olx.py -v
```
Expected: FAIL — `ModuleNotFoundError: scrapers.olx`.

- [ ] **Step 4: Write `scrapers/olx.py`**

```python
import re
from playwright.async_api import Page
from bs4 import BeautifulSoup
from scrapers.base import BaseScraper


def parse_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for card in soup.select('[data-cy="l-card"]'):
        a = card.select_one("a[href]")
        img = card.select_one("img")
        price = card.select_one('[data-testid="ad-price"]')
        meta = card.get_text(" ", strip=True)
        year = re.search(r"(19|20)\d{2}", meta)
        mileage = re.search(r"([\d ]+) km", meta)
        if not a or not price:
            continue
        out.append({
            "title": (card.select_one("h6").get_text(strip=True) if card.select_one("h6") else meta[:200]),
            "brand": "", "model": "",
            "year": year.group(0) if year else None,
            "price": price.get_text(strip=True),
            "mileage": mileage.group(0) if mileage else None,
            "fuel_type": next((t for t in ("Benzyna", "Diesel", "Hybryda", "Elektryczny", "LPG") if t in meta), None),
            "transmission": None,
            "location": None,
            "source": "olx",
            "url": a["href"],
            "image_url": img["src"] if img and img.get("src") else None,
        })
    return out


class OLXScraper(BaseScraper):
    source = "olx"

    def build_url(self) -> str:
        return "https://www.olx.pl/motoryzacja/samochody/"

    async def parse_page(self, page: Page) -> list[dict]:
        return parse_html(await page.content())
```

- [ ] **Step 5: Run to verify it passes**

```bash
cd backend && python3 -m pytest tests/test_olx.py -v
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scrapers/olx.py backend/tests/fixtures/olx_list.html backend/tests/test_olx.py
git commit -m "feat(scrapers): olx scraper with fixture test

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 11: Facebook stub scraper (TDD)

**Files:**
- Create: `scrapers/facebook.py`, `backend/tests/test_facebook.py`

**Interfaces:** Produces `scrapers.facebook.FacebookScraper` (`source="facebook"`) whose `run()` always returns `ScrapeResult(source="facebook", blocked=True, reason="login required (stub)")`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_facebook.py`:
```python
import asyncio
from scrapers.facebook import FacebookScraper
from scrapers.base import ScrapeResult


def test_facebook_is_stub_blocked():
    scraper = FacebookScraper()

    class FakePlaywright:
        class chromium:
            @staticmethod
            async def launch(headless=True):
                raise AssertionError("stub must not launch a browser")

    res = asyncio.get_event_loop().run_until_complete(scraper.run(FakePlaywright()))
    assert isinstance(res, ScrapeResult)
    assert res.source == "facebook"
    assert res.blocked is True
    assert res.listings == []
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd backend && python3 -m pytest tests/test_facebook.py -v
```
Expected: FAIL — `ModuleNotFoundError: scrapers.facebook`.

- [ ] **Step 3: Write `scrapers/facebook.py`**

```python
from typing import Optional
from scrapers.base import BaseScraper, ScrapeResult


class FacebookScraper(BaseScraper):
    """Stub: FB Marketplace requires an authenticated session (out of MVP scope)."""

    source = "facebook"

    def build_url(self) -> str:
        return "https://www.facebook.com/marketplace/"

    async def parse_page(self, page):  # never reached
        return []

    async def run(self, playwright=None) -> ScrapeResult:
        return ScrapeResult(source=self.source, blocked=True, reason="login required (stub)")
```

- [ ] **Step 4: Run to verify it passes**

```bash
cd backend && python3 -m pytest tests/test_facebook.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scrapers/facebook.py backend/tests/test_facebook.py
git commit -m "feat(scrapers): facebook stub (blocked)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 12: ScrapeJobManager runner (TDD)

**Files:**
- Create: `backend/app/scraper_runner.py`, `backend/tests/test_runner.py`

**Interfaces:**
- Consumes: scrapers (`OtomotoScraper`, `OLXScraper`, `FacebookScraper`), `BaseScraper.run`, `crud.upsert_car`, `database.SessionLocal`.
- Produces: `scraper_runner.manager` (singleton instance). Methods: `start() -> ScrapeStart` (raises if running), `status() -> ScrapeStatus`, internal `_run(job_id)` async coroutine that iterates scrapers, persists listings, fills `per_source` counts.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_runner.py`:
```python
import asyncio
from app.scraper_runner import ScrapeJobManager
from scrapers.base import ScrapeResult


def test_status_starts_idle():
    m = ScrapeJobManager()
    assert m.status().status == "idle"


def test_start_then_done_with_mock_scrapers(monkeypatch):
    m = ScrapeJobManager()

    class FakePlaywright:
        pass

    def fake_make_scrapers():
        class S:
            source = "otomoto"
            async def run(self, pw):
                return ScrapeResult("otomoto", listings=[
                    {"title": "x", "brand": "vw", "model": "g", "year": 2020,
                     "price": 1000, "currency": "PLN", "mileage": 1, "fuel_type": "petrol",
                     "transmission": "manual", "location": "W", "source": "otomoto",
                     "url": "mock1", "image_url": None},
                ])
        return [S()]

    monkeypatch.setattr(m, "_make_scrapers", fake_make_scrapers)
    monkeypatch.setattr(m, "_run_playwright", lambda coro: asyncio.get_event_loop().run_until_complete(coro))
    start = m.start()
    assert start.status == "running"
    m._run_playwright(m._current_coro)  # execute synchronously
    st = m.status()
    assert st.status == "done"
    assert st.per_source["otomoto"].saved == 1
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd backend && python3 -m pytest tests/test_runner.py -v
```
Expected: FAIL — `ModuleNotFoundError: app.scraper_runner`.

- [ ] **Step 3: Write `backend/app/scraper_runner.py`**

```python
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Callable
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
    def __init__(self):
        self._status = schemas.ScrapeStatus(status="idle", per_source={})
        self._current_coro = None

    def status(self) -> schemas.ScrapeStatus:
        return self._status

    def _make_scrapers(self) -> list[BaseScraper]:
        return [OtomotoScraper(), OLXScraper(), FacebookScraper()]

    def _run_playwright(self, coro):
        """Default: run in the running event loop; overridable in tests."""
        loop = asyncio.get_event_loop()
        return loop.create_task(coro)

    def start(self) -> schemas.ScrapeStart:
        if self._status.status == "running":
            from fastapi import HTTPException
            raise HTTPException(status_code=409, detail="a scrape is already running")
        job_id = str(uuid.uuid4())
        self._status = schemas.ScrapeStatus(
            status="running", job_id=job_id, started_at=_now(),
            per_source={s.source: schemas.SourceResult() for s in self._make_scrapers()},
        )
        self._current_coro = self._run(job_id)
        self._run_playwright(self._current_coro)
        return schemas.ScrapeStart(job_id=job_id, status="running")

    async def _run(self, job_id: str):
        from playwright.async_api import async_playwright
        scrapers = self._make_scrapers()
        async with async_playwright() as pw:
            for scraper in scrapers:
                result = await scraper.run(pw)
                sr = self._status.per_source.setdefault(scraper.source, schemas.SourceResult())
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
        self._status.finished_at = _now()
        self._status.total_saved = sum(s.saved for s in self._status.per_source.values())


manager = ScrapeJobManager()
```

> **Note:** In the production `start()` path `_run_playwright` schedules the coroutine as a background `Task` on the loop that FastAPI/uvicorn runs. For dev that loop exists; the task persists across requests until done. If `start()` is called outside a running loop (e.g. from a sync test), the override in the test drives execution.

- [ ] **Step 4: Run to verify it passes**

```bash
cd backend && python3 -m pytest tests/test_runner.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/scraper_runner.py backend/tests/test_runner.py
git commit -m "feat(backend): ScrapeJobManager runner

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 13: Scrape router wiring (TDD)

**Files:**
- Modify: `backend/app/routers/scrape.py` (replace placeholder from Task 7)
- Create: `backend/tests/test_scrape_api.py`

**Interfaces:**
- Consumes: `scraper_runner.manager`.
- Produces: `POST /scrape/run` → 202 `{job_id, status}`; `GET /scrape/status` → `ScrapeStatus`; 409 when already running.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_scrape_api.py`:
```python
from fastapi.testclient import TestClient
from app.main import app
from app.scraper_runner import manager
from app import schemas


def test_status_endpoint():
    manager._status = schemas.ScrapeStatus(status="idle", per_source={})
    client = TestClient(app)
    r = client.get("/scrape/status")
    assert r.status_code == 200
    assert r.json()["status"] == "idle"


def test_run_returns_202(monkeypatch):
    manager._status = schemas.ScrapeStatus(status="idle", per_source={})
    # avoid real playwright: make start synchronous no-op
    monkeypatch.setattr(manager, "_make_scrapers", lambda: [])
    monkeypatch.setattr(manager, "_run_playwright", lambda coro: None)
    client = TestClient(app)
    r = client.post("/scrape/run")
    assert r.status_code == 202
    assert r.json()["status"] == "running"


def test_conflict_when_running():
    manager._status = schemas.ScrapeStatus(status="running", per_source={})
    client = TestClient(app)
    r = client.post("/scrape/run")
    assert r.status_code == 409
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd backend && python3 -m pytest tests/test_scrape_api.py -v
```
Expected: FAIL — routes missing (`/scrape/status` returns 404).

- [ ] **Step 3: Replace `backend/app/routers/scrape.py`**

```python
from fastapi import APIRouter
from app.scraper_runner import manager

router = APIRouter(prefix="/scrape", tags=["scrape"])


@router.post("/run", status_code=202)
def run():
    start = manager.start()
    return start


@router.get("/status")
def status():
    return manager.status()
```

- [ ] **Step 4: Run to verify it passes**

```bash
cd backend && python3 -m pytest tests/test_scrape_api.py -v
```
Expected: PASS. Also run the full suite: `python3 -m pytest -q` — all green.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/scrape.py backend/tests/test_scrape_api.py
git commit -m "feat(backend): scrape router wired to runner

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 14: Seed script

**Files:**
- Create: `backend/seed.py`

**Interfaces:**
- Consumes: `database.init_db`, `database.SessionLocal`, `crud.upsert_car`.
- Produces: `python seed.py` populates ~40 realistic cars across all three sources; idempotent via upsert.

- [ ] **Step 1: Write `backend/seed.py`**

```python
import random
from app.database import init_db, SessionLocal
from app.crud import upsert_car

BRANDS = {
    "volkswagen": ["golf", "passat", "tiguan"],
    "audi": ["a4", "a6", "q5"],
    "bmw": ["320i", "x3", "520"],
    "toyota": ["corolla", "yaris", "rav4"],
    "skoda": ["octavia", "superb", "kodiaq"],
}
FUELS = ["petrol", "diesel", "hybrid", "electric", "lpg"]
TRANS = ["manual", "automatic"]
CITIES = ["Warszawa", "Kraków", "Wrocław", "Poznań", "Gdańsk", "Łódź"]
SOURCES = ["otomoto", "olx", "facebook"]


def build_seed(n=40) -> list[dict]:
    out = []
    for i in range(n):
        brand = random.choice(list(BRANDS))
        model = random.choice(BRANDS[brand])
        source = SOURCES[i % 3]
        out.append({
            "title": f"{brand.title()} {model.title()}",
            "brand": brand, "model": model,
            "year": random.randint(2010, 2023),
            "price": random.randint(15000, 180000),
            "currency": "PLN",
            "mileage": random.randint(10000, 300000),
            "fuel_type": random.choice(FUELS),
            "transmission": random.choice(TRANS),
            "location": random.choice(CITIES),
            "source": source,
            "url": f"https://example.{source}/listing/{i}",
            "image_url": f"https://picsum.photos/seed/{brand}{i}/400/300",
        })
    return out


def main():
    init_db()
    db = SessionLocal()
    try:
        for item in build_seed():
            upsert_car(db, item)
        print(f"Seeded {len(build_seed())} cars")
    finally:
        db.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke-run against sqlite (no Postgres needed)**

```bash
cd backend && DATABASE_URL="sqlite:///./seed_check.db" python3 seed.py && rm -f seed_check.db
```
Expected: prints `Seeded 40 cars`.

- [ ] **Step 3: Commit**

```bash
git add backend/seed.py
git commit -m "feat(backend): seed script

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 15: Demo scripts

**Files:**
- Create: `scripts/seed_demo.py`, `scripts/scrape_demo.py`

**Interfaces:** Standalone CLI demos. `seed_demo` imports `backend.seed`; `scrape_demo` runs scrapers directly (no API) and prints a table + blocked reasons.

- [ ] **Step 1: Write `scripts/seed_demo.py`**

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from seed import main  # noqa
if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write `scripts/scrape_demo.py`**

```python
import asyncio, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from scrapers.otomoto import OtomotoScraper
from scrapers.olx import OLXScraper
from scrapers.facebook import FacebookScraper
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as pw:
        for scraper in (OtomotoScraper(), OLXScraper(), FacebookScraper()):
            r = await scraper.run(pw)
            print(f"\n=== {r.source} ===  blocked={r.blocked} reason={r.reason}")
            for it in r.listings[:5]:
                print(f"  - {it.get('title')} | {it.get('price')} PLN | {it.get('url')}")
            if not r.listings and not r.blocked:
                print("  (no listings parsed — selectors may need updating)")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3: Commit**

```bash
git add scripts/seed_demo.py scripts/scrape_demo.py
git commit -m "feat(scripts): seed and scrape demos

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 16: Frontend setup + API client

**Files:**
- Create: `frontend/package.json`, `frontend/next.config.mjs`, `frontend/tsconfig.json`, `frontend/tailwind.config.ts`, `frontend/postcss.config.mjs`, `frontend/app/globals.css`, `frontend/app/layout.tsx`, `frontend/lib/api.ts`, `frontend/.env.local.example`

**Interfaces:** Produces a Next.js app and a typed `lib/api.ts` exposing `getCars`, `searchCars(filters)`, `runScrape()`, `getScrapeStatus()` against `NEXT_PUBLIC_API_URL`.

- [ ] **Step 1: Write `frontend/package.json`**

```json
{
  "name": "carsky-frontend",
  "private": true,
  "scripts": {
    "dev": "next dev -p 3000 -H 0.0.0.0",
    "build": "next build",
    "start": "next start -p 3000 -H 0.0.0.0"
  },
  "dependencies": {
    "next": "14.2.3",
    "react": "18.3.1",
    "react-dom": "18.3.1"
  },
  "devDependencies": {
    "typescript": "5.4.5",
    "@types/node": "20.12.12",
    "@types/react": "18.3.2",
    "@types/react-dom": "18.3.0",
    "tailwindcss": "3.4.3",
    "postcss": "8.4.38",
    "autoprefixer": "10.4.19"
  }
}
```

- [ ] **Step 2: Write config files**

`frontend/next.config.mjs`:
```js
/** @type {import('next').NextConfig} */
export default { reactStrictMode: true };
```

`frontend/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2020", "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true, "skipLibCheck": true, "strict": true,
    "noEmit": true, "esModuleInterop": true, "module": "esnext",
    "moduleResolution": "bundler", "resolveJsonModule": true,
    "isolatedModules": true, "jsx": "preserve", "incremental": true,
    "plugins": [{"name": "next"}], "paths": {"@/*": ["./*"]}
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

`frontend/tailwind.config.ts`:
```ts
import type { Config } from "tailwindcss";
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: { extend: {} }, plugins: [],
};
export default config;
```

`frontend/postcss.config.mjs`:
```js
export default { plugins: { tailwindcss: {}, autoprefixer: {} } };
```

`frontend/app/globals.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

`frontend/.env.local.example`:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

- [ ] **Step 3: Write `frontend/app/layout.tsx`**

```tsx
import "./globals.css";
export const metadata = { title: "CarSkyscanner" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pl">
      <body className="bg-gray-50 text-gray-900 min-h-screen">{children}</body>
    </html>
  );
}
```

- [ ] **Step 4: Write `frontend/lib/api.ts`**

```ts
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface Car {
  id: string; title: string | null; brand: string; model: string;
  year: number | null; price: number | null; currency: string;
  mileage: number | null; fuel_type: string | null; transmission: string | null;
  location: string | null; source: string; url: string; image_url: string | null;
  created_at: string;
}

export interface Filters {
  brand?: string; model?: string; year_min?: number; year_max?: number;
  price_min?: number; price_max?: number; mileage_max?: number;
  fuel_type?: string; transmission?: string;
}

export interface SearchResponse { items: Car[]; total: number; limit: number; offset: number; }
export interface SourceResult { found: number; saved: number; blocked: number; errors: number; }
export interface ScrapeStatus {
  status: string; job_id: string | null; started_at: string | null;
  finished_at: string | null; total_saved: number; per_source: Record<string, SourceResult>;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API}${path}`, { headers: { "Content-Type": "application/json" }, ...init });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

export const getCars = (limit = 100, offset = 0) =>
  req<SearchResponse>(`/cars?limit=${limit}&offset=${offset}`);
export const searchCars = (f: Filters) =>
  req<SearchResponse>("/search", { method: "POST", body: JSON.stringify(f) });
export const runScrape = () => req<{ job_id: string; status: string }>("/scrape/run", { method: "POST" });
export const getScrapeStatus = () => req<ScrapeStatus>("/scrape/status");
```

- [ ] **Step 5: Install + typecheck smoke**

```bash
cd frontend && npm install && npx tsc --noEmit
```
Expected: `tsc` exits 0 (no page yet — `app/page.tsx` comes in Task 17; if tsc errors on missing page, continue to Task 17 first).

- [ ] **Step 6: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): next setup and typed api client

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 17: Frontend components and page

**Files:**
- Create: `frontend/app/page.tsx`, `frontend/components/SearchForm.tsx`, `frontend/components/ResultsList.tsx`, `frontend/components/CarCard.tsx`, `frontend/components/SourceBadge.tsx`, `frontend/components/ScrapePanel.tsx`

**Interfaces:** Client components composing the API client into one page.

- [ ] **Step 1: Write `frontend/components/SourceBadge.tsx`**

```tsx
const COLORS: Record<string, string> = {
  otomoto: "bg-orange-100 text-orange-800",
  olx: "bg-blue-100 text-blue-800",
  facebook: "bg-indigo-100 text-indigo-800",
};
export function SourceBadge({ source }: { source: string }) {
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-semibold ${COLORS[source] ?? "bg-gray-200"}`}>
      {source.toUpperCase()}
    </span>
  );
}
```

- [ ] **Step 2: Write `frontend/components/CarCard.tsx`**

```tsx
import { Car } from "@/lib/api";
import { SourceBadge } from "./SourceBadge";
export function CarCard({ car }: { car: Car }) {
  return (
    <div className="bg-white rounded-lg shadow p-3 flex gap-3">
      <img src={car.image_url ?? ""} alt={car.title ?? car.brand}
           className="w-32 h-24 object-cover rounded bg-gray-200" />
      <div className="flex-1">
        <div className="flex justify-between items-start">
          <h3 className="font-semibold">{car.title ?? `${car.brand} ${car.model}`}</h3>
          <SourceBadge source={car.source} />
        </div>
        <p className="text-lg font-bold">{car.price?.toLocaleString("pl-PL")} {car.currency}</p>
        <p className="text-sm text-gray-600">
          {car.year} • {car.mileage?.toLocaleString("pl-PL")} km • {car.fuel_type} • {car.transmission}
        </p>
        <p className="text-sm text-gray-500">{car.location}</p>
        <a href={car.url} target="_blank" rel="noreferrer"
           className="inline-block mt-2 text-sm text-blue-600 hover:underline">
          Открыть объявление →
        </a>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Write `frontend/components/ResultsList.tsx`**

```tsx
import { Car } from "@/lib/api";
import { CarCard } from "./CarCard";
export function ResultsList({ cars, loading }: { cars: Car[]; loading: boolean }) {
  if (loading) return <p className="text-gray-500">Загрузка…</p>;
  if (!cars.length) return <p className="text-gray-500">Ничего не найдено.</p>;
  return <div className="grid grid-cols-1 md:grid-cols-2 gap-3">{cars.map((c) => <CarCard key={c.id} car={c} />)}</div>;
}
```

- [ ] **Step 4: Write `frontend/components/SearchForm.tsx`**

```tsx
"use client";
import { Filters } from "@/lib/api";
export function SearchForm({ onSearch }: { onSearch: (f: Filters) => void }) {
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        const fd = new FormData(e.currentTarget);
        const num = (k: string) => (fd.get(k) as string) || undefined;
        onSearch({
          brand: (fd.get("brand") as string) || undefined,
          model: (fd.get("model") as string) || undefined,
          year_min: num("year_min") ? Number(num("year_min")) : undefined,
          year_max: num("year_max") ? Number(num("year_max")) : undefined,
          price_min: num("price_min") ? Number(num("price_min")) : undefined,
          price_max: num("price_max") ? Number(num("price_max")) : undefined,
          mileage_max: num("mileage_max") ? Number(num("mileage_max")) : undefined,
          fuel_type: (fd.get("fuel_type") as string) || undefined,
          transmission: (fd.get("transmission") as string) || undefined,
        });
      }}
      className="bg-white rounded-lg shadow p-4 grid grid-cols-2 md:grid-cols-3 gap-3"
    >
      <input name="brand" placeholder="Марка" className="input" />
      <input name="model" placeholder="Модель" className="input" />
      <input name="year_min" type="number" placeholder="Год от" className="input" />
      <input name="year_max" type="number" placeholder="Год до" className="input" />
      <input name="price_min" type="number" placeholder="Цена от" className="input" />
      <input name="price_max" type="number" placeholder="Цена до" className="input" />
      <input name="mileage_max" type="number" placeholder="Пробег до (км)" className="input" />
      <select name="fuel_type" className="input">
        <option value="">Топливо</option>
        <option value="petrol">Бензин</option><option value="diesel">Дизель</option>
        <option value="hybrid">Гибрид</option><option value="electric">Электро</option>
        <option value="lpg">LPG</option>
      </select>
      <select name="transmission" className="input">
        <option value="">КПП</option>
        <option value="manual">Механика</option><option value="automatic">Автомат</option>
      </select>
      <button className="col-span-2 md:col-span-3 bg-blue-600 text-white rounded py-2 hover:bg-blue-700">
        Найти
      </button>
      <style jsx>{`.input{@apply border rounded px-2 py-1;}`}</style>
    </form>
  );
}
```

- [ ] **Step 5: Write `frontend/components/ScrapePanel.tsx`**

```tsx
"use client";
import { useEffect, useRef, useState } from "react";
import { runScrape, getScrapeStatus, ScrapeStatus } from "@/lib/api";
export function ScrapePanel() {
  const [status, setStatus] = useState<ScrapeStatus | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const poll = () => getScrapeStatus().then(setStatus).catch(() => {});
  useEffect(() => { poll(); return () => { if (timer.current) clearInterval(timer.current); }; }, []);

  const start = async () => {
    try { await runScrape(); } catch (e: any) { if (!String(e).includes("409")) alert(e); }
    timer.current = setInterval(async () => {
      await poll();
      if (status && (status.status === "done" || status.status === "error") && timer.current) {
        clearInterval(timer.current); timer.current = null;
      }
    }, 2000);
  };

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex items-center gap-3">
        <button onClick={start} className="bg-green-600 text-white rounded px-3 py-1 hover:bg-green-700">
          Запустить скрейп
        </button>
        <span className="text-sm">Статус: <b>{status?.status ?? "—"}</b></span>
      </div>
      {status && (
        <table className="mt-3 text-sm w-full">
          <thead><tr><th align="left">Источник</th><th>Найдено</th><th>Сохранено</th><th>Блок</th><th>Ошибки</th></tr></thead>
          <tbody>
            {Object.entries(status.per_source).map(([k, v]) => (
              <tr key={k}><td>{k}</td><td align="center">{v.found}</td><td align="center">{v.saved}</td>
                <td align="center">{v.blocked}</td><td align="center">{v.errors}</td></tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
```

- [ ] **Step 6: Write `frontend/app/page.tsx`**

```tsx
"use client";
import { useEffect, useState } from "react";
import { Car, Filters, getCars, searchCars } from "@/lib/api";
import { SearchForm } from "@/components/SearchForm";
import { ResultsList } from "@/components/ResultsList";
import { ScrapePanel } from "@/components/ScrapePanel";

export default function Page() {
  const [cars, setCars] = useState<Car[]>([]);
  const [loading, setLoading] = useState(true);

  const load = (f?: Filters) => {
    setLoading(true);
    const p = f && Object.values(f).some(Boolean) ? searchCars(f) : getCars();
    p.then((r) => setCars(r.items)).catch(() => setCars([])).finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);
  // refresh after a scrape completes
  useEffect(() => { const t = setInterval(() => getCars().then((r) => setCars(r.items)).catch(() => {}), 10000); return () => clearInterval(t); }, []);

  return (
    <main className="max-w-5xl mx-auto p-4 space-y-4">
      <h1 className="text-2xl font-bold">CarSkyscanner 🚗</h1>
      <SearchForm onSearch={(f) => load(f)} />
      <ScrapePanel />
      <ResultsList cars={cars} loading={loading} />
    </main>
  );
}
```

- [ ] **Step 7: Build smoke**

```bash
cd frontend && npm run build
```
Expected: build succeeds (`.next` produced). Fix any TS errors.

- [ ] **Step 8: Commit**

```bash
git add frontend/app frontend/components
git commit -m "feat(frontend): search, results, scrape UI

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 18: Docker (backend + frontend + compose)

**Files:**
- Create: `docker/Dockerfile.backend`, `docker/Dockerfile.frontend`, `docker/docker-compose.yml`

**Interfaces:** `cd docker && docker compose up --build` brings up postgres + backend(:8000) + frontend(:3000).

- [ ] **Step 1: Write `docker/Dockerfile.backend`**

```dockerfile
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
    libasound2 libpango-1.0-0 libcairo2 \
    && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt && python -m playwright install chromium --with-deps
COPY backend /app
COPY scrapers /app/scrapers
ENV PYTHONPATH=/app
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host ${BACKEND_HOST:-0.0.0.0} --port ${BACKEND_PORT:-8000}"]
```

- [ ] **Step 2: Write `docker/Dockerfile.frontend`**

```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY frontend/package.json ./
RUN npm install
COPY frontend ./
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
```

- [ ] **Step 3: Write `docker/docker-compose.yml`**

```yaml
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: carsky
      POSTGRES_PASSWORD: carsky
      POSTGRES_DB: carsky
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U carsky"]
      interval: 5s
      timeout: 5s
      retries: 10
    ports:
      - "5432:5432"

  backend:
    build:
      context: ..
      dockerfile: docker/Dockerfile.backend
    environment:
      DATABASE_URL: postgresql+psycopg2://carsky:carsky@postgres:5432/carsky
      AUTO_SEED: "true"
    depends_on:
      postgres:
        condition: service_healthy
    ports:
      - "8000:8000"

  frontend:
    build:
      context: ..
      dockerfile: docker/Dockerfile.frontend
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000
    depends_on:
      - backend
    ports:
      - "3000:3000"

volumes:
  pgdata:
```

- [ ] **Step 4: Wire auto-seed into backend startup**

Modify `backend/app/main.py` startup handler (append after `init_db()`):
```python
from app.config import settings
from app.database import SessionLocal
from app import crud

@app.on_event("startup")
def _startup():
    init_db()
    if settings.AUTO_SEED:
        from app.crud import get_cars
        db = SessionLocal()
        try:
            _, total = get_cars(db, limit=1)
            if total == 0:
                import seed
                seed.main()
        finally:
            db.close()
```

- [ ] **Step 5: Build & run smoke**

```bash
cd docker && docker compose up --build -d
docker compose ps
curl -s http://localhost:8000/health
curl -s "http://localhost:8000/cars?limit=1" | head -c 200
```
Expected: `/health` → `{"status":"ok"}`; `/cars` returns ≥1 item (seeded).

- [ ] **Step 6: Commit**

```bash
git add docker/ backend/app/main.py
git commit -m "feat: docker backend/frontend/compose with auto-seed

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 19: README finalization and acceptance check

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Rewrite `README.md`** with: overview, architecture diagram (text), quickstart (`cp .env.example .env` → `cd docker && docker compose up --build`), endpoints table, dev commands (`pytest`, `npm run dev`, `python seed.py`, `python scripts/scrape_demo.py`), a **Risks** section (live scrape may be blocked → seed data; FB stub; selectors may need updates), and the known limitations.

- [ ] **Step 2: Acceptance run-through (manual, against running stack)**

1. Open `http://localhost:3000` → page loads, seeded cars visible.
2. Set filter brand=`volkswagen`, price_max=`100000` → results filter.
3. Click "Запустить скрейп" → status goes `running` → `done` (or shows `blocked` per source).
4. Refresh → any newly scraped otomoto/olx listings appear (if not blocked).
5. `curl http://localhost:8000/docs` → Swagger shows `/cars`, `/search`, `/scrape/run`, `/scrape/status`.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: finalize README with risks and acceptance

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Self-Review (completed during authoring)

- **Spec coverage:** §1 goals → all tasks; §3 DB schema + indexes → Task 3; §4 API + filters + async runner → Tasks 5,6,7,12,13; §5 scrapers/normalizer/pipeline → Tasks 4,8,9,10,11,12; §6 frontend → Tasks 16,17; §7 docker → Task 18; §8 errors → runner try/except + 409 + frontend catch; §9 tests → Tasks 3–13; §10 seed/demo → Tasks 14,15; §11 success criteria → Task 19. No gaps.
- **Placeholders:** none left (the two illustrative stubs in Tasks 7/8 are explicitly marked "replace with" and the final code is given).
- **Type consistency:** `ScrapeResult`, `SourceResult`, `SearchFilters`, `ScrapeStatus`, `parse_html`, `manager.start/status` names match across tasks. CRUD uses `SearchFilters` (Task 6 before Task 5 — ordering note called out).
