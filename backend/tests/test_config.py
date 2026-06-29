from app.config import Settings


def test_enabled_sources_split():
    s = Settings(ENABLED_SOURCES="olx, otomoto ,facebook")
    assert s.enabled_sources == ["olx", "otomoto", "facebook"]


def test_defaults():
    s = Settings()
    assert s.SEARCH_PROVIDER_TIMEOUT_S == 45
    assert s.SEARCH_JOB_TIMEOUT_S == 60
