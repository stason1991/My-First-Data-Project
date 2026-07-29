import os
import sys
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.database import Base, get_db
from scripts import models  

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

# Добавляем StaticPool, чтобы SQLite удерживала одну базу данных между потоками FastAPI
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)

TestingSessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine, 
    expire_on_commit=False
)

@pytest.fixture(autouse=True, scope="session")
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(autouse=True)
def override_get_db():
    def _get_test_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    from backend import app
    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.clear()