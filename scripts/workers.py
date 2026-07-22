from celery import Celery
import sys
import os
import pickle
import re
import numpy as np
import pandas as pd
import xgboost as xgb
import torch
from transformers import AutoTokenizer, AutoModel

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config
from scripts.database import SessionLocal
import scripts.models as models
import skills_vocabulary as voc

celery_app = Celery("tasks", broker=Config.REDIS_URL, backend=Config.REDIS_URL)

# Инициализация ИИ-архитектуры при старте воркера
MODELS_PATH = "/app/models"
MODEL_XGB_FILE = os.path.join(MODELS_PATH, "xgb_salary_model.json")
MODEL_PCA_FILE = os.path.join(MODELS_PATH, "pca_transformer.pkl")

bst_model = None
pca_transformer = None
tokenizer = None
bert_model = None

def init_ml_models():
    global bst_model, pca_transformer, tokenizer, bert_model
    if bst_model is None:
        # Загрузка обученной модели XGBoost
        bst_model = xgb.XGBRegressor()
        bst_model.load_model(MODEL_XGB_FILE)
        
        # Загрузка объекта сжатия PCA (3 компоненты)
        with open(MODEL_PCA_FILE, "rb") as f:
            pca_transformer = pickle.load(f)
            
        # Загрузка локального трансформера RuBERT-tiny
        tokenizer = AutoTokenizer.from_pretrained("cointegrated/rubert-tiny")
        bert_model = AutoModel.from_pretrained("cointegrated/rubert-tiny")
        bert_model.eval()

def get_bert_embedding(text: str):
    inputs = tokenizer(text, padding=True, truncation=True, max_length=64, return_tensors="pt")
    with torch.no_grad():
        outputs = bert_model(**inputs)
    return outputs.last_hidden_state[0, 0, :].numpy()


@celery_app.task(name="scripts.workers.predict_salary_task")
def predict_salary_task(prediction_id: int, payload: dict, raw_text: str):
    db = SessionLocal()
    try:
        init_ml_models()
        
        db_pred = db.query(models.VacancyPrediction).filter(models.VacancyPrediction.id == prediction_id).first()
        if not db_pred:
            return "ERROR: Session Not Found"

        # Инициализируем вектор признаков нулями строго по именам колонок обученного XGBoost
        input_data = {col: 0.0 for col in bst_model.feature_names_in_}
        
        # Этап 1: Гибридный NLP-анализ текста (REGEX ПО ПОЛНОМУ СЛОВАРЮ)
        clean_text = raw_text.lower()
        
        all_skills_vocab = {}
        all_skills_vocab.update(voc.SOFT_SKILLS_TRIGGERS)
        all_skills_vocab.update(voc.HARD_SKILLS_TRIGGERS)
        all_skills_vocab.update(voc.BUSINESS_SKILLS_TRIGGERS)
        all_skills_vocab.update(voc.SOCIAL_INFRA_TRIGGERS)
        
        activated_pure_skills_count = 0
        total_pure_skills_in_model = 0
        
        meta_cols = ['experience_months', 'skills_completion_rate', 'text_pca_1', 'text_pca_2', 'text_pca_3', 'role_class', 'region_tier', 'bank_tier']
        
        for skill_feature, keywords in all_skills_vocab.items():
            if skill_feature in input_data:
                is_found = any(bool(re.search(r'\b' + re.escape(kw) + r'\b', clean_text)) for kw in keywords)
                if is_found:
                    input_data[skill_feature] = 1.0
                    
                if skill_feature not in meta_cols:
                    total_pure_skills_in_model += 1
                    if is_found:
                        activated_pure_skills_count += 1

        # Конвертируем булевые флаги из веб-интерфейса Streamlit в числа
        for key, value in payload.items():
            if key in input_data and isinstance(value, bool):
                input_data[key] = 1.0 if value else 0.0

        # Этап 2: Динамический расчет мета-параметров
        input_data['experience_months'] = float(payload['experience_months'])
        
        if total_pure_skills_in_model > 0:
            input_data['skills_completion_rate'] = float(activated_pure_skills_count / total_pure_skills_in_model)
        else:
            input_data['skills_completion_rate'] = float(payload['skills_completion_rate'])

        # Этап 3: Семантический анализ и сжатие PCA (RuBERT-tiny)
        embedding = get_bert_embedding(raw_text)
        pca_features = pca_transformer.transform(embedding.reshape(1, -1)).flatten()
        
        input_data['text_pca_1'] = float(pca_features[0])
        input_data['text_pca_2'] = float(pca_features[1])
        input_data['text_pca_3'] = float(pca_features[2])

        # Этап 4: Передаем сырые категориальные значения, как было на обучении
        input_data['role_class'] = int(payload.get('role_class', payload.get('role_id', 1)))
        input_data['region_tier'] = str(payload['region_tier'])
        input_data['bank_tier'] = str(payload['bank_tier'])
        
        # Офисная санитария фичей
        if input_data['role_class'] in [8, 9] and 'has_car_and_driver_license' in input_data:
            input_data['has_car_and_driver_license'] = 0.0

        # Этап 5: Строгое разделение типов данных для инференса
        # Создаем DataFrame и выстраиваем точный порядок колонок из модели
        X_infer = pd.DataFrame([input_data])[bst_model.feature_names_in_]
        
        # Переводим категориальные столбцы в тип 'category'
        X_infer['role_class'] = X_infer['role_class'].astype('category')
        X_infer['region_tier'] = X_infer['region_tier'].astype('category')
        X_infer['bank_tier'] = X_infer['bank_tier'].astype('category')
        
        # Все числовые фичи (навыки, PCA, стаж) приводим к float32
        numeric_cols = [col for col in X_infer.columns if col not in ['role_class', 'region_tier', 'bank_tier']]
        X_infer[numeric_cols] = X_infer[numeric_cols].astype('float32')
        
        # Вычисляем непрерывное зарплатное предложение
        prediction = bst_model.predict(X_infer)
        final_predicted_offer = float(np.round(prediction[0], 0))

        # Обновляем лог-транзакции инференса в СУБД PostgreSQL
        db_pred.predicted_offer = int(final_predicted_offer)
        db_pred.skills_completion_rate = float(input_data['skills_completion_rate'])
        db_pred.status = "SUCCESS"
        db.commit()
        return "SUCCESS"
        
    except Exception as e:
        db.close()
        db = SessionLocal()
        db_pred = db.query(models.VacancyPrediction).filter(models.VacancyPrediction.id == prediction_id).first()
        if db_pred:
            db_pred.status = "FAILURE"
            db.commit()
        return f"ERROR: {str(e)}"
    finally:
        db.close()