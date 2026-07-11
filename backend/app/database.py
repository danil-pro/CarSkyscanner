from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.config import settings

engine = create_engine(settings.DATABASE_URL, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    import app.models  # noqa: F401  ensure model is registered
    Base.metadata.create_all(bind=engine)
    # create_all won't add columns to an existing table (no Alembic in this
    # project), so add new columns idempotently on Postgres.
    if engine.dialect.name == "postgresql":
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE car_details ADD COLUMN IF NOT EXISTS specs JSON"))
            conn.execute(text("ALTER TABLE cars ADD COLUMN IF NOT EXISTS body_type VARCHAR(32)"))
