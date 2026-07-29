from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from scripts.database import get_db, engine, Base
import scripts.models as models
import scripts.schemas as schemas
import scripts.workers as workers

app = FastAPI(title="Salary Prediction b2b REST API", version="1.0.0")

# Настройка CORS для защиты от блокировок запросов со Streamlit
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Безопасное развертывание схем таблиц в PostgreSQL при старте приложения
@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)


@app.post("/api/v1/predict", response_model=schemas.PredictionResponse, status_code=202)
def create_prediction(payload: schemas.PredictionRequest, db: Session = Depends(get_db)):

    # 1. Извлекаем данные из Pydantic-модели в python-словарь
    payload_data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()

    # 2. Выделяем мета-параметры, которые физически существуют как колонки в модели VacancyPrediction
    db_columns = {"role_class", "experience_months", "region_tier", "bank_tier", "skills_completion_rate"}

    # Формируем словарь только из тех полей, которые есть в таблице базы данных
    db_data = {k: v for k, v in payload_data.items() if k in db_columns}

    # 3. Все остальные поля (45 навыков + 4 новых грейда) изолируем и упаковываем в JSON-поле verified_skills
    # Исключаем только физические колонки БД и raw_text (текст резюме в БД не пишем ради экономии места)
    excluded_fields = db_columns | {"raw_text"}
    db_data["verified_skills"] = {k: v for k, v in payload_data.items() if k not in excluded_fields}

    db_data["status"] = "PENDING"

    try:
        # Создаем запись в PostgreSQL (структура строго соответствует models.py)
        db_pred = models.VacancyPrediction(**db_data)
        db.add(db_pred)
        db.commit()
        db.refresh(db_pred)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Ошибка записи транзакции в PostgreSQL: {e}")

    # 4. ML-отправка в Celery: передаем исходный полный payload_data, где есть и грейды, и навыки для XGBoost
    try:
        task = workers.celery_app.send_task(
            "scripts.workers.predict_salary_task", args=[db_pred.id, payload_data, payload.raw_text]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Сбой брокера очередей Celery при отправке задачи: {e}")

    # 5. Привязываем Celery UUID к записи для поллинга статуса
    db_pred.task_id = task.id
    db.commit()

    return {"task_id": task.id, "status": "PENDING"}


@app.get("/api/v1/predict/status/{task_id}")
def get_prediction_status(task_id: str, db: Session = Depends(get_db)):
    db_pred = db.query(models.VacancyPrediction).filter(models.VacancyPrediction.task_id == task_id).first()
    if not db_pred:
        raise HTTPException(status_code=404, detail="Task not found")

    # Добавлен возврат explanation_json для отрисовки ТОП-25 фичей SHAP в Streamlit,
    # а также error_message для удобного дебага ошибок воркера прямо на фронтенде.
    return {
        "id": db_pred.id,
        "status": db_pred.status,
        "predicted_offer": db_pred.predicted_offer,
        "explanation_json": db_pred.explanation_json,
        "error_message": db_pred.error_message if hasattr(db_pred, "error_message") else None,
    }


# Изменили префикс пути на /predict/feedback для 100% совпадения с запросами из app.py
@app.post("/api/v1/predict/feedback")
def submit_feedback(payload: schemas.FeedbackRequest, db: Session = Depends(get_db)):
    db_pred = db.query(models.VacancyPrediction).filter(models.VacancyPrediction.id == payload.prediction_id).first()
    if not db_pred:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        db_feedback = models.Feedback(
            prediction_id=payload.prediction_id, hr_accepted=payload.hr_accepted, actual_salary=payload.actual_salary
        )
        db.add(db_feedback)
        db.commit()
        return {"status": "success"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Ошибка сохранения фидбека в PostgreSQL: {e}")
