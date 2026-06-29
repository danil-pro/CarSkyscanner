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
