from sqlalchemy import Column, Integer, String, Float, JSON, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from scripts.database import Base


class VacancyPrediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String, unique=True, index=True, nullable=True)

    # --- Мета-параметры кандидата ---
    role_class = Column(Integer, nullable=False)
    experience_months = Column(Integer, nullable=False)
    # Тип изменен на Integer для идеального соответствия модели и API
    region_tier = Column(Integer, nullable=False)
    bank_tier = Column(String, nullable=False)
    skills_completion_rate = Column(Float, nullable=False)

    # Хранилище для всех 45 верифицированных навыков (чистый JSON-словарь флагов True/False)
    verified_skills = Column(JSON, nullable=False)

    # --- Системные поля расчета ---
    predicted_offer = Column(Integer, nullable=True)
    status = Column(String, default="PENDING")

    # Хранилище для ТОП-25 факторов ценообразования SHAP
    # PostgreSQL эффективно индексирует и хранит такие структуры
    explanation_json = Column(JSON, nullable=True)

    # Поле для логирования трейсбэков ошибок воркера Celery
    error_message = Column(String, nullable=True)

    # Связь один-к-одному с таблицей фидбека (Acceptance Rate мониторинг)
    feedback = relationship("Feedback", back_populates="prediction", uselist=False)


class Feedback(Base):
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True, index=True)
    prediction_id = Column(Integer, ForeignKey("predictions.id"), unique=True, nullable=False)
    hr_accepted = Column(Boolean, nullable=False)
    actual_salary = Column(Integer, nullable=True)

    # Обратная связь с записью расчета
    prediction = relationship("VacancyPrediction", back_populates="feedback")
