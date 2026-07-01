from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+psycopg2://carsky:carsky@localhost:5432/carsky"
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    AUTO_SEED: bool = True

    # Live search
    ENABLED_SOURCES: str = "olx,otomoto,facebook"
    FB_STORAGE_STATE_PATH: str | None = None
    SEARCH_PROVIDER_TIMEOUT_S: int = 45
    SEARCH_JOB_TIMEOUT_S: int = 60

    # Detail fetch cache
    DETAILS_TTL_S: int = 43200  # 12h cache for scraped listing details

    @property
    def enabled_sources(self) -> list[str]:
        return [s.strip() for s in self.ENABLED_SOURCES.split(",") if s.strip()]


settings = Settings()
