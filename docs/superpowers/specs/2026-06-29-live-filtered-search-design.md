# Дизайн: живой поиск авто по фильтрам на нескольких платформах

- **Дата:** 2026-06-29
- **Статус:** одобрен, готов к плану реализации
- **Автор:** согласован с пользователем в сессии

## Контекст и цель

`CarSkyscanner` — агрегатор объявлений о продаже авто. Сейчас поиск (`POST /search`)
фильтрует только то, что уже лежит в БД; скраперы работают по фиксированным URL без
передачи фильтров. Пользователь хочет: **при заполнении фильтров и нажатии «Найти» —
живой сбор машин по этим фильтрам со всех подключённых платформ, с показом свежих
результатов** (синхронное ощущение: ничего не показываем, пока не собрано).

Источники: OLX (работает), Otomoto (DataDome-блок, best-effort), Facebook Marketplace
(требует логин → session reuse).

### Зафиксированные решения
1. **Модель поиска:** live/синхронный — каждый поиск ждёт свежий скрап перед показом.
2. **Facebook:** session reuse — одноразовый ручной логин, переиспользование куки.
3. **Otomoto:** остаётся best-effort (DataDome; будет обычно пустым).
4. **Архитектура:** B — абстракция `ListingProvider` + эндпоинт `/search/live`
   с per-source прогрессом через опрос статуса.

## Архитектура

### `ListingProvider` (интерфейс, одна платформа)
```python
@dataclass
class ProviderResult:
    source: str
    listings: list[dict]
    status: str            # ok | blocked | error | session-invalid | session-not-configured
    reason: str | None

class ListingProvider(ABC):
    source: str
    async def search(self, filters: SearchFilters) -> ProviderResult: ...
```
- `OLXProvider`, `OtomotoProvider` — оборачивают существующий `BaseScraper`
  (stealth, `resolve_url`, `extract_image_url`, скролл для lazy-фото), но строят
  **отфильтрованный** URL.
- `FacebookProvider` — грузит `storage_state.json`, идёт на поиск Marketplace, парсит.

### `SearchOrchestrator`
Запускает включённые провайдеры конкурентно (`asyncio.gather`), собирает листинги,
ведёт per-source статус. Таймаут на провайдер `SEARCH_PROVIDER_TIMEOUT_S` (~45с),
на всю задачу `SEARCH_JOB_TIMEOUT_S` (~60с).

### Эндпоинты (рядом с существующими `/search`, `/scrape`)
- `POST /search/live` — body: `SearchFilters`. Стартует задачу поиска.
  → `{job_id, status:"running"}`.
- `GET /search/live/{job_id}` → `{status, per_source:{...прогресс...}, results:[...] | null}`.
  `results` заполняется при `status=done`.

### Фронтенд
«Найти» → `POST /search/live` → опрос `GET /search/live/{job_id}` каждые ~2с. Во время
ожидания показывает per-source прогресс («OLX 12 ✓ · Otomoto заблокирован · FB грузит…»).
Результаты отображаются только когда задача `done`.

### Персистентность
Orchestrator upsert'ит собранные листинги в БД (`upsert_car`, ключ `(source, url)`) —
кэш + доступ через `/cars`. `source` **определяется по домену URL** (фикс бага №2).
Живой результат отдаётся параллельно.

## Маппинг фильтров → URL (best-effort, per-платформа)

Метод `build_search_url(filters)` у каждого провайдера. Не все фильтры поддержаны везде.

| Фильтр | OLX | Otomoto | FB Marketplace |
|---|---|---|---|
| brand/model | `search[filter_enum_make/model]` | путь `osobowe/{brand}/{model}` | часть `query=` |
| price min/max | `search[filter_float_price:from/to]` | `search[filter_float_price:from/to]` | `minPrice/maxPrice` |
| year min/max | `search[filter_float_year:from/to]` | `search[filter_float_year:from/to]` | — |
| fuel | `search[filter_enum_fuel]` (PL-значение) | `search[filter_enum_fuel_type]` | — |
| mileage/transmission | где поддержано | где поддержано | — |

Внутренние EN-значения маппятся в PL для OLX/Otomoto (`petrol`→`benzyna` и т.п.).
**Риск:** точные имена `search[...]`-параметров нужно сверить с живым сайтом и,
возможно, поднастроить (нормально для скрапинга).

## Facebook — session reuse

- Одноразово, **на хосте** (видимый браузер, не в Docker): `scripts/fb_login.py`
  запускает headed Playwright Chromium → пользователь **вручную** логинится →
  скрипт сохраняет `storage_state.json`.
- **Пароль нигде не хранится и не попадает в код/env** — вводится только пользователем
  в браузере. Рекомендуется сменить пароль и использовать отдельный/throwaway-аккаунт.
- `storage_state.json` → `backend/secrets/`, в `.gitignore`, примонтирован в контейнер.
- `FacebookProvider`: `browser.new_context(storage_state=...)`. Файл отсутствует →
  `session-not-configured`. FB редиректит на логин/checkpoint → `session-invalid`
  (перелогин). Иначе парсит результаты.

## Сквозные вещи

- **Ошибки:** провайдер всегда возвращает статус; orchestrator **не роняет весь поиск**
  при сбое одного источника — частичные результаты + per-source статус.
- **Сид:** остаётся опциональным демо-фолбэком (`AUTO_SEED=true` для дева, чтобы `/cars`
  не был пустым; в проде `false`). URL сидов — реальные домены (готово). Сид синтетический.
- **Безопасность:** `.gitignore` += `backend/secrets/`, `*.storage_state.json`.
  Никаких хардкоженых кредов. Путь к сессии и список источников — через env.
- **Конфиг (env):** `ENABLED_SOURCES=olx,otomoto,facebook`, `FB_STORAGE_STATE_PATH`,
  `SEARCH_PROVIDER_TIMEOUT_S`, `SEARCH_JOB_TIMEOUT_S`.

## Тесты
- Провайдеры на HTML-фикстурах (мок страницы): маппинг фильтров→URL, парсинг,
  определение `source` по домену.
- `SearchOrchestrator` на фейковых провайдерах: агрегация, per-source статус,
  частичный сбой не роняет всё.
- `test_crud.py` не трогается (предполагает изолированную БД).

## Баг-фиксы в рамках работы
- **#2 (бейдж≠ссылка):** `source` по домену URL — OLX-карточка с otomoto-ссылкой
  получает `source=otomoto`.
- **#1 (сид выглядит сломанным):** URL сидов → реальные домены; пометка что сид синтетический.
- **(завершено ранее):** абсолютные URL (`urljoin`), фото через `data-src`+скролл,
  извлечение бренда из title, anti-bot hardening, pin `python:3.11-slim-bookworm`,
  порт postgres `5433`.

## Вне области (YAGNI)
- Авторизация пользователей в приложении.
- История задач (in-memory как сейчас).
- Кросс-платформенный дедуп кроме `(source, url)`.

## Риски
- Точные `search[...]`-параметры OLX/Otomoto — требуют сверки/поднастройки.
- Otomoto под DataDome — почти всегда пусто (best-effort).
- FB: риск checkpoint/бана аккаунта; сессия может протухать → нужен перелогин.
- Долгий (~20-60с) поиск — таймауты HTTP/браузера; смягчается опросом статуса.
