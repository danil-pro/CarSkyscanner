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


def test_health():
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_get_cars_and_search():
    db = SessionLocal()
    crud.upsert_car(db, dict(title="VW Golf", brand="volkswagen", model="golf", year=2020,
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
