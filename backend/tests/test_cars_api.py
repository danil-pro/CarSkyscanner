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
