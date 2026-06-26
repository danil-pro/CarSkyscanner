# Дизайн: Car Aggregator MVP (Польша)

- **Дата:** 2026-06-26
- **Статус:** одобрен (brainstorming), ожидает ревью
- **Источник требований:** `PDR.md`

## 1. Цель и рамки

Минимальный работающий продукт: поиск машин через фильтры, агрегация объявлений из нескольких источников (Otomoto, OLX, Facebook Marketplace), единый интерфейс результатов.

**Scope — строго по PDR, MVP only.** Никаких: аутентификации, платежей, AI/ML/ранжирования, рекомендаций, сложной архитектуры.

### Ключевые проектные решения (согласованы)

1. **Стратегия скрейпинга — «скрейперы + seed-данные как основа».** Полноценные Playwright-скрейперы для Otomoto/OLX/FB с честной обработкой блокировок + rich seed-данные в БД гарантируют работающий UI и весь пайплайн даже при блокировке живого скрейпа.
2. **`POST /scrape/run` — асинхронно.** Возвращает `202` + `job_id`, скрейп идёт в фоне, статус опрашивается через `GET /scrape/status`. Не блокирует HTTP-запрос на минуты.
3. **Архитектура — Подход A:** scrapers как Python-пакет верхнего уровня, импортируемый бэкендом; один backend-контейнер содержит FastAPI + Playwright + браузеры. Никакой очереди/Celery — in-process `asyncio`-задача достаточна для dev-MVP.
4. **`facebook.py` — stub.** Честно рапортует `blocked` (нет сессии). Реальный FB-скрейп вынесен за рамки MVP (требует личный аккаунт, риск бана, нарушение ToS).

### Допущения

- Валюта везде `PLN`, без конвертации (поле `currency` хранится).
- Пагинация простая (`limit`/`offset`, по умолчанию 100).
- Дедупликация по `(source, url)` через `upsert`.

## 2. Структура монорепо

```
CarSkyscanner/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app + CORS + роутеры
│   │   ├── config.py          # Pydantic Settings (DB URL и т.д.)
│   │   ├── database.py        # engine, SessionLocal, Base, get_db
│   │   ├── models.py          # SQLAlchemy: Car
│   │   ├── schemas.py         # Pydantic: Car, SearchFilters, ScrapeStatus
│   │   ├── crud.py            # get_cars, search_cars, upsert_car
│   │   ├── scraper_runner.py  # in-memory менеджер асинхр. scrape-задач
│   │   └── routers/
│   │       ├── cars.py        # GET /cars, POST /search
│   │       └── scrape.py      # POST /scrape/run, GET /scrape/status
│   ├── seed.py                # загрузка seed-данных
│   ├── requirements.txt
│   └── Dockerfile
├── scrapers/                  # Python-пакет, импортируется бэкендом
│   ├── __init__.py
│   ├── base.py                # BaseScraper (общий Playwright-контекст, обработка блокировок)
│   ├── normalizer.py          # нормализация → единая схема
│   ├── otomoto.py
│   ├── olx.py
│   └── facebook.py            # stub (честный лог блокировки)
├── frontend/                  # Next.js (App Router) + Tailwind
│   ├── app/page.tsx           # форма фильтров + список результатов
│   ├── components/            # SearchForm, CarCard, SourceBadge, ScrapePanel, ResultsList
│   ├── lib/api.ts             # типизированный клиент к бэкенду
│   └── Dockerfile
├── docker/
│   ├── docker-compose.yml     # backend + frontend + postgres
│   ├── Dockerfile.backend
│   └── Dockerfile.frontend
├── scripts/
│   ├── seed_demo.py           # demo: наполнить БД
│   └── scrape_demo.py         # demo: запустить скрейп напрямую
├── .env.example
├── PDR.md
└── README.md
```

## 3. База данных

Таблица `cars`:

| Поле | Тип | Примечание |
|---|---|---|
| `id` | UUID PK | `gen_random_uuid()` (встроено в PG13+) |
| `title` | TEXT | |
| `brand`, `model` | TEXT | trim/lower при нормализации |
| `year` | INT | |
| `price` | NUMERIC(12,2) | |
| `currency` | TEXT | default `'PLN'` |
| `mileage` | INT | |
| `fuel_type` | TEXT | `petrol|diesel|lpg|hybrid|electric|other` |
| `transmission` | TEXT | `manual|automatic` |
| `location` | TEXT | |
| `source` | TEXT | `otomoto` / `olx` / `facebook` |
| `url` | TEXT | |
| `image_url` | TEXT | |
| `created_at` | TIMESTAMPTZ | default `now()` |

- **Индексы (PDR):** `brand`, `model`, `price`, `year`.
- **Уникальный индекс `(source, url)`** — для дедупликации (upsert при повторном скрейпе).

## 4. Backend API

| Метод | Путь | Назначение |
|---|---|---|
| `GET` | `/cars` | все машины (пагинация `limit`/`offset`) |
| `POST` | `/search` | отфильтрованные машины |
| `POST` | `/scrape/run` | запускает фоновый скрейп → `202 {job_id, status:"running"}` |
| `GET` | `/scrape/status` | статус текущей/последней задачи |
| `GET` | `/health` | readiness (БД доступна) |

### Фильтры `SearchFilters` (тело `POST /search`, все поля optional)

`brand`, `model` (ILIKE), `year_min`, `year_max`, `price_min`, `price_max`, `mileage_max`, `fuel_type`, `transmission`. Пустой фильтр → все записи. Логика — чисто SQL через SQLAlchemy (никакого AI/ранжирования).

```python
# crud.search_cars собирает query динамически
q = select(Car)
if filters.brand:        q = q.where(func.lower(Car.brand) == filters.brand.lower())
if filters.model:        q = q.where(Car.model.ilike(f"%{filters.model}%"))
if filters.year_min:     q = q.where(Car.year >= filters.year_min)
if filters.price_max:    q = q.where(Car.price <= filters.price_max)
if filters.mileage_max:  q = q.where(Car.mileage <= filters.mileage_max)
# ... и т.д.
```

### Асинхронный scrape-менеджер (`scraper_runner.py`)

- In-memory синглтон `ScrapeJobManager`: одна активная задача за раз; повторный запуск во время скрейпа → `409 Conflict`.
- `POST /scrape/run` создаёт `asyncio.create_task`, сразу `202`.
- Задача гоняет источники по очереди `otomoto → olx → facebook`, считает `{found, saved, blocked, errors}` по каждому.
- Результаты сохраняет через `upsert_car` (по `source+url`).
- `GET /scrape/status` → `{status, started_at, finished_at, per_source:{...}, total_saved}`.
- Состояние in-memory; после рестарта контейнера сбрасывается в `idle` (норма для dev-MVP, отмечено в README).

### Pydantic-схемы ответа

`CarOut` (все поля + `id`), `SearchResponse {items, total, limit, offset}`, `ScrapeStatus {...}`.

## 5. Скрейперы, нормализатор, пайплайн

### Контракт (PDR)

Каждый скрейпер возвращает список объектов в единой нормализованной схеме:
```python
{title, brand, model, year, price, mileage, fuel_type, transmission,
 location, source, url, image_url}   # currency добавляет normalizer → "PLN"
```

### Базовый класс `BaseScraper` (`scrapers/base.py`)

- Общий асинхронный Playwright-контекст (один browser на запуск, новый context/страница на источник).
- Шаблон `run()`: открыть страницу списка → собрать карточки → извлечь поля → вернуть `[normalized]`.
- **Обработка блокировок — честно, без агрессивного обхода:** таймауты, детект капчи/403/«Access Denied». При блокировке источник не падает, возвращает `{blocked: True, reason}`. Без ротаций прокси/captcha-solving (вне MVP и этики).
- Общие хелперы парсинга: цена «89 900 PLN» → `89900.0`, пробег «150 tys. km» → `150000`, год → int.

### Нормализатор (`scrapers/normalizer.py`)

- `brand`/`model` → trim + lower для матчинга.
- `fuel_type` → `petrol|diesel|lpg|hybrid|electric|other`.
- `transmission` → `manual|automatic`.
- Валидация: отбрасывает карточки без `url` или `price` (логирует), не роняет весь скрейп.

### Конкретные скрейперы

- **`otomoto.py`** — список по URL-шаблону поиска (`https://www.otomoto.pl/osobowe/<brand>?...`), парсинг карточек (`data-testid` селекторы с fallback на классы). Точные селекторы уточняются по живой разметке при имплементации.
- **`olx.py`** — `https://www.olx.pl/motoryzacja/samochody/`, парсинг карточек.
- **`facebook.py`** — stub: попытка зайти на marketplace, детект логина/блокировки → `blocked` с причиной. Мок-карточки НЕ подмешиваются.

### Пайплайн (PDR)

`SCRAPER → NORMALIZER → DATABASE → API → FRONTEND`. Runner оркеструет: для каждого источника `raw = scraper.run()` → `clean = normalizer.normalize(raw)` → `upsert_car` по `(source, url)`.

### Ограничение (честно)

Живой скрейп otomoto/olx может блокироваться Datadome в headless. Поэтому seed гарантирует работающий UI; при блокировке статус покажет `blocked`, данные берутся из seed/предыдущих успешных запусков.

## 6. Frontend (Next.js + Tailwind)

- Next.js App Router, single-page. Клиент ходит напрямую в FastAPI (`NEXT_PUBLIC_API_URL`), без SSR. CORS разрешён на бэкенде.
- **Один экран `app/page.tsx`:**
  - `SearchForm` (фильтры) → `POST /search`.
  - Список результатов (`ResultsList` / `CarCard`): изображение, цена, год, пробег, `SourceBadge` (цвет по источнику), кнопка «Открыть объявление» → `url`.
  - `ScrapePanel`: «Запустить скрейп» → `POST /scrape/run`, polling `GET /scrape/status` ~2с до терминального, счётчики `saved/blocked/errors` по источникам.
  - Пустое состояние, loading-скелетоны, ошибки сети.

```
components/
├── SearchForm.tsx
├── CarCard.tsx
├── SourceBadge.tsx
├── ScrapePanel.tsx
└── ResultsList.tsx
lib/api.ts   # типизированный fetch-клиент, типы Car/Filters/ScrapeStatus
```

Пагинация — лимит 100 по умолчанию + кнопка «Загрузить ещё» (increment `offset`); чистый Tailwind, без UI-библиотек.

## 7. Docker

`docker-compose.yml` — 3 сервиса:
```yaml
services:
  postgres:   # postgres:15-alpine, volume, healthcheck
  backend:    # python:3.11-slim + playwright + browsers,
              #   depends_on postgres (healthy), :8000,
              #   при старте: create_all + опц. авто-seed
  frontend:   # node:20-alpine, :3000
```
`docker-compose.yml` лежит в `docker/`. Запуск: `cd docker && docker compose up --build` (или `docker compose -f docker/docker-compose.yml up --build` из корня). Фронтенд `:3000`, API `:8000`, Postgres внутренний.

## 8. Обработка ошибок

- **Бэкенд:** единая FastAPI exception-handler → JSON `{detail}`. Блокировки скрейпа — поле в `ScrapeStatus`, не ошибка. БД недоступна при старте → retry с backoff; `/health` отражает состояние.
- **Скрейперы:** источник упал/заблокирован → лог + счётчик, остальные продолжают. Timeout на страницу.
- **Фронтенд:** catch на каждый запрос, сообщение, retry для `/scrape/status`.

## 9. Тестирование

- **Backend (`pytest`):** unit на `normalizer` (парсинг цены/пробега/года/топлива) и `crud.search_cars` (комбинации фильтров) через SQLite in-memory; API через `TestClient` на `GET /cars`, `POST /search`; scrapers — тест на `facebook` stub (возвращает `blocked`) + парсеры на сохранённых HTML-фикстурах (не на живые сайты).
- **Фронтенд:** вручную + smoke через сборку (MVP).

## 10. Seed / demo скрипты

- `backend/seed.py` / `scripts/seed_demo.py` — ~30–50 реалистичных машин (VW/Audi/BMW/Toyota/Skoda, цены в PLN, разные источники incl. facebook) → `upsert`. Запуск: `python seed.py` или авто при пустой БД на старте.
- `scripts/scrape_demo.py` — запускает scrapers напрямую (без API), печатает результаты/блокировки.

## 11. Критерии успеха (PDR)

| Критерий | Как достигается |
|---|---|
| открыть фронтенд | `:3000` после `docker-compose up` |
| выставить фильтры | `SearchForm` |
| увидеть машины из БД | seed + `GET /cars` / `POST /search` |
| запустить скрейп вручную | `ScrapePanel` → `/scrape/run` |
| увидеть новые объявления | после успешного скрейпа (otomoto/olx); при блокировке — честный статус + seed |

## 12. Известные ограничения и риски

- Живой скрейп может блокироваться анти-бот защитой; митигируется seed-данными.
- FB Marketplace не скрейпится в MVP (stub).
- Scrape-статус in-memory — не переживае рестарт контейнера (норма для dev).
- Селекторы otomoto/olx могут меняться — код структурируется так, чтобы их было легко обновить.
