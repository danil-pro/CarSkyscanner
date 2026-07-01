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
