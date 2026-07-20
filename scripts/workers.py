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
# Импортируем полный словарь триггеров
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
        # Мы ищем ключевые слова во всем тексте вакансии, переведенном в нижний регистр
        clean_text = raw_text.lower()
        
        # Объединяем все группы навыков для сквозного парсинга
        all_skills_vocab = {}
        all_skills_vocab.update(voc.SOFT_SKILLS_TRIGGERS)
        all_skills_vocab.update(voc.HARD_SKILLS_TRIGGERS)
        all_skills_vocab.update(voc.BUSINESS_SKILLS_TRIGGERS)
        all_skills_vocab.update(voc.SOCIAL_INFRA_TRIGGERS)
        
        activated_pure_skills_count = 0
        total_pure_skills_in_model = 0
        
        # Служебный список колонок, которые не относятся к чистым хард/софт навыкам
        meta_cols = ['experience_months', 'skills_completion_rate', 'text_pca_1', 'text_pca_2', 'text_pca_3']
        
        for skill_feature, keywords in all_skills_vocab.items():
            # Проверяем, участвует ли этот признак вообще в структуре нашей модели
            if skill_feature in input_data:
                # Взводим бинарный флаг, если нашли хотя бы одно совпадение из skills_vocabulary
                is_found = any(bool(re.search(r'\b' + re.escape(kw) + r'\b', clean_text)) for kw in keywords)
                if is_found:
                    input_data[skill_feature] = 1.0
                    
                # Если это чистый ИТ-или бизнес-навык, учитываем его в расчете плотности (как на этапе EDA)
                if skill_feature not in meta_cols and not skill_feature.startswith('role_class_') and not skill_feature.startswith('region_tier_') and not skill_feature.startswith('bank_tier_'):
                    total_pure_skills_in_model += 1
                    if is_found:
                        activated_pure_skills_count += 1

        # Этап 2: Динамический расчет мета-параметров
        # 1. Заполняем минимальный стаж напрямую из ползунка Streamlit
        input_data['experience_months'] = float(payload['experience_months'])
        
        # 2. Вычисляем честный skills_completion_rate на основе реально найденных навыков в тексте
        if total_pure_skills_in_model > 0:
            input_data['skills_completion_rate'] = float(activated_pure_skills_count / total_pure_skills_in_model)
        else:
            input_data['skills_completion_rate'] = float(payload['skills_completion_rate'])

        # Этап 3: семантический анализ и сжатие PCA (RuBERT-tiny)
        # Извлекаем контекстный эмбеддинг из полного текста,
        # так как PCA обучался строго на признаках текстовых описаний, а не коротких названий вакансий
        embedding = get_bert_embedding(raw_text)
        
        # Проецируем плотный вектор через сохраненный трансформер PCA (transform вместо fit_transform)
        pca_features = pca_transformer.transform(embedding.reshape(1, -1)).flatten()
        
        # Безопасно раскладываем 3 полученные ортогональные координаты по фичам матрицы X
        input_data['text_pca_1'] = float(pca_features[0])
        input_data['text_pca_2'] = float(pca_features[1])
        input_data['text_pca_3'] = float(pca_features[2])

        # Этап 4: активация one-hot категорий (классы, тыры регионов и классы)
        role_key = f"role_class_{payload['role_class']}"
        region_key = f"region_tier_{payload['region_tier']}"
        bank_key = f"bank_tier_{payload['bank_tier']}"
        
        if role_key in input_data: input_data[role_key] = 1.0
        if region_key in input_data: input_data[region_key] = 1.0
        if bank_key in input_data: input_data[bank_key] = 1.0
        
        # Офисная санитария фичей: если класс 8 или 9, принудительно обнуляем авто (как в финальной ML-сессии)
        if int(payload['role_class']) in [8, 9] and 'has_car_and_driver_license' in input_data:
            input_data['has_car_and_driver_license'] = 0.0

        # Этап 5: инференс модели XGBOOST
        # Превращаем словарь в DataFrame с идеальным соблюдением порядка колонок обучения
        X_infer = pd.DataFrame([input_data])[bst_model.feature_names_in_]
        
        # Вычисляем непрерывное зарплатное предложение
        prediction = bst_model.predict(X_infer)
        final_predicted_offer = float(np.round(prediction[0], 0))

        # Обновляем логтранзакции инференса в СУБД PostgreSQL
        db_pred.predicted_offer = final_predicted_offer
        db_pred.skills_completion_rate = input_data['skills_completion_rate']
        db_pred.status = "SUCCESS"
        db.commit()
        return "SUCCESS"
        
    except Exception as e:
        db_pred = db.query(models.VacancyPrediction).filter(models.VacancyPrediction.id == prediction_id).first()
        if db_pred:
            db_pred.status = "FAILURE"
            db.commit()
        return f"ERROR: {str(e)}"
    finally:
        db.close()