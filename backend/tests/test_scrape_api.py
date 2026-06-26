from fastapi.testclient import TestClient
from app.main import app
from app.scraper_runner import manager
from app import schemas


def test_status_endpoint():
    manager._status = schemas.ScrapeStatus(status="idle", per_source={})
    client = TestClient(app)
    r = client.get("/scrape/status")
    assert r.status_code == 200
    assert r.json()["status"] == "idle"


def test_run_returns_202(monkeypatch):
    manager._status = schemas.ScrapeStatus(status="idle", per_source={})

    async def fake_run(job_id):  # avoid launching real playwright
        manager._status.status = "done"

    monkeypatch.setattr(manager, "_run", fake_run)
    client = TestClient(app)
    r = client.post("/scrape/run")
    assert r.status_code == 202
    assert r.json()["status"] == "running"


def test_conflict_when_running():
    manager._status = schemas.ScrapeStatus(status="running", per_source={})
    client = TestClient(app)
    r = client.post("/scrape/run")
    assert r.status_code == 409
