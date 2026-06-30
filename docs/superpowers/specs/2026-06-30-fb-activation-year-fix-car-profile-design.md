# Design — FB Activation, Year-Bug Fix, Car Profile Page

**Date:** 2026-06-30
**Branch:** `feat/live-search`
**Status:** Approved (architecture decisions confirmed) → pending implementation plan

## Scope

Three features requested by the user:

1. **Year-bug fix** — listings show year `2026` (and some `2027`) instead of the real production year.
2. **Facebook Marketplace activation** — get the existing FB scraper actually returning data.
3. **Car profile page** — an in-site `/cars/[id]` page so users view a car without leaving for the external source site, including deep-scraped details (description, photo gallery).

## Stack context (confirmed)

- Backend: FastAPI (`backend/app/`), SQLAlchemy, PostgreSQL (prod) / SQLite (dev). Routers: `cars`, `scrape`, `search_live`.
- Frontend: Next.js 14 app-router, React 18, TypeScript, Tailwind (no design tokens). Currently a single client-rendered route `/`.
- Scrapers: standalone `scrapers/` package. `BaseScraper` (legacy `/scrape`) + `ListingProvider` (live `/search/live`). OLX + Otomoto live; Facebook has a working `FacebookProvider` plus a legacy stub `FacebookScraper`.

---

## Feature A — Year-Bug Fix

### Root cause (confirmed from production DB + fixtures)

Production DB (`docker-postgres-1`, db `carsky`) shows wrong future years:

| source | year=2026 | year=2027 | notes |
|--------|-----------|-----------|-------|
| olx    | 113       | 1         | affected |
| otomoto| 48        | 1         | affected |
| facebook | 0       | 0         | **clean** |

**OLX** — `scrapers/olx.py:15-16`:
```python
meta = card.get_text(" ", strip=True)          # entire card text
year = re.search(r"(19|20)\d{2}", meta)         # leftmost match
```
The card text prints the **listing date** immediately before the real production year. Real stored example:
```
"...55 999 zł do negocjacji Przysucha - 31 maja 2026  2019 - 110 480 km Obserwuj"
        price                       location  DATE(2026)  YEAR(2019) MILEAGE
```
`re.search` returns the **leftmost** `(19|20)\d{2}` token → the date `2026`, not the real year `2019`. Same shape on every sampled row (real years 2019/2014/2016/2023).

**Otomoto** — `scrapers/otomoto.py:19,24`:
```python
dds = [d.get_text(strip=True) for d in art.select("dd")]
"year": dds[0] if len(dds) > 0 else None,
```
`dds[0]` is **not** the year. Fixture `backend/tests/fixtures/otomoto_list.html` shows the card `<dd>` order as:
```
[0] '89 900 PLN'   <- price
[1] '2018'         <- real year
[2] 'Benzyna' ... [4] '150 tys. km' [5] 'Warszawa'
```
So the parser reads the price slot (or, in production, whichever `<dd>` contains a `2026` date token) as the year.

**Facebook** — `scrapers/facebook.py:66-68` uses the same unanchored regex, but FB Marketplace item-link text apparently does not contain a stray current-year date, so FB years are correct. FB will still benefit from the normalizer backstop.

**No future-year guard** — `scrapers/normalizer.py:70-74` `parse_year` accepts any 1900–2099, which is why `2027` rows exist.

### Fix design (defense in depth)

1. **OLX anchor** — the production year is the token immediately preceding the mileage segment ` - <digits> km`. Extract with a regex anchored to that pattern rather than scanning all card text. Example approach:
   ```python
   m = re.search(r"(19|20)\d{2}(?=\s*-\s*\d[\d ]*\s*km)", meta)
   year = int(m.group()) if m else None
   ```
   Falls back to `None` (not a wrong year) when the pattern is absent.
2. **Otomoto anchor** — select the `<dd>` whose stripped text is a bare plausible year, instead of positional `dds[0]`:
   ```python
   def _pick_year(dds):
       for d in dds:
           if re.fullmatch(r"(19|20)\d{2}", d.strip()):
               return d
       return None
   ```
3. **Normalizer backstop** — `parse_year` rejects future years:
   ```python
   def parse_year(value):
       if not value: return None
       m = re.search(r"(19|20)\d{2}", str(value))
       if not m: return None
       y = int(m.group())
       return y if y <= _current_year_plus_one() else None
   ```
   (`_current_year_plus_one()` via `date.today().year + 1`, i.e. `2027` as of 2026-06-30.) This catches the `2027` outliers and any residual stray future tokens. **Important:** because `2026` *is* the current year, the guard does **not** reject it — the `2026` date bug is fixed by the OLX/Otomoto anchoring above, not by the guard. The guard is a backstop for genuinely-impossible years only.
4. **Post-filter validation (optional hardening)** — when `year_min`/`year_max` filters are present, drop listings whose parsed year falls outside before upsert (today the scrape→upsert path does not filter, `search_orchestrator.py:107-116`).

### Data repair (one-time)

A script to clean the ~163 wrong rows already stored (OLX 113×2026+1×2027; Otomoto 48×2026+1×2027):
- **Recommended:** set `year = NULL` for rows where `source in ('olx','otomoto')` and `year in (2026, 2027)`. These rows will be repopulated with correct years on the next live search via the fixed parser.
- **Caveat:** `2027` is unambiguously wrong (future) and safe to null. `2026` is the *current* year — a handful of rows could be genuine 2026-model cars; nulling them is a temporary, self-healing loss (next scrape repopulates). If preserving them matters, prefer **re-scraping** those specific listings instead of nulling. Either way the fixed parser prevents new wrong rows.

### Tests (TDD — write failing first)

- `test_normalizer.py`: `parse_year("2027")` → `None` (future, rejected by guard); `parse_year("2026")` → `2026` (current year, allowed — proves the guard alone does **not** fix the date bug); `parse_year("2019")` → `2019`; `parse_year("abc")` → `None`.
- OLX: parse a fixture/inline card containing `"... 31 maja 2026 2019 - 110 480 km ..."` → `year == 2019`.
- Otomoto: parse a card whose `<dd>` list is `['89 900 PLN', '2018', 'Benzyna', ...]` → `year == 2018` (not `None`, not price-derived).
- Regression: existing `test_normalizer.test_parse_year`, `test_providers`, `test_filters` still pass.

---

## Feature B — Facebook Activation (minimal)

The FB scraper already exists and is wired in (`scrapers/facebook.py:46-113` `FacebookProvider`; registered in `search_orchestrator.py:22`; enabled by default `config.py:13`). It only needs activation + the year fix + the missing scroll.

### Changes

1. **Apply the year fix** to FB extraction (normalizer backstop covers it; optionally tighten `facebook.py:68`).
2. **Add feed scrolling** — `FacebookProvider.search()` overrides `run()` and currently does not scroll (unlike `BaseScraper.run`'s 8× scroll). Without scrolling, lazy-rendered Marketplace items are missed → `found=0`. Add a bounded scroll loop (reuse the stealth/scroll pattern from `base.py`).
3. **Document the session capture** (currently undocumented):
   - Add `FB_STORAGE_STATE_PATH` to `.env.example` with a comment.
   - Update README: FB is no longer a stub; document the capture command and that 2FA is completed by the operator in the headed browser.
   - Fix stale README text ("login required (stub)") to match `facebook.py:42`.
4. **Do NOT commit credentials.** The phone/password stay out of the repo. The session file (`backend/secrets/fb_storage_state.json`) is already gitignored, excluded from the image (`.dockerignore`), and mounted read-only via compose (`docker-compose.yml`).

### Operator runbook (delivered to user)

```bash
# one-time, on the host, in a real (headed) browser — operator completes any 2FA:
FB_STORAGE_STATE_PATH=backend/secrets/fb_storage_state.json python scripts/fb_login.py
```
Then `/search/live` returns FB listings with correct years.

### Acceptance

- With a valid `fb_storage_state.json`, `POST /search/live` returns `facebook` listings (`per_source.facebook.status == 'ok'`, `found > 0`) with parsed year/price.
- Without the file, `status == 'session-not-configured'` (existing behavior preserved).
- Existing FB tests (`test_providers.py:55-87`) still pass; add a scroll/parse test where feasible.

---

## Feature C — Car Profile Page + Deep-Scraped Details

### Decisions (confirmed)

- Profile page is a **Server Component** (SEO, fast first paint, server-side base fetch).
- Deep-scraped details use a **DB cache + graceful degradation**.

### Backend

**New endpoints** (`backend/app/routers/cars.py`):

- `GET /cars/{id}` → `schemas.Car` (base fields). `404` if not found. Backed by new `crud.get_car(db, car_id)`.
- `GET /cars/{id}/details` → `schemas.CarDetails` (`{description, images: list[str], fetched_at, status}`).
  - Serve from cache if fresh (`now - fetched_at < TTL`, default 12h).
  - Else fetch fresh: load the source listing page via Playwright (reuse `BaseScraper` stealth args; FB uses `storage_state` session), parse description + image gallery, upsert into cache, return.
  - On block/failure (DataDome, session-invalid, network): return `status='unavailable'`, `description=None`, `images=[]` (do **not** raise — graceful degradation).

**New data model** — side table (1:1 with `cars`, lazy):
```python
class CarDetail(Base):
    __tablename__ = "car_details"
    car_id: Mapped[UUID] = mapped_column(ForeignKey("cars.id"), primary_key=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    images: Mapped[list] = mapped_column(JSON, nullable=True)     # gallery URLs
    status: Mapped[str] = mapped_column(String(32), default="ok")  # ok | unavailable
    fetched_at: Mapped[datetime] = mapped_column(default=_now)
    car = relationship("Car", back_populates="detail")
```
`Car.detail = relationship("CarDetail", back_populates="car", uselist=False, cascade="all, delete-orphan")`.

**Detail parsers** (`scrapers/`, new module e.g. `scrapers/details.py` or per-source `detail_parse` functions):
- `parse_olx_detail(html, base_url) -> {description, images}`
- `parse_otomoto_detail(html, base_url) -> {description, images}`
- `parse_facebook_detail(html, base_url) -> {description, images}`
Each takes the item-page HTML (already fetched with stealth/session) and extracts the description text + photo-gallery URLs. Anti-bot risk is real (Otomoto DataDome, FB session) — that is why degradation is mandatory.

**Stampede guard** (optional, recommended): a simple in-process lock per `car_id` so concurrent requests for the same uncached detail don't trigger N parallel scrapes.

### Frontend

**New route** `frontend/app/cars/[id]/page.tsx` — Server Component:
- Server-side `fetch(`${API}/cars/${id}`)` for the base car (404 → `notFound()`).
- Renders: large image (first gallery photo or `image_url`), title, price + currency, source badge, full spec table (year, mileage, fuel, transmission, location), and an **"Open original listing →"** button linking to `car.url` (`target="_blank"`) — preserves the PDR requirement.
- Embeds a client `<DetailsPanel carId={id} />` that calls `getCarDetails(id)` after mount; shows description + photo gallery when `status=='ok'`, hides gracefully when `status=='unavailable'`.

**API client** (`frontend/lib/api.ts`):
- `getCar(id)` — `GET /cars/{id}`.
- `getCarDetails(id)` — `GET /cars/{id}/details`.
- Add `CarDetails` type.

**CarCard change** (`frontend/components/CarCard.tsx:34-41`):
- Wrap the whole card in `next/link` `<Link href={`/cars/${c.id}`}>` (whole card clickable → profile).
- Keep an explicit **"Open original →"** affordance (either on the card or only on the profile). Decision: keep "Open original →" on the profile page; the card navigates internally. (The external link is not lost — it lives on the profile.)

**Styling**: bare Tailwind utilities (no design tokens exist yet); match `CarCard`/`SourceBadge` ad-hoc style. No new design system in this iteration.

### Tests

- Backend: `GET /cars/{id}` 200 + 404; `GET /cars/{id}/details` cache-hit path, fresh-scrape path (mocked fetcher), and degradation path (fetcher raises → `status='unavailable'`).
- Detail parsers: unit tests with OLX/Otomoto/FB item-page fixtures → description + images.
- Frontend: profile renders base car fields; `DetailsPanel` renders details when ok, renders nothing/placeholder when unavailable. (Component test or manual.)

---

## Phasing

Implementation will be ordered (each phase independently shippable):

1. **Phase 1 — Year fix + data repair + FB activation.** Highest value, lowest surface area, unblocks correct data everywhere. Includes the FB scroll + docs.
2. **Phase 2 — Profile base.** `GET /cars/{id}`, `crud.get_car`, Server Component `/cars/[id]`, clickable `CarCard`, "open original" button. No deep-scrape yet.
3. **Phase 3 — Deep-scraped details.** `car_details` table, `GET /cars/{id}/details`, per-source detail parsers, cache + degradation, `DetailsPanel`.

---

## Risks

- **Anti-bot**: Otomoto DataDome and FB may block detail-page fetches. Mitigation: graceful degradation + cache; the profile stays useful with base fields.
- **FB session expiry / 2FA**: the `+48` account may require re-login periodically. No automation; operator re-runs `fb_login.py`. Surfaces as `session-invalid` in per-source progress.
- **Stampede**: many profile views → many scrapes. Mitigation: DB cache (TTL) + per-id lock.
- **First Server Component**: introduces server-side data fetching in an otherwise fully-client app. Keep it isolated to the profile route.
- **Year anchoring heuristics**: regex anchoring is robust to the observed patterns but depends on OLX/Otomoto DOM conventions. Mitigation: `None` fallback (never a wrong year) + future-year guard + existing regression tests.

## Out of scope

- i18n / locale routing (current app is single-locale, hardcoded `lang="pl"`).
- Saved-cars feature (not in PDR).
- Automated FB login / 2FA (fragile, ToS risk) — session is captured by the operator.
- ML ranking, price prediction.
- New frontend design system / component library.

## Key files (touched/created)

- Year: `scrapers/olx.py`, `scrapers/otomoto.py`, `scrapers/normalizer.py`, `backend/tests/test_normalizer.py`, `backend/tests/test_providers.py`.
- FB: `scrapers/facebook.py`, `scrapers/filters.py` (optional year param), `.env.example`, `README.md`.
- Profile: `backend/app/routers/cars.py`, `backend/app/crud.py`, `backend/app/models.py`, `backend/app/schemas.py`; `frontend/app/cars/[id]/page.tsx`, `frontend/components/CarCard.tsx`, `frontend/components/DetailsPanel.tsx`, `frontend/lib/api.ts`.
- Details: `scrapers/details.py` (new), `backend/app/routers/cars.py` (details endpoint).
- Data repair: one-off script under `scripts/` or an Alembic migration.
