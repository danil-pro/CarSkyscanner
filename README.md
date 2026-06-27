# CarSkyscanner

Car listing aggregator MVP for the Polish market. It pulls car listings from
**Otomoto** and **OLX** (live, via Playwright), plus a **Facebook Marketplace**
stub, normalizes them into a single schema, stores them in PostgreSQL, and
exposes a filtered search through a FastAPI backend and a Next.js frontend.

The full design spec lives in
`docs/superpowers/specs/2026-06-26-car-aggregator-mvp-design.md`.

---

## Architecture

```
                       ┌───────────────┐
   Otomoto (Playwright)│               │
   OLX      (Playwright)│  scrapers/    │  raw HTML/listings
   Facebook (stub)     │  base/otomoto/│ ──────────────┐
                       │  olx/facebook │               ▼
                       └───────┬───────┘        ┌─────────────┐
                               │                │ normalizer  │ → normalized dict
                               │                └──────┬──────┘
                               │                       │
                       ┌───────▼───────────────────────▼─────┐
                       │ backend/app/scraper_runner.py        │  ScrapeJobManager
                       │ (async, in-memory job lifecycle)     │  start() / status()
                       └───────┬───────────────────────────┬──┘
                               │ upsert_car()              │
                       ┌───────▼───────┐          ┌────────▼────────┐
                       │  PostgreSQL   │◄─────────│  CRUD (search)  │
                       │  cars table   │          └────────┬────────┘
                       └───────────────┘                   │
                               ▲                           │
                               │ seed.py (40 demo cars)    │ JSON
                               │                           ▼
                       ┌───────┴───────┐          ┌─────────────────┐
                       │   backend     │◄─────────│  frontend (Next)│
                       │ FastAPI +     │  HTTP    │  search form,   │
                       │ SQLAlchemy    │          │  results, scrape│
                       └───────────────┘          └─────────────────┘
```

**Layers**

| Layer | Path | Responsibility |
|-------|------|----------------|
| Scrapers | `scrapers/` | `BaseScraper` (Playwright launch, block detection), `otomoto.py`, `olx.py`, `facebook.py` (stub), `normalizer.py` (raw → canonical dict) |
| Runner | `backend/app/scraper_runner.py` | `ScrapeJobManager` — single in-memory async job, per-source counters, `idle\|running\|done\|error` lifecycle |
| API | `backend/app/routers/` | `cars.py` (`/cars`, `/search`), `scrape.py` (`/scrape/run`, `/scrape/status`) |
| Persistence | `backend/app/models.py`, `crud.py`, `database.py` | SQLAlchemy `Car` model, `upsert_car` (dedupe by source+url), filtered search |
| Frontend | `frontend/` | Next.js 14 app: `SearchForm`, `ResultsList`/`CarCard`, `ScrapePanel`, `SourceBadge`; typed client in `lib/api.ts` |
| Infra | `docker/` | `docker-compose.yml` (postgres + backend + frontend), `Dockerfile.backend`, `Dockerfile.frontend` |

Scraping is async and headless. On `/scrape/run` the runner launches one
Chromium instance, iterates the three scrapers, detects block pages (DataDome /
captcha / HTTP >= 400), normalizes surviving listings, and upserts them. Each
source reports `found / saved / blocked / errors`.

---

## Quickstart (Docker, full stack)

```bash
cp .env.example .env
cd docker && docker compose up --build
```

Then open:

- **Frontend:** http://localhost:3000
- **API docs (Swagger):** http://localhost:8000/docs
- **Health:** http://localhost:8000/health

On first start the backend auto-seeds 40 demo cars (`AUTO_SEED=true`), so the
frontend shows listings immediately even before any live scrape runs. Click
**"Запустить скрейп"** to trigger a live Otomoto/OLX pull.

---

## API endpoints

| Method | Path | Body | Returns |
|--------|------|------|---------|
| `GET`  | `/health` | — | `{"status":"ok"}` |
| `GET`  | `/cars?limit=&offset=` | — | paginated `SearchResponse` of all cars |
| `POST` | `/search?limit=&offset=` | `SearchFilters` (below) | filtered `SearchResponse` |
| `POST` | `/scrape/run` | — | `202` + `{job_id, status:"running"}` (`409` if one is already running) |
| `GET`  | `/scrape/status` | — | `ScrapeStatus` (`idle\|running\|done\|error`, per-source counters) |

**`SearchFilters`** (all optional): `brand`, `model`, `year_min`, `year_max`,
`price_min`, `price_max`, `mileage_max`, `fuel_type`, `transmission`.

Example:

```bash
curl -X POST http://localhost:8000/search \
  -H 'Content-Type: application/json' \
  -d '{"brand":"volkswagen","price_max":100000}'
```

---

## Development commands

Run from the repo root unless noted.

**Backend (local, sqlite for dev):**

The `scrapers/` package lives at the repo root (a sibling of `backend/`), so
`PYTHONPATH` must point there — the app will fail to import without it.

```bash
cd backend
PYTHONPATH=$(pwd)/.. DATABASE_URL="sqlite:///./dev.db" AUTO_SEED=true \
  python -m uvicorn app.main:app --reload --port 8000
```

**Run tests:**

```bash
cd backend && pytest
```

**Seed the database manually** (idempotent — dedupes by source+url):

```bash
cd backend && python seed.py          # 40 demo cars
```

**Try the scrapers standalone** (requires Playwright browsers installed — see Risks):

```bash
python scripts/scrape_demo.py         # prints blocked status + first 5 listings per source
python scripts/seed_demo.py
```

**Frontend dev server** (point it at a running backend):

```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

**Install Playwright browsers** (needed for live scraping, not for seed/search):

```bash
python -m playwright install chromium
```

---

## Risks

- **Live scraping may be blocked.** Otomoto and OLX deploy DataDome / captcha and
  HTTP-level blocks against headless traffic. Block detection is built in
  (`BLOCKED_MARKERS`, HTTP >= 400), and a blocked source simply reports
  `blocked: 1` without failing the job. **Seed data** (40 demo cars) guarantees
  the app is always browsable, even when every live source is blocked.
- **Facebook Marketplace is a stub.** It requires an authenticated session,
  which is out of MVP scope. `FacebookScraper.run()` always returns
  `blocked=True, reason="login required (stub)"`.
- **CSS selectors may need updates.** Otomoto/OLX markup changes over time. If a
  source returns `found: 0` without being blocked, the selectors in
  `scrapers/otomoto.py` / `scrapers/olx.py` likely need refreshing; the
  `scripts/scrape_demo.py` script is the fastest way to diagnose this.
- **`next@14.2.3` advisory.** The frontend pins Next 14.2.3, which has known
  advisories. Bump to the latest patched 14.x (and re-run `npm audit`) before
  any real deployment.

## Known limitations

- **Single scrape job at a time.** The runner holds job state in memory; a
  second `/scrape/run` while one is running returns `409`. Restarting the
  backend resets state to `idle` (no persistent job log).
- **No scheduling.** Scrapes are manual-only (UI button or API call); there is
  no cron/periodic trigger.
- **No real Facebook data** (stub only — see Risks).
- **`total` reflects the DB at query time** — it is not snapshot-isolated under
  concurrent writes.
- **CORS is open (`allow_origins=["*"]`)** — fine for a local MVP, must be
  tightened before public deployment.
- **No auth** on any endpoint.
