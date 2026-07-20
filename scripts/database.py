from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
import sys
import os

# Корректный импорт config из корня
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

engine = create_engine(Config.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()