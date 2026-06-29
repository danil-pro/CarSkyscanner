# Live Filtered Multi-Platform Car Search — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a user submits filters and clicks "Найти", the backend live-scrapes OLX + best-effort Otomoto + Facebook (session reuse) using those filters and returns fresh results with per-source progress.

**Architecture:** A `ListingProvider` interface per platform wraps the existing `BaseScraper`. A `SearchOrchestrator` runs enabled providers concurrently (`asyncio.gather`), upserts results into Postgres, and exposes an in-memory job. New endpoints `POST /search/live` + `GET /search/live/{job_id}`; the frontend starts a job and polls until done, showing per-source progress.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, Playwright 1.49.1, psycopg2; Next.js 14.2.3 (TS, Tailwind); Postgres 15; Docker (`python:3.11-slim-bookworm`).

**Spec:** `docs/superpowers/specs/2026-06-29-live-filtered-search-design.md`

## Global Constraints

- Backend base image pinned to `python:3.11-slim-bookworm` (already done).
- No hardcoded credentials. Facebook password is NEVER stored; only `storage_state.json` (cookies) from a one-time manual login.
- `backend/secrets/` and `*.storage_state.json` must be gitignored.
- Internal fuel values are English (`petrol`,`diesel`,`hybrid`,`electric`,`lpg`); OLX/Otomoto need Polish values.
- Existing DB upsert key is `(source, url)` in `app.crud.upsert_car` — reuse it.
- Scrapers already have `resolve_url`, `extract_image_url`, stealth context, scroll-for-lazy-images in `scrapers/base.py` (completed earlier this session) — reuse, do not rewrite.
- Each task ends with a green test (where unit-testable) and a commit.

---

## File Structure

**Create:**
- `scrapers/filters.py` — pure functions mapping `SearchFilters` → per-platform search URLs.
- `scrapers/providers.py` — `ProviderResult`, `ListingProvider` ABC, `OLXProvider`, `OtomotoProvider`.
- `backend/app/search_orchestrator.py` — `SearchOrchestrator` + in-memory `LiveSearchJob`.
- `backend/app/routers/search_live.py` — `/search/live` endpoints.
- `scripts/fb_login.py` — one-time headed Facebook login → `storage_state.json`.
- `frontend/components/LiveSearchProgress.tsx` — per-source progress UI.
- Tests: `backend/tests/test_filters.py`, `backend/tests/test_providers.py`, `backend/tests/test_search_orchestrator.py`, `backend/tests/test_search_live.py`.

**Modify:**
- `scrapers/olx.py` — derive `source` from link domain (bug #2).
- `scrapers/facebook.py` — replace stub with `FacebookProvider` (session reuse).
- `backend/app/config.py` — add settings.
- `backend/app/main.py` — register `search_live` router.
- `frontend/lib/api.ts` — add live-search client calls + types.
- `frontend/app/page.tsx` — wire live search + progress polling.
- `.gitignore`, `docker/docker-compose.yml`, `docker/Dockerfile.backend`.

---

## Task 1: Commit existing groundwork (baseline)

**Files:** working tree (already changed earlier this session)

Earlier this session these were applied but not committed: scraper URL/photo/brand/anti-bot fixes, `scrapers/base.py` helpers, `backend/seed.py` real-domain URLs, `backend/app/crud.py` partial+title filter, `frontend/components/CarCard.tsx` placeholder, `docker/Dockerfile.backend` bookworm pin, `docker/docker-compose.yml` port 5433. Establish a clean baseline before building the feature.

- [ ] **Step 1: Review the diff**

Run: `git status` and `git diff`
Expected: only the files listed above modified; `package-lock.json` untracked (leave it).

- [ ] **Step 2: Stage and commit**

```bash
git add scrapers/ backend/app/crud.py backend/seed.py frontend/components/CarCard.tsx docker/Dockerfile.backend docker/docker-compose.yml
git commit -m "$(cat <<'EOF'
fix(scrapers): absolute URLs, lazy-load photos, brand extraction, anti-bot

- urljoin relative listing/image URLs; scroll for lazy thumbnails; reject
  OLX no_thumbnail placeholder
- extract brand/model from title (+ aliases) so filters match scraped data
- partial+title-aware brand/model filter in crud
- seed: real-domain URLs; CarCard: graceful no-photo placeholder
- docker: pin python:3.11-slim-bookworm (playwright --with-deps), postgres host port 5433

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 3: Verify**

Run: `git log --oneline -1`
Expected: the new commit at HEAD.

---

## Task 2: Filter → URL mapping module

**Files:**
- Create: `scrapers/filters.py`
- Test: `backend/tests/test_filters.py`

**Interfaces:**
- Produces: `build_olx_url(filters) -> str`, `build_otomoto_url(filters) -> str`, `build_facebook_url(filters) -> str`. `filters` is any object with optional attrs `brand, model, price_min, price_max, year_min, year_max, fuel_type` (duck-typed; `app.schemas.SearchFilters` satisfies this).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_filters.py`:
```python
from app.schemas import SearchFilters
from scrapers.filters import build_olx_url, build_otomoto_url, build_facebook_url


def test_olx_brand_and_price():
    url = build_olx_url(SearchFilters(brand="volkswagen", price_max=50000))
    assert url.startswith("https://www.olx.pl/motoryzacja/samochody/?")
    assert "filter_enum_make=Volkswagen" in url
    assert "to=50000" in url


def test_olx_empty_returns_base():
    assert build_olx_url(SearchFilters()) == "https://www.olx.pl/motoryzacja/samochody/"


def test_otomoto_brand_model_in_path():
    url = build_otomoto_url(SearchFilters(brand="bmw", model="x3", year_min=2018))
    assert "/osobowe/bmw/x3" in url
    assert "from=2018" in url


def test_facebook_query_and_price():
    url = build_facebook_url(SearchFilters(brand="toyota", model="yaris", price_min=10000))
    assert "query=toyota+yaris" in url
    assert "minPrice=10000" in url
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec docker-backend-1 pytest backend/tests/test_filters.py -q` (or `pytest backend/tests/test_filters.py -q` if running on host with the venv)
Expected: FAIL — `ModuleNotFoundError: scrapers.filters`

- [ ] **Step 3: Write minimal implementation**

Create `scrapers/filters.py`:
```python
from urllib.parse import urlencode, quote

FUEL_PL = {
    "petrol": "benzyna", "diesel": "diesel", "hybrid": "hybryda",
    "electric": "elektryczny", "lpg": "lpg",
}

OLX_BASE = "https://www.olx.pl/motoryzacja/samochody/"
OTOMOTO_BASE = "https://www.otomoto.pl/osobowe"
FB_BASE = "https://www.facebook.com/marketplace/search/"


def _fuel_pl(value):
    return FUEL_PL.get(value, value) if value else None


def build_olx_url(f) -> str:
    p = {}
    if getattr(f, "brand", None):
        p["search[filter_enum_make]"] = f.brand.capitalize()
    if getattr(f, "model", None):
        p["search[filter_enum_model]"] = f.model.capitalize()
    if f.price_min is not None:
        p["search[filter_float_price:from]"] = int(f.price_min)
    if f.price_max is not None:
        p["search[filter_float_price:to]"] = int(f.price_max)
    if f.year_min is not None:
        p["search[filter_float_year:from]"] = f.year_min
    if f.year_max is not None:
        p["search[filter_float_year:to]"] = f.year_max
    if getattr(f, "fuel_type", None):
        p["search[filter_enum_fuel]"] = _fuel_pl(f.fuel_type)
    return f"{OLX_BASE}?{urlencode(p)}" if p else OLX_BASE


def build_otomoto_url(f) -> str:
    parts = [OTOMOTO_BASE]
    if getattr(f, "brand", None):
        parts.append(quote(f.brand))
    if getattr(f, "model", None):
        parts.append(quote(f.model))
    path = "/".join(parts)
    p = {}
    if f.price_min is not None:
        p["search[filter_float_price:from]"] = int(f.price_min)
    if f.price_max is not None:
        p["search[filter_float_price:to]"] = int(f.price_max)
    if f.year_min is not None:
        p["search[filter_float_year:from]"] = f.year_min
    if f.year_max is not None:
        p["search[filter_float_year:to]"] = f.year_max
    if getattr(f, "fuel_type", None):
        p["search[filter_enum_fuel_type]"] = _fuel_pl(f.fuel_type)
    return f"{path}?{urlencode(p)}" if p else path + "/"


def build_facebook_url(f) -> str:
    q = " ".join(x for x in (getattr(f, "brand", None), getattr(f, "model", None)) if x).strip()
    p = {"exact": "false"}
    if q:
        p["query"] = q
    if f.price_min is not None:
        p["minPrice"] = int(f.price_min)
    if f.price_max is not None:
        p["maxPrice"] = int(f.price_max)
    return f"{FB_BASE}?{urlencode(p)}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker exec docker-backend-1 pytest backend/tests/test_filters.py -q`
Expected: PASS (4 tests). If the container lacks the new file, rebuild backend first: `docker compose -f docker/docker-compose.yml build backend && docker compose -f docker/docker-compose.yml up -d backend`.

- [ ] **Step 5: Commit**

```bash
git add scrapers/filters.py backend/tests/test_filters.py
git commit -m "feat(scrapers): filter->URL mapping for olx/otomoto/facebook"
```

---

## Task 3: Bug #2 — derive `source` from link domain

**Files:**
- Modify: `scrapers/olx.py` (the `parse_html` function)
- Test: `backend/tests/test_providers.py` (created here, extended in Task 4)

**Interfaces:**
- Produces: `scrapers.olx.parse_html(html)` now sets each listing's `"source"` to `"otomoto"` when the card's link points at `otomoto.pl`, else `"olx"`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_providers.py`:
```python
from scrapers.olx import parse_html

OLX_CARD_OTOMOTO_LINK = """
<html><body>
<div data-cy="l-card">
  <a href="/d/oferta/vw-golf-CID5-ID1.html"><h6>VW Golf</h6></a>
  <span data-testid="ad-price">50 000 zł</span>
  <img data-src="https://ireland.apollo.olxcdn.com:443/v1/files/abc/image"/>
  <p>2018 · 150 000 km · Benzyna</p>
</div>
<div data-cy="l-card">
  <a href="https://www.otomoto.pl/osobowe/vw-golf-ID123.html"><h6>VW Golf</h6></a>
  <span data-testid="ad-price">60 000 zł</span>
  <img data-src="https://ireland.apollo.olxcdn.com:443/v1/files/def/image"/>
  <p>2019 · 120 000 km · Diesel</p>
</div>
</body></html>
"""


def test_olx_parse_source_by_domain():
    listings = parse_html(OLX_CARD_OTOMOTO_LINK)
    assert len(listings) == 2
    assert listings[0]["source"] == "olx"
    assert listings[1]["source"] == "otomoto"  # cross-listed otomoto ad
    assert listings[1]["url"].startswith("https://www.otomoto.pl/")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec docker-backend-1 pytest backend/tests/test_providers.py::test_olx_parse_source_by_domain -q`
Expected: FAIL — `assert listings[1]["source"] == "otomoto"` (currently always `"olx"`).

- [ ] **Step 3: Write minimal implementation**

In `scrapers/olx.py`, edit the loop inside `parse_html` so the link is read once and `source` is derived from the domain:
```python
    for card in soup.select('[data-cy="l-card"]'):
        a = card.select_one("a[href]")
        price = card.select_one('[data-testid="ad-price"]')
        meta = card.get_text(" ", strip=True)
        year = re.search(r"(19|20)\d{2}", meta)
        mileage = re.search(r"([\d  ]+)\s*km", meta)
        href = a["href"] if a else None
        url = resolve_url(BASE_URL, href)
        if not url:
            continue
        out.append({
            "title": (card.select_one("h6").get_text(strip=True) if card.select_one("h6") else meta[:200]),
            "brand": "", "model": "",
            "year": year.group(0) if year else None,
            "price": price.get_text(strip=True) if price else None,
            "mileage": mileage.group(1).replace(" ", " ") if mileage else None,
            "fuel_type": next((t for t in ("Benzyna", "Diesel", "Hybryda", "Elektryczny", "LPG") if t in meta), None),
            "transmission": None,
            "location": None,
            "source": "otomoto" if "otomoto.pl" in (href or "") else "olx",
            "url": url,
            "image_url": extract_image_url(card, BASE_URL),
        })
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker exec docker-backend-1 pytest backend/tests/test_providers.py::test_olx_parse_source_by_domain -q`
Expected: PASS. (Rebuild backend if the container has stale code.)

- [ ] **Step 5: Commit**

```bash
git add scrapers/olx.py backend/tests/test_providers.py
git commit -m "fix(scrapers): derive listing source from link domain (olx cross-listed otomoto)"
```

---

## Task 4: ListingProvider abstraction + OLX/Otomoto providers

**Files:**
- Create: `scrapers/providers.py`
- Modify: `backend/tests/test_providers.py` (append)

**Interfaces:**
- Produces: `ProviderResult(source, listings, status, reason, found)`, `ListingProvider.search(playwright) -> ProviderResult`, `OLXProvider(filters)`, `OtomotoProvider(filters)`. `status ∈ {ok, blocked, error, session-invalid, session-not-configured}`.
- Consumes: `scrapers.olx.OLXScraper`, `scrapers.otomoto.OtomotoScraper`, `scrapers.base.ScrapeResult`, `scrapers.filters.build_olx_url`/`build_otomoto_url`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_providers.py`:
```python
from app.schemas import SearchFilters
from scrapers.base import ScrapeResult
from scrapers.providers import OLXProvider, OtomotoProvider, ProviderResult, _from_scrape


def test_olx_provider_builds_filtered_url():
    p = OLXProvider(SearchFilters(brand="volkswagen"))
    assert "filter_enum_make=Volkswagen" in p.build_url()
    assert p.source == "olx"


def test_otomoto_provider_builds_filtered_url():
    p = OtomotoProvider(SearchFilters(brand="audi", model="a4"))
    assert "/osobowe/audi/a4" in p.build_url()


def test_from_scrape_blocked():
    r = _from_scrape("otomoto", ScrapeResult("otomoto", blocked=True, reason="blocked-marker:datadome"))
    assert r.status == "blocked" and r.source == "otomoto" and r.found == 0


def test_from_scrape_ok():
    r = _from_scrape("olx", ScrapeResult("olx", listings=[{"x": 1}]))
    assert r.status == "ok" and r.found == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec docker-backend-1 pytest backend/tests/test_providers.py -q`
Expected: FAIL — `ModuleNotFoundError: scrapers.providers`.

- [ ] **Step 3: Write minimal implementation**

Create `scrapers/providers.py`:
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from playwright.async_api import Playwright

from scrapers.base import ScrapeResult
from scrapers.olx import OLXScraper
from scrapers.otomoto import OtomotoScraper
from scrapers.filters import build_olx_url, build_otomoto_url


@dataclass
class ProviderResult:
    source: str
    listings: list[dict] = field(default_factory=list)
    status: str = "ok"
    reason: Optional[str] = None
    found: int = 0


def _from_scrape(source: str, result: ScrapeResult) -> ProviderResult:
    return ProviderResult(
        source=source,
        listings=result.listings,
        status="blocked" if result.blocked else "ok",
        reason=result.reason,
        found=len(result.listings),
    )


class ListingProvider(ABC):
    source: str

    @abstractmethod
    async def search(self, playwright: Playwright) -> ProviderResult:
        ...


class OLXProvider(OLXScraper, ListingProvider):
    source = "olx"

    def __init__(self, filters):
        self.filters = filters

    def build_url(self) -> str:
        return build_olx_url(self.filters)

    async def search(self, playwright: Playwright) -> ProviderResult:
        return _from_scrape(self.source, await self.run(playwright))


class OtomotoProvider(OtomotoScraper, ListingProvider):
    source = "otomoto"

    def __init__(self, filters):
        self.filters = filters

    def build_url(self) -> str:
        return build_otomoto_url(self.filters)

    async def search(self, playwright: Playwright) -> ProviderResult:
        return _from_scrape(self.source, await self.run(playwright))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker exec docker-backend-1 pytest backend/tests/test_providers.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add scrapers/providers.py backend/tests/test_providers.py
git commit -m "feat(scrapers): ListingProvider abstraction + OLX/Otomoto providers"
```

---

## Task 5: FacebookProvider (session reuse) + login script

**Files:**
- Modify: `scrapers/facebook.py` (replace stub)
- Create: `scripts/fb_login.py`
- Test: `backend/tests/test_providers.py` (append)

**Interfaces:**
- Produces: `FacebookProvider(filters, storage_state_path)` with `source="facebook"` and `search(playwright)`. Status `session-not-configured` when the file is missing; `session-invalid` when redirected to login/checkpoint; otherwise `ok` with parsed listings.
- Consumes: `scrapers.filters.build_facebook_url`, `scrapers.base.{resolve_url, extract_image_url, USER_AGENT, STEALTH_INIT}`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_providers.py`:
```python
from scrapers.facebook import FacebookProvider


def test_facebook_not_configured(tmp_path):
    import asyncio
    p = FacebookProvider(SearchFilters(brand="toyota"), storage_state_path=str(tmp_path / "missing.json"))
    res = asyncio.run(p.search(playwright=None))
    assert res.status == "session-not-configured"
    assert res.source == "facebook"


def test_facebook_parses_item_links(tmp_path):
    html = """
    <html><body>
      <a href="/marketplace/item/111/">Toyota Yaris 2019 · 50 000 zł</a>
      <a href="/marketplace/item/222/">Honda Civic 2018 · 40 000 zł</a>
    </body></html>
    """
    p = FacebookProvider(SearchFilters(), storage_state_path=str(tmp_path / "x.json"))
    listings = p._parse(html)
    assert len(listings) == 2
    assert listings[0]["source"] == "facebook"
    assert listings[0]["url"].startswith("https://www.facebook.com/marketplace/item/")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec docker-backend-1 pytest backend/tests/test_providers.py::test_facebook_not_configured -q`
Expected: FAIL — `FacebookProvider` still the old stub (no `storage_state_path` arg).

- [ ] **Step 3: Write minimal implementation**

Replace the entire contents of `scrapers/facebook.py`:
```python
import os
import re
from typing import Optional

from bs4 import BeautifulSoup
from playwright.async_api import Playwright

from scrapers.base import (
    ListingProvider,
    USER_AGENT,
    STEALTH_INIT,
    resolve_url,
    extract_image_url,
)
from scrapers.providers import ProviderResult
from scrapers.filters import build_facebook_url

FB_BASE = "https://www.facebook.com/marketplace/"
_LOGIN_MARKERS = ("/login", "/checkpoint", "/two_step", "/recover")


class FacebookProvider(ListingProvider):
    """Scrape FB Marketplace using a saved login session (storage_state.json)."""

    source = "facebook"

    def __init__(self, filters, storage_state_path: Optional[str] = None):
        self.filters = filters
        self.storage_state_path = storage_state_path or os.getenv("FB_STORAGE_STATE_PATH")

    def build_url(self) -> str:
        return build_facebook_url(self.filters)

    def _parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        out = []
        for a in soup.select('a[href*="/marketplace/item/"]'):
            href = a.get("href")
            url = resolve_url(FB_BASE, href)
            if not url:
                continue
            text = a.get_text(" ", strip=True)
            price = re.search(r"(\d[\d  ]*)\s*(zł|zl|PLN)?", text)
            year = re.search(r"(19|20)\d{2}", text)
            out.append({
                "title": text[:200] or None,
                "brand": "", "model": "",
                "year": year.group(0) if year else None,
                "price": price.group(1) if price else None,
                "mileage": None, "fuel_type": None, "transmission": None,
                "location": None,
                "source": "facebook",
                "url": url,
                "image_url": None,
            })
        return out

    async def search(self, playwright: Playwright) -> ProviderResult:
        if not self.storage_state_path or not os.path.exists(self.storage_state_path):
            return ProviderResult(self.source, status="session-not-configured",
                                  reason="no storage_state file")
        if playwright is None:
            return ProviderResult(self.source, status="error", reason="no playwright")
        browser = await playwright.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(
            storage_state=self.storage_state_path,
            user_agent=USER_AGENT,
            locale="pl-PL",
            viewport={"width": 1366, "height": 800},
        )
        await context.add_init_script(STEALTH_INIT)
        page = await context.new_page()
        try:
            await page.goto(self.build_url(), timeout=45000, wait_until="domcontentloaded")
            current = page.url
            if any(m in current for m in _LOGIN_MARKERS):
                return ProviderResult(self.source, status="session-invalid",
                                      reason=f"redirected to {current}")
            raw = self._parse(await page.content())
            return ProviderResult(self.source, listings=raw, status="ok", found=len(raw))
        except Exception as e:
            return ProviderResult(self.source, status="error", reason=f"error: {e}")
        finally:
            await browser.close()
```

Note: `FacebookProvider(ListingProvider)` requires `ListingProvider` to be importable from `scrapers.base`. Add this import line at the top of `scrapers/base.py` is NOT needed — instead import from `scrapers.providers`. **Correction:** to avoid a circular import (`providers` imports `base`, `facebook` imports both), have `facebook.py` import `ListingProvider` from `scrapers.providers`. Replace the `from scrapers.base import (ListingProvider, ...)` line with:
```python
from scrapers.base import USER_AGENT, STEALTH_INIT, resolve_url, extract_image_url
from scrapers.providers import ListingProvider, ProviderResult
```
(FB parsing uses `re`, not `extract_image_url`; `extract_image_url` may stay imported unused or be removed — remove it to keep imports clean.)

- [ ] **Step 4: Run test to verify it passes**

Run: `docker exec docker-backend-1 pytest backend/tests/test_providers.py -q`
Expected: PASS (7 tests).

- [ ] **Step 5: Create the one-time login script**

Create `scripts/fb_login.py`:
```python
"""One-time Facebook login to capture a Playwright storage_state.json.

Run on the HOST (needs a visible browser): pip install playwright && playwright install chromium
Then:  FB_STORAGE_STATE_PATH=backend/secrets/fb_storage_state.json python scripts/fb_login.py
Log into Facebook in the window that opens, then return to the terminal and press Enter.
"""
import asyncio
import os

from playwright.async_api import async_playwright


async def main():
    out = os.getenv("FB_STORAGE_STATE_PATH", "backend/secrets/fb_storage_state.json")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        ctx = await browser.new_context()
        page = await ctx.new_page()
        await page.goto("https://www.facebook.com/login")
        print("Log into Facebook in the browser, then press Enter here.")
        input()
        await ctx.storage_state(path=out)
        print(f"Saved session -> {out}")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 6: Commit**

```bash
git add scrapers/facebook.py scripts/fb_login.py backend/tests/test_providers.py
git commit -m "feat(scrapers): Facebook Marketplace provider via session reuse + login script"
```

---

## Task 6: Config settings

**Files:**
- Modify: `backend/app/config.py`
- Test: `backend/tests/test_config.py`

**Interfaces:**
- Produces: `settings.enabled_sources -> list[str]`, `settings.FB_STORAGE_STATE_PATH`, `settings.SEARCH_PROVIDER_TIMEOUT_S`, `settings.SEARCH_JOB_TIMEOUT_S`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_config.py`:
```python
from app.config import Settings


def test_enabled_sources_split():
    s = Settings(ENABLED_SOURCES="olx, otomoto ,facebook")
    assert s.enabled_sources == ["olx", "otomoto", "facebook"]


def test_defaults():
    s = Settings()
    assert s.SEARCH_PROVIDER_TIMEOUT_S == 45
    assert s.SEARCH_JOB_TIMEOUT_S == 60
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec docker-backend-1 pytest backend/tests/test_config.py -q`
Expected: FAIL — `AttributeError: enabled_sources` / `SEARCH_PROVIDER_TIMEOUT_S`.

- [ ] **Step 3: Write minimal implementation**

Replace `backend/app/config.py` contents:
```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+psycopg2://carsky:carsky@localhost:5432/carsky"
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    AUTO_SEED: bool = True

    # Live search
    ENABLED_SOURCES: str = "olx,otomoto,facebook"
    FB_STORAGE_STATE_PATH: str | None = None
    SEARCH_PROVIDER_TIMEOUT_S: int = 45
    SEARCH_JOB_TIMEOUT_S: int = 60

    @property
    def enabled_sources(self) -> list[str]:
        return [s.strip() for s in self.ENABLED_SOURCES.split(",") if s.strip()]


settings = Settings()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker exec docker-backend-1 pytest backend/tests/test_config.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/config.py backend/tests/test_config.py
git commit -m "feat(config): live-search settings (sources, FB path, timeouts)"
```

---

## Task 7: SearchOrchestrator

**Files:**
- Create: `backend/app/search_orchestrator.py`
- Test: `backend/tests/test_search_orchestrator.py`

**Interfaces:**
- Produces: `SearchOrchestrator` (constructor takes `provider_factory` and `acquire_playwright` for testability), `orchestrator` singleton, `LiveSearchJob`. Methods: `start(filters) -> job_id`, `get(job_id) -> LiveSearchJob | None`. `LiveSearchJob.to_dict() -> dict` with keys `job_id, status, per_source, results, error`.
- Consumes: `app.config.settings`, `app.crud.upsert_car`, `app.database.SessionLocal`, providers from Task 4/5.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_search_orchestrator.py`:
```python
import asyncio
import pytest

from app.schemas import SearchFilters
from scrapers.providers import ProviderResult
from app.search_orchestrator import SearchOrchestrator


class FakeProvider:
    def __init__(self, source, result):
        self.source = source
        self._result = result

    async def search(self, playwright):
        return self._result


class FakePW:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *a):
        return False


def _orch(providers):
    return SearchOrchestrator(
        provider_factory=lambda filters: providers,
        acquire_playwright=lambda: FakePW(),
    )


# NOTE: orch.start() schedules the job via asyncio.create_task, which requires a
# running event loop — so these tests are async and run under pytest-asyncio.
@pytest.mark.asyncio
async def test_run_collects_and_marks_done():
    orch = _orch([
        FakeProvider("olx", ProviderResult("olx", listings=[{"source": "olx", "url": "u1", "price": 1.0}], found=1)),
        FakeProvider("otomoto", ProviderResult("otomoto", status="blocked", reason="datadome")),
    ])
    job_id = orch.start(SearchFilters())
    await asyncio.sleep(0.1)
    job = orch.get(job_id)
    assert job.status == "done"
    assert job.per_source["olx"]["status"] == "ok"
    assert job.per_source["otomoto"]["status"] == "blocked"
    assert job.results is not None and len(job.results) == 1


def test_unknown_job_returns_none():
    orch = _orch([])
    assert orch.get("nope") is None


@pytest.mark.asyncio
async def test_provider_timeout_marks_error():
    class Slow:
        source = "olx"

        async def search(self, playwright):
            await asyncio.sleep(10)
            return ProviderResult("olx")

    orch = SearchOrchestrator(
        provider_factory=lambda f: [Slow()],
        acquire_playwright=lambda: FakePW(),
        provider_timeout_s=0.05,
    )
    job_id = orch.start(SearchFilters())
    await asyncio.sleep(0.3)
    job = orch.get(job_id)
    assert job.per_source["olx"]["status"] == "error"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec docker-backend-1 pytest backend/tests/test_search_orchestrator.py -q`
Expected: FAIL — `ModuleNotFoundError: app.search_orchestrator`.

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/search_orchestrator.py`:
```python
import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

from app import schemas
from app.config import settings
from app.crud import upsert_car
from app.database import SessionLocal
from app.schemas import SearchFilters
from scrapers.providers import OLXProvider, OtomotoProvider, ProviderResult
from scrapers.facebook import FacebookProvider


def default_provider_factory(filters: SearchFilters):
    providers = []
    for src in settings.enabled_sources:
        if src == "olx":
            providers.append(OLXProvider(filters))
        elif src == "otomoto":
            providers.append(OtomotoProvider(filters))
        elif src == "facebook":
            providers.append(FacebookProvider(filters, settings.FB_STORAGE_STATE_PATH))
    return providers


def _default_acquire_playwright():
    from playwright.async_api import async_playwright
    return async_playwright()


class LiveSearchJob:
    def __init__(self, job_id: str, filters: SearchFilters):
        self.job_id = job_id
        self.filters = filters
        self.status = "running"
        self.per_source: dict[str, dict] = {}
        self.results: Optional[list[dict]] = None
        self.error: Optional[str] = None
        self.started_at = datetime.now(timezone.utc)
        self.finished_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "per_source": self.per_source,
            "results": self.results,
            "error": self.error,
        }


class SearchOrchestrator:
    def __init__(
        self,
        provider_factory: Callable[[SearchFilters], list] = default_provider_factory,
        acquire_playwright: Callable[[], Awaitable] = _default_acquire_playwright,
        provider_timeout_s: int = None,
    ):
        self._provider_factory = provider_factory
        self._acquire_playwright = acquire_playwright
        self._provider_timeout_s = provider_timeout_s or settings.SEARCH_PROVIDER_TIMEOUT_S
        self._jobs: dict[str, LiveSearchJob] = {}

    def start(self, filters: SearchFilters) -> str:
        job_id = str(uuid.uuid4())
        job = LiveSearchJob(job_id, filters)
        for p in self._provider_factory(filters):
            job.per_source[p.source] = {"status": "pending", "found": 0, "reason": None}
        self._jobs[job_id] = job
        asyncio.create_task(self._run(job))
        return job_id

    def get(self, job_id: str) -> Optional[LiveSearchJob]:
        return self._jobs.get(job_id)

    async def _run(self, job: LiveSearchJob):
        providers = self._provider_factory(job.filters)
        try:
            async with self._acquire_playwright() as pw:
                async def run_one(p):
                    try:
                        res = await asyncio.wait_for(p.search(pw), timeout=self._provider_timeout_s)
                    except asyncio.TimeoutError:
                        res = ProviderResult(p.source, status="error", reason="timeout")
                    except Exception as e:  # never let one provider sink the job
                        res = ProviderResult(p.source, status="error", reason=f"error: {e}")
                    job.per_source[p.source] = {
                        "status": res.status, "found": res.found, "reason": res.reason,
                    }
                    return res

                results = await asyncio.gather(*(run_one(p) for p in providers))

            collected = []
            db = SessionLocal()
            try:
                for res in results:
                    for listing in res.listings:
                        try:
                            upsert_car(db, listing)
                        except Exception:
                            pass
                        collected.append(listing)
            finally:
                db.close()
            job.results = collected
            job.status = "done"
        except Exception as e:
            job.status = "error"
            job.error = str(e)
        finally:
            job.finished_at = datetime.now(timezone.utc)


orchestrator = SearchOrchestrator()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker exec docker-backend-1 pytest backend/tests/test_search_orchestrator.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/search_orchestrator.py backend/tests/test_search_orchestrator.py
git commit -m "feat(backend): SearchOrchestrator runs providers concurrently with per-source status"
```

---

## Task 8: `/search/live` API router

**Files:**
- Create: `backend/app/routers/search_live.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_search_live.py`

**Interfaces:**
- Produces: `POST /search/live` (body `SearchFilters`) → `{job_id, status}`; `GET /search/live/{job_id}` → job dict (404 if unknown).
- Consumes: `app.search_orchestrator.orchestrator`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_search_live.py`:
```python
from fastapi.testclient import TestClient
from app.main import app
from app.routers import search_live
from app.search_orchestrator import SearchOrchestrator, LiveSearchJob
from app.schemas import SearchFilters


class DoneOrch(SearchOrchestrator):
    def __init__(self):
        super().__init__(provider_factory=lambda f: [], acquire_playwright=lambda: None)
        self._fake = LiveSearchJob("job-1", SearchFilters())
        self._fake.status = "done"
        self._fake.results = []
        self._fake.per_source = {"olx": {"status": "ok", "found": 0, "reason": None}}
        self._jobs = {"job-1": self._fake}

    def start(self, filters):
        return "job-1"

    def get(self, job_id):
        return self._fake if job_id == "job-1" else None


def _client():
    app.dependency_overrides[search_live.get_orchestrator] = lambda: DoneOrch()
    return TestClient(app)


def test_start_live_search():
    r = _client().post("/search/live", json={"brand": "volkswagen"})
    assert r.status_code == 200
    assert r.json() == {"job_id": "job-1", "status": "running"}


def test_get_live_job():
    r = _client().get("/search/live/job-1")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "done"
    assert body["per_source"]["olx"]["status"] == "ok"


def test_get_unknown_job_404():
    r = _client().get("/search/live/nope")
    assert r.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec docker-backend-1 pytest backend/tests/test_search_live.py -q`
Expected: FAIL — 404 (router not registered).

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/routers/search_live.py`:
```python
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
```

Register in `backend/app/main.py` — add the import next to the other router imports (line 3) and the include call next to the others (after line 36):
```python
from app.routers import cars, scrape, search_live
```
and
```python
app.include_router(search_live.router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker exec docker-backend-1 pytest backend/tests/test_search_live.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/search_live.py backend/app/main.py backend/tests/test_search_live.py
git commit -m "feat(backend): /search/live endpoints with orchestrator dependency"
```

---

## Task 9: Frontend — live search + progress polling

**Files:**
- Modify: `frontend/lib/api.ts`
- Create: `frontend/components/LiveSearchProgress.tsx`
- Modify: `frontend/app/page.tsx`

**Interfaces:**
- Produces: `startLiveSearch(f)`, `getLiveSearch(jobId)`, types `LiveSearchJob`, `ProviderProgress`. The page polls until `status !== "running"` then renders `results`.

- [ ] **Step 1: Add client types + calls**

In `frontend/lib/api.ts`, append after the existing exports:
```typescript
export interface ProviderProgress { status: string; found: number; reason: string | null; }
export interface LiveSearchJob {
  job_id: string; status: string;
  per_source: Record<string, ProviderProgress>;
  results: Car[] | null; error?: string | null;
}

export const startLiveSearch = (f: Filters) =>
  req<{ job_id: string; status: string }>("/search/live", { method: "POST", body: JSON.stringify(f) });
export const getLiveSearch = (jobId: string) => req<LiveSearchJob>(`/search/live/${jobId}`);
```

- [ ] **Step 2: Create the progress component**

Create `frontend/components/LiveSearchProgress.tsx`:
```tsx
"use client";
import type { LiveSearchJob } from "@/lib/api";

const LABELS: Record<string, string> = {
  ok: "✓", blocked: "⛔", error: "✗",
  "session-invalid": "🔒", "session-not-configured": "🔒", pending: "…",
};

export function LiveSearchProgress({ job }: { job: LiveSearchJob }) {
  return (
    <div className="bg-white rounded-lg shadow p-3 text-sm space-y-1">
      <div className="font-semibold">Живой поиск… {job.status === "running" ? "собираем данные" : job.status}</div>
      {Object.entries(job.per_source).map(([src, p]) => (
        <div key={src} className="flex justify-between text-gray-700">
          <span>{src.toUpperCase()} {LABELS[p.status] ?? ""}</span>
          <span className="text-gray-500">{p.status === "ok" ? `найдено ${p.found}` : p.reason || p.status}</span>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Wire the page to live search**

Replace `frontend/app/page.tsx` contents:
```tsx
"use client";
import { useEffect, useRef, useState } from "react";
import { Car, Filters, getCars, startLiveSearch, getLiveSearch, LiveSearchJob } from "@/lib/api";
import { SearchForm } from "@/components/SearchForm";
import { ResultsList } from "@/components/ResultsList";
import { ScrapePanel } from "@/components/ScrapePanel";
import { LiveSearchProgress } from "@/components/LiveSearchProgress";

export default function Page() {
  const [cars, setCars] = useState<Car[]>([]);
  const [loading, setLoading] = useState(true);
  const [job, setJob] = useState<LiveSearchJob | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = () => {
    if (timer.current) { clearInterval(timer.current); timer.current = null; }
  };

  const runLive = (f: Filters) => {
    setLoading(true);
    setJob(null);
    setCars([]);
    stopPolling();
    startLiveSearch(f)
      .then(({ job_id }) => {
        timer.current = setInterval(() => {
          getLiveSearch(job_id)
            .then((j) => {
              setJob(j);
              if (j.status !== "running") {
                stopPolling();
                setCars(j.results ?? []);
                setLoading(false);
              }
            })
            .catch(() => { stopPolling(); setLoading(false); });
        }, 2000);
      })
      .catch(() => setLoading(false));
  };

  useEffect(() => {
    // initial load from DB (cached), then live search drives updates
    getCars().then((r) => setCars(r.items)).catch(() => setCars([])).finally(() => setLoading(false));
    return () => stopPolling();
  }, []);

  return (
    <main className="max-w-5xl mx-auto p-4 space-y-4">
      <h1 className="text-2xl font-bold">CarSkyscanner 🚗</h1>
      <SearchForm onSearch={(f) => runLive(f)} />
      <ScrapePanel />
      {job && <LiveSearchProgress job={job} />}
      <ResultsList cars={cars} loading={loading} />
    </main>
  );
}
```

- [ ] **Step 4: Build and verify**

Run: `docker compose -f docker/docker-compose.yml build frontend && docker compose -f docker/docker-compose.yml up -d frontend`
Then open http://localhost:3000, fill brand=volkswagen, click "Найти". Expected: progress panel shows per-source status, then results appear (OLX should yield listings; Otomoto usually "blocked"; FB "session-not-configured" until Task 11 login).

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/api.ts frontend/components/LiveSearchProgress.tsx frontend/app/page.tsx
git commit -m "feat(frontend): live search with per-source progress polling"
```

---

## Task 10: Docker / compose / gitignore for FB session

**Files:**
- Modify: `.gitignore`, `docker/docker-compose.yml`, `docker/Dockerfile.backend`

- [ ] **Step 1: Ignore secrets**

Append to `.gitignore`:
```
backend/secrets/
*.storage_state.json
```
Create `backend/secrets/.gitkeep` so the dir exists:
```bash
mkdir -p backend/secrets && touch backend/secrets/.gitkeep
```

- [ ] **Step 2: Mount secrets + env into the backend container**

In `docker/docker-compose.yml`, under the `backend` service, add a volume mount and env (place after the existing `environment:` block, merged in):
```yaml
    environment:
      DATABASE_URL: postgresql+psycopg2://carsky:carsky@postgres:5432/carsky
      AUTO_SEED: "true"
      ENABLED_SOURCES: "olx,otomoto,facebook"
      FB_STORAGE_STATE_PATH: "/app/secrets/fb_storage_state.json"
      SEARCH_PROVIDER_TIMEOUT_S: "45"
      SEARCH_JOB_TIMEOUT_S: "60"
    volumes:
      - ./backend/secrets:/app/secrets:ro
```

- [ ] **Step 3: Confirm Dockerfile copies nothing secret**

`docker/Dockerfile.backend` must NOT `COPY backend/secrets`. Verify the existing `COPY backend /app` line — it would copy `backend/secrets` into the image. Add `backend/secrets/` to `docker/.dockerignore` (create if absent) so the build context excludes it:
```bash
printf 'backend/secrets/\n*.storage_state.json\n' > docker/.dockerignore
```
(The mount in Step 2 provides the file at runtime; the image stays secret-free.)

- [ ] **Step 4: Verify**

Run: `docker compose -f docker/docker-compose.yml up -d backend` and `docker exec docker-backend-1 printenv FB_STORAGE_STATE_PATH`
Expected: `/app/secrets/fb_storage_state.json`.

- [ ] **Step 5: Commit**

```bash
git add .gitignore docker/docker-compose.yml docker/.dockerignore backend/secrets/.gitkeep
git commit -m "chore(docker): mount FB session secrets read-only; exclude from image"
```

---

## Task 11: End-to-end verification (manual)

**Files:** none (verification only)

- [ ] **Step 1: Run the full unit suite**

Run: `docker compose -f docker/docker-compose.yml build backend && docker exec docker-backend-1 pytest -q`
Expected: all tests pass (filters, providers, config, orchestrator, search_live). Note: `test_crud.py` assumes an isolated DB — if it fails only due to a populated shared DB, that is a pre-existing test-design issue, not a regression; confirm by running it against an empty DB (`TRUNCATE cars;` then re-run).

- [ ] **Step 2: Capture a Facebook session (host)**

On the host (install Playwright if needed: `pip install playwright && playwright install chromium`):
```bash
FB_STORAGE_STATE_PATH=backend/secrets/fb_storage_state.json python scripts/fb_login.py
```
Log into Facebook in the window, press Enter. Expected: `Saved session -> backend/secrets/fb_storage_state.json`.

- [ ] **Step 3: Restart backend with the new code + session**

Run: `docker compose -f docker/docker-compose.yml up -d backend`

- [ ] **Step 4: Live search end-to-end**

Open http://localhost:3000, set brand=volkswagen, price_max=80000, click "Найти". Expected:
- Progress shows OLX (ok, N found), Otomoto (usually blocked), Facebook (ok if session valid, else session-invalid).
- After completion (~20-60s), results list shows fresh OLX (and FB if working) listings with real photos, real absolute URLs, and badges matching their link domain.
- Clicking a listing opens the real source page (no DNS error).

- [ ] **Step 5: Verify source/domain consistency**

Run:
```bash
docker exec docker-postgres-1 psql -U carsky -d carsky -c \
"select source, count(*) filter (where url not like 'https://%') as bad_urls from cars group by source;"
```
Expected: `bad_urls = 0` for every source.

- [ ] **Step 6: Final commit (if any scratch fixes)**

Only if Steps 1-5 surfaced fixes. Otherwise the feature is complete.
```bash
git add -A && git commit -m "chore: e2e verification fixes" || echo "nothing to commit"
```

---

## Self-Review Notes

- **Spec coverage:** provider abstraction (T4), FB session reuse (T5), filter→URL (T2), orchestrator + per-source status + timeouts (T7), `/search/live` + polling (T8, T9), bug #2 source-by-domain (T3), bug #1 seed URLs (T1 baseline, already applied), config/security (T6, T10), tests (each task), e2e (T11). Otomoto best-effort is the same code path as OLX (T4), surfaced as "blocked" in status.
- **Risks acknowledged in spec:** exact `search[...]` param names (T2 — data-driven, easy to correct after live check); FB selector volatility (T5 `_parse` targets `/marketplace/item/` links); FB checkpoint risk (T5 session-invalid status + T11 re-login).
- **Type consistency:** `ProviderResult(source, listings, status, reason, found)`, `LiveSearchJob.to_dict()` keys match the frontend `LiveSearchJob` type; `get_orchestrator` dependency name matches the test override.
