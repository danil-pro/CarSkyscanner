from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import cars, scrape, search_live
from app.config import settings
from app.database import init_db, SessionLocal

app = FastAPI(title="CarSkyscanner API", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


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


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(cars.router)
app.include_router(scrape.router)
app.include_router(search_live.router)
