from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+psycopg2://carsky:carsky@localhost:5432/carsky"
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    AUTO_SEED: bool = True


settings = Settings()
