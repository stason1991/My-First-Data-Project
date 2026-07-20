from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from scripts.database import get_db, engine, Base
import scripts.models as models
import scripts.schemas as schemas
import scripts.workers as workers

app = FastAPI(title="Salary Prediction b2b REST API", version="1.0.0")

# Автоматическое развертывание схем таблиц в PostgreSQL при старте
Base.metadata.create_all(bind=engine)

@app.post("/api/v1/predict", response_model=schemas.PredictionResponse, status_code=202)
def create_prediction(payload: schemas.PredictionRequest, db: Session = Depends(get_db)):
    # 1. Записываем транзакцию в PostgreSQL, сохраняя 100% входящих параметров
    db_pred = models.VacancyPrediction(
        role_class=payload.role_class,
        experience_months=payload.experience_months,
        region_tier=payload.region_tier,
        bank_tier=payload.bank_tier,
        skills_completion_rate=payload.skills_completion_rate,
        skill_vip_negotiations=payload.skill_vip_negotiations,
        skill_cold_sales=payload.skill_cold_sales,
        skill_initiative_proactivity=payload.skill_initiative_proactivity,
        status="PENDING"
    )
    db.add(db_pred)
    db.commit()
    db.refresh(db_pred)

    # 2. МАСШТАБИРУЕМАЯ ML-ОТПРАВКА: Передаем ровно 3 аргумента (raw_text извлечен из Pydantic)
    task = workers.celery_app.send_task(
        "scripts.workers.predict_salary_task",
        args=[db_pred.id, payload.dict(), payload.raw_text]  # ИСПРАВЛЕНО: Добавлен третий обязательный аргумент payload.raw_text
    )
    
    # 3. Привязываем сгенерированный Celery UUID к записи в СУБД для поллинга статуса
    db_pred.task_id = task.id
    db.commit()
    
    return {"task_id": task.id, "status": "PENDING"}

@app.get("/api/v1/predict/status/{task_id}")
def get_prediction_status(task_id: str, db: Session = Depends(get_db)):
    db_pred = db.query(models.VacancyPrediction).filter(models.VacancyPrediction.task_id == task_id).first()
    if not db_pred:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "id": db_pred.id,
        "status": db_pred.status,
        "predicted_offer": db_pred.predicted_offer
    }

@app.post("/api/v1/feedback")
def submit_feedback(payload: schemas.FeedbackRequest, db: Session = Depends(get_db)):
    db_pred = db.query(models.VacancyPrediction).filter(models.VacancyPrediction.id == payload.prediction_id).first()
    if not db_pred:
        raise HTTPException(status_code=404, detail="Session not found")
    
    db_feedback = models.Feedback(
        prediction_id=payload.prediction_id,
        hr_accepted=payload.hr_accepted,
        actual_salary=payload.actual_salary
    )
    db.add(db_feedback)
    db.commit()
    return {"status": "success"}