import pytest
from sqlalchemy import create_engine
from app.database import Base, SessionLocal, engine
import app.models  # noqa: F401  register the Car model


@pytest.fixture(scope="function", autouse=True)
def sqlite_db(tmp_path):
    test_engine = create_engine(f"sqlite:///{tmp_path}/test.db", future=True)
    Base.metadata.create_all(bind=test_engine)
    SessionLocal.configure(bind=test_engine)
    yield
    SessionLocal.configure(bind=engine)
    Base.metadata.drop_all(bind=test_engine)
