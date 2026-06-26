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
