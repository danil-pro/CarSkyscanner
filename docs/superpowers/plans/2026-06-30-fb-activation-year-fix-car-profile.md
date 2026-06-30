# FB Activation, Year-Bug Fix, Car Profile — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the wrong-year (2026/2027) bug, activate the Facebook Marketplace source, and add an in-site car profile page (`/cars/[id]`) with optional deep-scraped details — all without committing credentials.

**Architecture:** Year extraction is anchored per-source (OLX: year preceding mileage; Otomoto: the bare-year `<dd>`) plus a future-year guard in `parse_year`. FB gets feed scrolling + docs. The profile adds `GET /cars/{id}` and a Next.js Server Component; deep-scraped details add a `car_details` cache table, per-source detail parsers, and `GET /cars/{id}/details` with graceful degradation.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + PostgreSQL (Python 3.11); Next.js 14.2 app-router (Server + Client components) + Tailwind; Playwright scrapers; pytest (asyncio_mode=auto).

## Global Constraints

- **Test env:** `backend/tests/conftest.py` adds repo root to `sys.path` and gives every test a fresh SQLite DB via `Base.metadata.create_all` — new models auto-create in tests. Run unit tests fast in a host venv: `cd backend && .venv/bin/python -m pytest tests/<file>::<test> -v`. Or in docker: `docker compose -f docker/docker-compose.yml exec -T backend python -m pytest tests/<file>::<test> -v`.
- **Host venv setup (once):** `cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt` (add `.venv/bin/python -m playwright install chromium` only for browser-based tasks).
- **Docker bakes source** (only `backend/secrets` is volume-mounted): after editing backend/frontend source, rebuild to serve: `docker compose -f docker/docker-compose.yml up -d --build backend frontend`. Unit tests do **not** require a rebuild (run via host venv or rebuild + `exec`).
- **Credentials:** never commit FB phone/password or `storage_state.json`. The session file lives in `backend/secrets/` (gitignored, `.dockerignore`d, mounted `:ro` by compose).
- **Next 14:** route `params` is a plain object (`{ id: string }`), not a Promise. No i18n/locale router exists — use plain `/cars/[id]`.
- **Style:** bare Tailwind utilities (no design tokens); match existing components. Frontend has no JS test runner — verify via `npm run build` (typecheck) + manual browser check.

---

## Phase 1 — Year Fix, FB Activation, Data Repair

### Task 1: `parse_year` rejects future years

**Files:**
- Modify: `scrapers/normalizer.py:1-3` (imports), `scrapers/normalizer.py:70-74` (`parse_year`)
- Test: `backend/tests/test_normalizer.py`

**Interfaces:**
- Produces: `parse_year(value, now_year: Optional[int] = None) -> Optional[int]` — returns `None` when `year > now_year + 1`; `now_year` defaults to today's year. Existing callers (`normalize` at `normalizer.py:129`) pass one arg and are unaffected.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_normalizer.py`:
```python
def test_parse_year_rejects_future_years():
    # 2027 is future relative to now_year=2026 -> rejected
    assert parse_year("2027", now_year=2026) is None
    assert parse_year("2099", now_year=2026) is None
    # current year is allowed (proves the guard alone does NOT fix the 2026 date bug)
    assert parse_year("2026", now_year=2026) == 2026
    assert parse_year("2019", now_year=2026) == 2019
    assert parse_year(None) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_normalizer.py::test_parse_year_rejects_future_years -v`
Expected: FAIL — `TypeError: parse_year() got an unexpected keyword argument 'now_year'`.

- [ ] **Step 3: Implement**

In `scrapers/normalizer.py`, add the date import at the top (after `import re`):
```python
from datetime import date
```
Replace `parse_year` (lines 70-74) with:
```python
def parse_year(value, now_year: Optional[int] = None) -> Optional[int]:
    if not value:
        return None
    m = re.search(r"(19|20)\d{2}", str(value))
    if not m:
        return None
    y = int(m.group())
    if now_year is None:
        now_year = date.today().year
    return y if y <= now_year + 1 else None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_normalizer.py -v`
Expected: PASS (all 8 tests, including the existing `test_parse_year`).

- [ ] **Step 5: Commit**

```bash
git add scrapers/normalizer.py backend/tests/test_normalizer.py
git commit -m "fix(normalizer): reject future years in parse_year (> now+1)"
```

---

### Task 2: OLX year anchored to the spec line (not the listing date)

**Files:**
- Modify: `scrapers/olx.py:16` (regex), `scrapers/olx.py:25` (group index)
- Test: `backend/tests/test_providers.py`

**Interfaces:** none new (internal to `parse_html`).

**Why:** production OLX card text is `"...55 999 zł ... Przysucha - 31 maja 2026 2019 - 110 480 km..."`. The current `re.search(r"(19|20)\d{2}", meta)` grabs the leftmost token — the date `2026` — not the real year `2019`. The real year is the token immediately before ` <digits> km`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_providers.py`:
```python
def test_olx_parse_year_ignores_listing_date():
    # Real OLX shape: a listing date "... 31 maja 2026" precedes the real "2019 - 110 480 km".
    html = """
    <html><body>
    <div data-cy="l-card">
      <a href="/d/oferta/vw-polo-ID1.html"><h6>VW Polo</h6></a>
      <span data-testid="ad-price">55 999 zł</span>
      <p>Przysucha - 31 maja 2026 2019 - 110 480 km Benzyna</p>
    </div>
    </body></html>
    """
    listings = parse_html(html)
    assert listings[0]["year"] == "2019"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_providers.py::test_olx_parse_year_ignores_listing_date -v`
Expected: FAIL — `assert '2026' == '2019'`.

- [ ] **Step 3: Implement**

In `scrapers/olx.py`, replace line 16:
```python
        year = re.search(r"(19|20)\d{2}", meta)
```
with:
```python
        # Anchor the year to the spec line "YEAR - MILEAGE km" (or "YEAR · MILEAGE km").
        # Without this, a listing date like "31 maja 2026" is grabbed before the real year.
        year = re.search(r"((?:19|20)\d{2})\D{0,3}\d[\d ]*?km", meta)
```
and change line 25 from `year.group(0)` to `year.group(1)` (the year capture group):
```python
            "year": year.group(1) if year else None,
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_providers.py -v`
Expected: PASS — new test passes; existing `test_olx_parse_source_by_domain` still passes (its fixture `2018 · 150 000 km` still yields `2018`).

- [ ] **Step 5: Commit**

```bash
git add scrapers/olx.py backend/tests/test_providers.py
git commit -m "fix(olx): anchor year to the YEAR-MILEAGE spec line, not the listing date"
```

---

### Task 3: Otomoto picks the bare-year `<dd>` (not the price slot)

**Files:**
- Modify: `scrapers/otomoto.py:3` (import `re`), `scrapers/otomoto.py:9-34` (add `_pick_year`, use it)
- Test: `backend/tests/test_providers.py`

**Why:** `dds[0]` is the price (`'89 900 PLN'`), not the year; the year is a later bare-4-digit `<dd>` (`'2018'`). `parse_year(dds[0])` grabs any `2026` token from the wrong slot.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_providers.py`:
```python
def test_otomoto_parse_year_picks_year_not_price():
    from scrapers.otomoto import parse_html
    # dd[0] is the price; the bare year '2008' is later. dds[0] used to win with a stray token.
    html = """
    <html><body>
    <div data-testid="listing-ad">
      <a href="/osobowe/peugeot-207-ID1.html"></a>
      <span data-testid="ad-price">4 200 zł</span>
      <dd>4 200 PLN</dd><dd>2008</dd><dd>Benzyna</dd><dd>Manualna</dd><dd>150 tys. km</dd><dd>Warszawa</dd>
    </div>
    </body></html>
    """
    listings = parse_html(html)
    assert listings[0]["year"] == "2008"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_providers.py::test_otomoto_parse_year_picks_year_not_price -v`
Expected: FAIL — `assert '4 200 PLN' == '2008'` (or the price-derived value).

- [ ] **Step 3: Implement**

In `scrapers/otomoto.py`, add the import after line 2 (`from urllib.parse import quote`):
```python
import re
```
Add a helper above `parse_html` (after the `BASE_URL` line):
```python
def _pick_year(dds: list[str]) -> str | None:
    """Return the first <dd> that is a bare plausible year (e.g. '2018'), not a price/date slot."""
    for d in dds:
        s = d.strip()
        if re.fullmatch(r"(19|20)\d{2}", s):
            y = int(s)
            if 1950 <= y <= 2030:  # loose bound; parse_year re-checks against today
                return s
    return None
```
Replace line 24 (`"year": dds[0] if len(dds) > 0 else None,`) with:
```python
            "year": _pick_year(dds),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_providers.py tests/test_normalizer.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scrapers/otomoto.py backend/tests/test_providers.py
git commit -m "fix(otomoto): pick the bare-year <dd> instead of the price slot dds[0]"
```

---

### Task 4: Facebook provider scrolls the feed (so `found > 0`)

**Files:**
- Modify: `scrapers/facebook.py:101-108` (insert scroll before parsing)

**Why:** `FacebookProvider.search()` overrides `BaseScraper.run()` and never scrolls, so lazy Marketplace items never render → `found=0` even with a valid session.

- [ ] **Step 1: Implement the scroll**

In `scrapers/facebook.py`, inside `search()`, **after** the login-marker check (the `if any(m in current ...)` block ending at line 106) and **before** the `raw = ...` line (107), insert:
```python
            # Scroll to render lazy-loaded Marketplace items (otherwise found=0).
            try:
                for _ in range(6):
                    await page.evaluate("window.scrollBy(0, window.innerHeight)")
                    await page.wait_for_timeout(400)
                await page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
```

- [ ] **Step 2: Verify no regression in unit tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_providers.py -v`
Expected: PASS (the scroll is inside `search()`; `_parse` tests are unaffected).

- [ ] **Step 3: Integration verification (manual, needs a session)**

After the operator captures a session (see Task 6), trigger `POST /search/live` with `{"brand":"volkswagen"}` and confirm `per_source.facebook.status == "ok"` and `found > 0`. (Scroll is a Playwright interaction; it cannot be cleanly unit-tested, so integration is the gate.)

- [ ] **Step 4: Commit**

```bash
git add scrapers/facebook.py
git commit -m "fix(facebook): scroll the marketplace feed so lazy items render (found>0)"
```

---

### Task 5: Document FB activation (`FB_STORAGE_STATE_PATH` + README)

**Files:**
- Modify: `.env.example:6-9`
- Modify: `README.md` (FB-related lines)

- [ ] **Step 1: Add the FB var to `.env.example`**

In `.env.example`, after the `AUTO_SEED=true` line (line 6) and before the `# Frontend` section, insert:
```
# Facebook Marketplace (optional). Path to a Playwright storage_state.json captured by
# `python scripts/fb_login.py` (headed; you complete any 2FA in the browser).
# Leave unset to disable FB; the file is gitignored and mounted read-only by compose.
FB_STORAGE_STATE_PATH=backend/secrets/fb_storage_state.json
```

- [ ] **Step 2: Fix stale README wording**

In `README.md`, replace these exact strings:
- `plus a Facebook Marketplace stub` → `plus Facebook Marketplace (live via a saved login session)`
- `facebook.py (stub)` → `facebook.py (live via /search/live with a saved session)`
- The sentence containing `Facebook Marketplace is a stub. It requires an authenticated session, which is out of MVP scope.` → `Facebook Marketplace is live via /search/live. It requires a saved login session (storage_state.json), captured by running \`python scripts/fb_login.py\` in a headed browser (the operator completes any 2FA). Without the session file the source reports \`session-not-configured\`.`
- `No real Facebook data (stub only).` → `Facebook data requires a saved session (see FB activation).`

- [ ] **Step 3: Commit**

```bash
git add .env.example README.md
git commit -m "docs(fb): document FB_STORAGE_STATE_PATH and the session-capture flow"
```

---

### Task 6: Repair existing wrong-year rows + deliver FB runbook

**Files:** none (operational commands).

- [ ] **Step 1: Inspect the damage (before)**

Run:
```bash
docker compose -f docker/docker-compose.yml exec -T postgres psql -U carsky -d carsky -c \
  "SELECT source, year, COUNT(*) FROM cars WHERE source IN ('olx','otomoto') AND year IN (2026,2027) GROUP BY source, year ORDER BY source, year;"
```
Expected: rows for olx (≈113×2026, 1×2027) and otomoto (≈48×2026, 1×2027).

- [ ] **Step 2: Null the implausible years**

Run:
```bash
docker compose -f docker/docker-compose.yml exec -T postgres psql -U carsky -d carsky -c \
  "UPDATE cars SET year=NULL WHERE source IN ('olx','otomoto') AND year IN (2026,2027);"
```
Expected: `UPDATE 16x` (≈163 rows). These repopulate with correct years on the next live search via the fixed parser. (Genuine 2026 cars, if any, are a temporary self-healing loss.)

- [ ] **Step 3: Verify (after)**

Re-run the Step 1 query → expect 0 rows.

- [ ] **Step 4: Deliver the FB capture runbook to the operator**

Tell the operator to run, once, on the host (in a real browser; they complete any 2FA):
```bash
FB_STORAGE_STATE_PATH=backend/secrets/fb_storage_state.json python scripts/fb_login.py
```
Then rebuild+restart and run a live search: `docker compose -f docker/docker-compose.yml up -d --build backend` → `POST /search/live {"brand":"volkswagen"}` → expect `per_source.facebook.status == "ok"`.

- [ ] **Step 5: No commit** (operational only). Note completion in the task handoff.

---

## Phase 2 — Car Profile (base)

### Task 7: Backend `GET /cars/{id}`

**Files:**
- Modify: `backend/app/crud.py` (add `get_car`)
- Modify: `backend/app/routers/cars.py:1-21` (add `uuid` import, `get_car` route)
- Test: `backend/tests/test_cars_api.py` (create)

**Interfaces:**
- Produces: `crud.get_car(db, car_id) -> Car | None`; HTTP `GET /cars/{car_id}` → `schemas.CarOut` or `404`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_cars_api.py`:
```python
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app import crud
from app.database import SessionLocal


def _make_car(**over):
    db = SessionLocal()
    try:
        car = crud.upsert_car(db, {
            "title": "X", "brand": "volkswagen", "model": "golf", "year": 2019,
            "price": 50000, "currency": "PLN", "source": "olx",
            "url": "https://olx.pl/d/" + uuid.uuid4().hex,
        } | over)
        return car
    finally:
        db.close()


def test_get_car_by_id_404():
    c = TestClient(app)
    assert c.get(f"/cars/{uuid.uuid4()}").status_code == 404


def test_get_car_by_id_ok():
    c = TestClient(app)
    car = _make_car()
    r = c.get(f"/cars/{car.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == str(car.id)
    assert body["year"] == 2019
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_cars_api.py -v`
Expected: FAIL — `404` for both (route doesn't exist) or AttributeError on `crud.get_car`.

- [ ] **Step 3: Implement**

In `backend/app/crud.py`, add after `upsert_car`:
```python
def get_car(db: Session, car_id) -> Car | None:
    return db.get(Car, car_id)
```
In `backend/app/routers/cars.py`, change the imports (line 1) to:
```python
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
```
and append after the `search` route:
```python
@router.get("/cars/{car_id}", response_model=schemas.CarOut)
def get_car(car_id: uuid.UUID, db: Session = Depends(get_db)):
    car = crud.get_car(db, car_id)
    if car is None:
        raise HTTPException(status_code=404, detail="car not found")
    return car
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_cars_api.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/crud.py backend/app/routers/cars.py backend/tests/test_cars_api.py
git commit -m "feat(api): add GET /cars/{id} single-car endpoint"
```

---

### Task 8: Frontend profile page + clickable card

**Files:**
- Modify: `frontend/lib/api.ts:46` (add `getCar`)
- Modify: `frontend/components/CarCard.tsx` (whole card → `<Link>`)
- Create: `frontend/app/cars/[id]/page.tsx`

**Interfaces:**
- Produces: `getCar(id)`; route `/cars/[id]` (Server Component).

- [ ] **Step 1: Add `getCar` to the API client**

In `frontend/lib/api.ts`, after `getCars` (line 31), add:
```typescript
export const getCar = (id: string) => req<Car>(`/cars/${id}`);
```

- [ ] **Step 2: Make the whole card link to the profile**

Replace `frontend/components/CarCard.tsx` with:
```tsx
import Link from "next/link";
import { Car } from "@/lib/api";
import { SourceBadge } from "./SourceBadge";

export function CarCard({ car }: { car: Car }) {
  return (
    <Link
      href={`/cars/${car.id}`}
      className="bg-white rounded-lg shadow p-3 flex gap-3 hover:shadow-md transition"
    >
      {car.image_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={car.image_url}
          alt={car.title ?? `${car.brand} ${car.model}`}
          className="w-32 h-24 object-cover rounded bg-gray-200 shrink-0"
        />
      ) : (
        <div className="w-32 h-24 rounded bg-gray-100 shrink-0 flex items-center justify-center text-gray-400 text-xs text-center px-1">
          Нет фото
        </div>
      )}
      <div className="flex-1 min-w-0">
        <div className="flex justify-between items-start gap-2">
          <h3 className="font-semibold truncate">
            {car.title ?? `${car.brand} ${car.model}`}
          </h3>
          <SourceBadge source={car.source} />
        </div>
        <p className="text-lg font-bold">
          {car.price?.toLocaleString("pl-PL")} {car.currency}
        </p>
        <p className="text-sm text-gray-600">
          {car.year} • {car.mileage?.toLocaleString("pl-PL")} km •{" "}
          {car.fuel_type} • {car.transmission}
        </p>
        <p className="text-sm text-gray-500">{car.location}</p>
      </div>
    </Link>
  );
}
```
(The external "Open original" link moves to the profile page in Step 3.)

- [ ] **Step 3: Create the profile Server Component**

Create `frontend/app/cars/[id]/page.tsx`:
```tsx
import { notFound } from "next/navigation";
import { Car } from "@/lib/api";
import { SourceBadge } from "@/components/SourceBadge";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function fetchCar(id: string): Promise<Car | null> {
  const r = await fetch(`${API}/cars/${id}`, { cache: "no-store" });
  if (!r.ok) return null;
  return r.json();
}

export default async function CarProfile({ params }: { params: { id: string } }) {
  const car = await fetchCar(params.id);
  if (!car) notFound();

  return (
    <main className="max-w-3xl mx-auto p-4 space-y-4">
      <a href="/" className="text-sm text-blue-600 hover:underline">← Назад к поиску</a>
      <div className="bg-white rounded-lg shadow p-4 flex flex-col md:flex-row gap-4">
        {car.image_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={car.image_url} alt={car.title ?? ""} className="w-full md:w-80 h-60 object-cover rounded bg-gray-200" />
        ) : (
          <div className="w-full md:w-80 h-60 rounded bg-gray-100 flex items-center justify-center text-gray-400">Нет фото</div>
        )}
        <div className="flex-1 space-y-2">
          <div className="flex justify-between items-start gap-2">
            <h1 className="text-xl font-bold">{car.title ?? `${car.brand} ${car.model}`}</h1>
            <SourceBadge source={car.source} />
          </div>
          <p className="text-2xl font-bold">{car.price?.toLocaleString("pl-PL")} {car.currency}</p>
          <table className="text-sm w-full">
            <tbody>
              <tr><td className="text-gray-500 pr-4">Год</td><td>{car.year ?? "—"}</td></tr>
              <tr><td className="text-gray-500 pr-4">Пробег</td><td>{car.mileage ? `${car.mileage.toLocaleString("pl-PL")} km` : "—"}</td></tr>
              <tr><td className="text-gray-500 pr-4">Топливо</td><td>{car.fuel_type ?? "—"}</td></tr>
              <tr><td className="text-gray-500 pr-4">КПП</td><td>{car.transmission ?? "—"}</td></tr>
              <tr><td className="text-gray-500 pr-4">Локация</td><td>{car.location ?? "—"}</td></tr>
            </tbody>
          </table>
          <a href={car.url} target="_blank" rel="noreferrer" className="inline-block mt-2 text-sm text-blue-600 hover:underline">
            Открыть оригинал объявления →
          </a>
        </div>
      </div>
    </main>
  );
}
```

- [ ] **Step 4: Typecheck + manual verify**

Run: `cd frontend && npm run build` (host) or `docker compose -f docker/docker-compose.yml exec -T frontend npm run build`.
Expected: build succeeds (no type errors). Then `docker compose ... up -d --build frontend`, open `http://localhost:3000`, click a car → lands on `/cars/<id>` showing the spec table + "Открыть оригинал"; a bad id shows 404.

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/api.ts frontend/components/CarCard.tsx frontend/app/cars/
git commit -m "feat(frontend): in-site car profile page /cars/[id] + clickable card"
```

---

## Phase 3 — Deep-Scraped Details (cached, graceful)

### Task 9: `CarDetail` model + relationship

**Files:**
- Modify: `backend/app/models.py:3` (imports), `backend/app/models.py:12-38` (relationship), append `CarDetail`
- Test: `backend/tests/test_models.py` (create)

**Interfaces:**
- Produces: `CarDetail` ORM model (table `car_details`); `Car.details` relationship. Auto-created on startup by `init_db()` (`Base.metadata.create_all`) and in tests by conftest.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_models.py`:
```python
from app.models import Car, CarDetail
from app import crud
from app.database import SessionLocal


def test_car_detail_roundtrip():
    db = SessionLocal()
    try:
        car = crud.upsert_car(db, {"title": "X", "brand": "vw", "model": "golf",
                                   "year": 2019, "price": 1000, "currency": "PLN",
                                   "source": "olx", "url": "https://olx.pl/d/d1"})
        d = CarDetail(car_id=car.id, description="Idealny stan", images=["a.jpg", "b.jpg"], status="ok")
        db.add(d)
        db.commit()
        got = db.get(CarDetail, car.id)
        assert got is not None
        assert got.description == "Idealny stan"
        assert got.images == ["a.jpg", "b.jpg"]
    finally:
        db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_models.py -v`
Expected: FAIL — `cannot import name 'CarDetail'`.

- [ ] **Step 3: Implement**

In `backend/app/models.py`, replace line 3 with:
```python
from sqlalchemy import String, Integer, Numeric, Index, Uuid, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
```
Inside the `Car` class, add a relationship (e.g. after `created_at` at line 30):
```python
    details: Mapped["CarDetail"] = relationship(back_populates="car", uselist=False, cascade="all, delete-orphan")
```
Append the new model at the end of the file:
```python
class CarDetail(Base):
    __tablename__ = "car_details"
    car_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("cars.id"), primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    images: Mapped[list] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ok")
    fetched_at: Mapped[datetime] = mapped_column(default=_now, nullable=False)

    car: Mapped["Car"] = relationship(back_populates="details")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_models.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models.py backend/tests/test_models.py
git commit -m "feat(models): add CarDetail (cached listing details) table + relationship"
```

---

### Task 10: Per-source detail parsers (description + images)

**Files:**
- Create: `scrapers/details.py`
- Create: `backend/tests/test_details_parsers.py`

**Interfaces:**
- Produces: `parse_detail(source: str, html: str, base_url: str) -> {"description": str|None, "images": list[str]}`. Dispatches to `_parse_olx`, `_parse_otomoto`, `_parse_facebook`. Best-effort selectors with broad fallbacks; returns empty values (never raises) when the DOM doesn't match — graceful degradation.

> **Note:** exact detail-page selectors are best-effort and must be validated against live HTML during integration (Task 12, Step 3). The tests below fix the contract against representative fixtures; degradation is the safety net for DOM drift / anti-bot blocks.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_details_parsers.py`:
```python
from scrapers.details import parse_detail


def test_parse_olx_detail():
    html = """
    <html><body>
      <div data-cy="ad_description"><p>Auto w stanie idealnym. Pierwszy właściciel.</p></div>
      <img data-src="https://ireland.apollo.olxcdn.com/a.jpg"/>
      <img data-src="https://ireland.apollo.olxcdn.com/b.jpg"/>
    </body></html>
    """
    out = parse_detail("olx", html, "https://www.olx.pl")
    assert "idealnym" in (out["description"] or "").lower()
    assert out["images"] == ["https://ireland.apollo.olxcdn.com/a.jpg", "https://ireland.apollo.olxcdn.com/b.jpg"]


def test_parse_unknown_source_returns_empty_without_raising():
    out = parse_detail("mysource", "<html></html>", "https://x")
    assert out == {"description": None, "images": []}
```

- [ ] **Step 2: Run tests to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_details_parsers.py -v`
Expected: FAIL — `ModuleNotFoundError: scrapers.details`.

- [ ] **Step 3: Implement**

Create `scrapers/details.py`:
```python
from typing import Optional
from bs4 import BeautifulSoup
from scrapers.base import resolve_url


def _images(soup, base_url: str) -> list[str]:
    seen, out = set(), []
    for img in soup.select("img"):
        for attr in ("src", "data-src", "data-lazy-src"):
            val = img.get(attr)
            if val:
                u = resolve_url(base_url, val.split(",")[0])
                if u and u not in seen:
                    seen.add(u)
                    out.append(u)
                    break
    return out


def _description(soup, selectors: tuple[str, ...]) -> Optional[str]:
    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            txt = el.get_text(" ", strip=True)
            if len(txt) >= 20:
                return txt[:5000]
    return None


def _parse_olx(html: str, base_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    return {
        "description": _description(soup, ('[data-cy="ad_description"]', 'div[aria-label="Opis"]', ".descriptioncontent")),
        "images": _images(soup, base_url),
    }


def _parse_otomoto(html: str, base_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    return {
        "description": _description(soup, ('[data-testid="content-container"]', 'div[data-role="offer-description"]', "#description")),
        "images": _images(soup, base_url),
    }


def _parse_facebook(html: str, base_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    return {
        "description": _description(soup, ('[data-singular="true"]', 'div[role="main"]', "span")),
        "images": _images(soup, base_url),
    }


_PARSERS = {"olx": _parse_olx, "otomoto": _parse_otomoto, "facebook": _parse_facebook}


def parse_detail(source: str, html: str, base_url: str) -> dict:
    """Best-effort extraction of {description, images}. Never raises."""
    parser = _PARSERS.get((source or "").lower())
    if parser is None:
        return {"description": None, "images": []}
    try:
        return parser(html, base_url)
    except Exception:
        return {"description": None, "images": []}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_details_parsers.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scrapers/details.py backend/tests/test_details_parsers.py
git commit -m "feat(scrapers): per-source detail parsers (description + images) with fallbacks"
```

---

### Task 11: Detail fetch service + `GET /cars/{id}/details` (cached, graceful)

**Files:**
- Modify: `backend/app/config.py` (add `DETAILS_TTL_S`)
- Create: `backend/app/detail_service.py`
- Modify: `backend/app/crud.py` (add `get_detail`, `upsert_detail`)
- Modify: `backend/app/schemas.py` (add `CarDetailsOut`)
- Modify: `backend/app/routers/cars.py` (add route)
- Test: `backend/tests/test_details_api.py` (create)

**Interfaces:**
- Produces: `crud.get_detail(db, car_id)`, `crud.upsert_detail(db, car_id, data)`; `detail_service.fetch_details(car, fetcher=...) -> dict`; HTTP `GET /cars/{id}/details` → `CarDetailsOut` or `404`.
- Design: TTL-cached in `car_details`; on miss, fetch via Playwright (stealth; FB uses session); on any failure return `status="unavailable"`. A fetcher seam makes the endpoint unit-testable without a browser.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_details_api.py`:
```python
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app import crud
from app.database import SessionLocal


def _make_car():
    db = SessionLocal()
    try:
        return crud.upsert_car(db, {"title": "X", "brand": "vw", "model": "golf", "year": 2019,
                                    "price": 1000, "currency": "PLN", "source": "olx",
                                    "url": "https://olx.pl/d/" + uuid.uuid4().hex})
    finally:
        db.close()


def test_details_404_for_missing_car():
    c = TestClient(app)
    assert c.get(f"/cars/{uuid.uuid4()}/details").status_code == 404


def test_details_fetches_and_caches(monkeypatch):
    from app import detail_service
    car = _make_car()
    monkeypatch.setattr(detail_service, "DEFAULT_FETCHER",
                        lambda c: {"description": "ok desc", "images": ["i.jpg"], "status": "ok"})
    c = TestClient(app)
    r1 = c.get(f"/cars/{car.id}/details")
    assert r1.status_code == 200 and r1.json()["description"] == "ok desc"
    # second call is served from cache (fetcher would raise if called again)
    monkeypatch.setattr(detail_service, "DEFAULT_FETCHER",
                        lambda c: (_ for _ in ()).throw(AssertionError("should be cached")))
    r2 = c.get(f"/cars/{car.id}/details")
    assert r2.status_code == 200 and r2.json()["description"] == "ok desc"


def test_details_graceful_when_fetch_fails(monkeypatch):
    from app import detail_service
    car = _make_car()
    def boom(_c):
        raise RuntimeError("blocked")
    monkeypatch.setattr(detail_service, "DEFAULT_FETCHER", boom)
    c = TestClient(app)
    r = c.get(f"/cars/{car.id}/details")
    assert r.status_code == 200
    assert r.json()["status"] == "unavailable"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/test_details_api.py -v`
Expected: FAIL — route missing / module import errors.

- [ ] **Step 3: Add TTL config**

In `backend/app/config.py`, add a field next to the other settings:
```python
    DETAILS_TTL_S: int = 43200  # 12h cache for scraped listing details
```

- [ ] **Step 4: Add crud helpers**

In `backend/app/crud.py`, import the model and add (after `get_car`):
```python
from app.models import Car, CarDetail
...
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
```
(Add `from datetime import datetime, timezone` to crud.py imports.)

- [ ] **Step 5: Create the detail service**

Create `backend/app/detail_service.py`:
```python
import asyncio
from typing import Callable, Optional
from playwright.async_api import async_playwright
from scrapers.base import USER_AGENT, STEALTH_INIT
from scrapers.details import parse_detail
from app.config import settings

_BASE = {"olx": "https://www.olx.pl", "otomoto": "https://www.otomoto.pl", "facebook": "https://www.facebook.com"}

# A seam for tests: DEFAULT_FETCHER(car) -> {"description","images","status"} (may raise).
DEFAULT_FETCHER: Callable = None  # set below


async def _fetch_via_playwright(car) -> dict:
    base = _BASE.get((car.source or "").lower(), "https://example.com")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=[
            "--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"])
        ctx_kwargs = dict(user_agent=USER_AGENT, locale="pl-PL", viewport={"width": 1366, "height": 800})
        if car.source == "facebook":
            path = settings.FB_STORAGE_STATE_PATH
            if not path:
                return {"description": None, "images": [], "status": "unavailable"}
            ctx_kwargs["storage_state"] = path
        ctx = await browser.new_context(**ctx_kwargs)
        await ctx.add_init_script(STEALTH_INIT)
        page = await ctx.new_page()
        try:
            await page.goto(car.url, timeout=45000, wait_until="domcontentloaded")
            html = await page.content()
            return parse_detail(car.source, html, base)
        finally:
            await browser.close()


def _fetch(car) -> dict:
    return asyncio.run(_fetch_via_playwright(car))


DEFAULT_FETCHER = _fetch


def fetch_details(car, fetcher: Optional[Callable] = None) -> dict:
    f = fetcher or DEFAULT_FETCHER
    try:
        out = f(car)
        return {"description": out.get("description"), "images": out.get("images") or [],
                "status": out.get("status", "ok")}
    except Exception:
        return {"description": None, "images": [], "status": "unavailable"}
```

- [ ] **Step 6: Add schema + route**

In `backend/app/schemas.py`, append:
```python
class CarDetailsOut(BaseModel):
    description: Optional[str] = None
    images: list[str] = []
    status: str
    fetched_at: Optional[datetime] = None
```
In `backend/app/routers/cars.py`, import datetime and add (after the `get_car` route):
```python
from datetime import datetime, timedelta, timezone
from app import detail_service
from app.config import settings
...
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
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_details_api.py -v`
Expected: PASS — 404, fetch+cache, graceful-unavailable.

- [ ] **Step 8: Commit**

```bash
git add backend/app/config.py backend/app/crud.py backend/app/schemas.py backend/app/routers/cars.py backend/app/detail_service.py backend/tests/test_details_api.py
git commit -m "feat(api): GET /cars/{id}/details with TTL cache + graceful degradation"
```

---

### Task 12: Frontend details panel + wiring

**Files:**
- Modify: `frontend/lib/api.ts` (add `getCarDetails`, `CarDetails`)
- Create: `frontend/components/DetailsPanel.tsx`
- Modify: `frontend/app/cars/[id]/page.tsx` (embed the panel)

- [ ] **Step 1: Add types + fetcher to the API client**

In `frontend/lib/api.ts`, add:
```typescript
export interface CarDetails { description: string | null; images: string[]; status: string; fetched_at: string | null; }
export const getCarDetails = (id: string) => req<CarDetails>(`/cars/${id}/details`);
```

- [ ] **Step 2: Create the client panel**

Create `frontend/components/DetailsPanel.tsx`:
```tsx
"use client";
import { useEffect, useState } from "react";
import { CarDetails, getCarDetails } from "@/lib/api";

export function DetailsPanel({ carId }: { carId: string }) {
  const [d, setD] = useState<CarDetails | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    getCarDetails(carId)
      .then((r) => alive && setD(r))
      .catch(() => alive && setD(null))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [carId]);

  if (loading) return <p className="text-sm text-gray-500">Загрузка деталей…</p>;
  if (!d || d.status !== "ok") {
    // graceful degradation: nothing to show; the base profile + "open original" still work
    return <p className="text-sm text-gray-400">Детали недоступны — см. оригинал объявления.</p>;
  }
  return (
    <div className="space-y-3">
      {d.description && (
        <div>
          <h2 className="font-semibold mb-1">Описание</h2>
          <p className="text-sm text-gray-700 whitespace-pre-line">{d.description}</p>
        </div>
      )}
      {d.images.length > 0 && (
        <div>
          <h2 className="font-semibold mb-1">Фото</h2>
          <div className="grid grid-cols-3 gap-2">
            {d.images.slice(0, 12).map((src) => (
              // eslint-disable-next-line @next/next/no-img-element
              <img key={src} src={src} alt="" className="w-full h-24 object-cover rounded bg-gray-200" />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Embed the panel in the profile**

In `frontend/app/cars/[id]/page.tsx`, import and render it below the car card block (inside `<main>`, after the closing `</div>` of the car block):
```tsx
import { DetailsPanel } from "@/components/DetailsPanel";
...
      </div>  {/* end car block */}
      <DetailsPanel carId={params.id} />
    </main>
```

- [ ] **Step 4: Typecheck + manual verify (integration)**

Run: `cd frontend && npm run build` → expect success. Then `docker compose -f docker/docker-compose.yml up -d --build backend frontend`, open a car profile, and confirm:
- Base spec table renders immediately.
- Details panel loads: shows description + gallery when the source is reachable (`status=ok`); shows the graceful message when blocked/unavailable.
- Also validate the Task 10 selectors against **live** HTML here: if description/images are empty on a known-good listing, adjust the selectors in `scrapers/details.py` (this is the integration gate noted in Task 10).

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/api.ts frontend/components/DetailsPanel.tsx frontend/app/cars/[id]/page.tsx
git commit -m "feat(frontend): cached details panel on the car profile (graceful degradation)"
```

---

## Final verification

- [ ] `cd backend && .venv/bin/python -m pytest -v` — full suite green.
- [ ] `cd frontend && npm run build` — typecheck clean.
- [ ] `docker compose -f docker/docker-compose.yml up -d --build backend frontend` — app serves.
- [ ] Year bug: search results no longer show 2026/2027 for olx/otomoto; the repair query returns 0 rows.
- [ ] FB: with a captured session, `POST /search/live` returns `facebook` `status=ok`, `found>0`.
- [ ] Profile: `/cars/<id>` shows base fields + (when reachable) details; whole card is clickable; "Открыть оригинал" still present.

## Notes / risks carried from the spec

- **Detail-page selectors are best-effort** — validated against live HTML in Task 12 Step 4; degradation hides them gracefully if a source blocks or changes its DOM.
- **FB session expiry / 2FA** — operator re-runs `fb_login.py`; surfaces as `session-invalid`.
- **Stampede** — concurrent uncached detail fetches for the same car are not locked; acceptable for current load (add a per-id lock if traffic grows).
- **Docker rebuild required** to serve any backend/frontend change (source is baked).
