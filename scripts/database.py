from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
import sys
import os

# Корректный импорт config из корня проекта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

# НАСТРОЙКА УСТОЙЧИВОГО К НАГРУЗКАМ ДВИЖКА СУБД POSTGRESQL
engine = create_engine(
    Config.DATABASE_URL,
    # Увеличиваем базовый размер пула до 20 одновременных постоянных соединений
    pool_size=20,
    # Разрешаем пулу временно создавать до 30 дополнительных соединений при пиковых нагрузках
    max_overflow=30,
    # Защита от падения: проверяем коннект перед каждым запросом (избегаем "OperationalError: connection lost")
    pool_pre_ping=True,
    # Автоматически закрываем и пересоздаем соединения каждые 30 минут
    pool_recycle=1800,
)

# Фабрика сессий для работы с транзакциями
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Базовый класс для декларативных моделей SQLAlchemy
Base = declarative_base()


def get_db():
    """
    Зависимость (Dependency) для FastAPI-эндпоинтов.
    Гарантирует безопасное открытие и 100% закрытие сессии после выполнения запроса.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
