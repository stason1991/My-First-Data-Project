from celery import Celery
import sys
import os
import pickle
import re
import json
import numpy as np
import pandas as pd
import xgboost as xgb
import torch
import shap
from transformers import AutoTokenizer, AutoModel

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config
from scripts.database import SessionLocal
import scripts.models as models
import skills_vocabulary as voc

celery_app = Celery("tasks", broker=Config.REDIS_URL, backend=Config.REDIS_URL)

# Инициализация ИИ-архитектуры при старте воркера
MODELS_PATH = "/app/models"
MODEL_XGB_FILE = os.path.join(MODELS_PATH, "xgb_salary_model_optuna.json")
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

        meta_cols = [
            "experience_months",
            "skills_completion_rate",
            "text_pca_1",
            "text_pca_2",
            "text_pca_3",
            "role_class",
            "region_tier",
            "bank_tier",
        ]

        for skill_feature, keywords in all_skills_vocab.items():
            if skill_feature in input_data:
                is_found = any(bool(re.search(r"\b" + re.escape(kw) + r"\b", clean_text)) for kw in keywords)
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
        input_data["experience_months"] = float(payload["experience_months"])

        if total_pure_skills_in_model > 0:
            input_data["skills_completion_rate"] = float(activated_pure_skills_count / total_pure_skills_in_model)
        else:
            input_data["skills_completion_rate"] = float(payload["skills_completion_rate"])

        # Этап 3: Семантический анализ и сжатие PCA (RuBERT-tiny)
        embedding = get_bert_embedding(raw_text)
        pca_features = pca_transformer.transform(embedding.reshape(1, -1)).flatten()

        input_data["text_pca_1"] = float(pca_features[0])
        input_data["text_pca_2"] = float(pca_features[1])
        input_data["text_pca_3"] = float(pca_features[2])

        # Этап 4: Передаем сырые категориальные значения, как было на обучении
        input_data["role_class"] = int(payload.get("role_class", payload.get("role_id", 1)))
        input_data["region_tier"] = str(payload["region_tier"])
        input_data["bank_tier"] = str(payload["bank_tier"])

        # Офисная санитария фичей
        if input_data["role_class"] in [8, 9] and "has_car_and_driver_license" in input_data:
            input_data["has_car_and_driver_license"] = 0.0

        # Этап 5: Строгое разделение типов данных для инференса
        X_infer = pd.DataFrame([input_data])[bst_model.feature_names_in_]

        # Переводим категориальные столбцы в тип 'category'
        X_infer["role_class"] = X_infer["role_class"].astype("category")
        X_infer["region_tier"] = X_infer["region_tier"].astype("category")
        X_infer["bank_tier"] = X_infer["bank_tier"].astype("category")

        # Все числовые фичи (навыки, PCA, стаж) приводим к float32
        numeric_cols = [col for col in X_infer.columns if col not in ["role_class", "region_tier", "bank_tier"]]
        X_infer[numeric_cols] = X_infer[numeric_cols].astype("float32")

        # Вычисляем непрерывное зарплатное предложение
        prediction = bst_model.predict(X_infer)
        final_predicted_offer = float(np.round(prediction[0], 0))

        def shap_predict_wrapper(x):
            df_tmp = pd.DataFrame(x, columns=bst_model.feature_names_in_)
            df_tmp["role_class"] = df_tmp["role_class"].astype("category")
            df_tmp["region_tier"] = df_tmp["region_tier"].astype("category")
            df_tmp["bank_tier"] = df_tmp["bank_tier"].astype("category")
            df_tmp["experience_months"] = df_tmp["experience_months"].astype("int32")

            meta_indices = ["role_class", "experience_months", "region_tier", "bank_tier"]
            num_cols = [c for c in df_tmp.columns if c not in meta_indices]
            df_tmp[num_cols] = df_tmp[num_cols].astype("float32")
            return bst_model.predict(df_tmp)

        # Шаблон, заполненный нулями строго по матрице обучения
        # Для категорий подставляем первые валидные значения из KNOWN_CATEGORIES (или вашего кода), чтобы XGBoost не ругался
        X_background = X_infer.copy()
        for col in X_background.columns:
            if col in ["role_class", "region_tier", "bank_tier"]:
                # Берем первую доступную дефолтную категорию для фона
                X_background[col] = X_background[col].iloc[0]
            else:
                X_background[col] = 0.0

        # Передаем фоновый датафрейм в качестве бэкграунда, а X_infer — для оценки
        explainer = shap.KernelExplainer(shap_predict_wrapper, X_background)
        shap_values = explainer.shap_values(X_infer)

        feature_impacts = {}
        flat_shap_values = np.array(shap_values).flatten()

        for feature_name, shap_value in zip(bst_model.feature_names_in_, flat_shap_values):
            clean_val_str = str(shap_value).replace("[", "").replace("]", "").strip()
            clean_val = float(clean_val_str)

            # Забираем только те фичи, которые изменили базовый оклад хотя бы на 1 копейку
            if abs(clean_val) > 0.01:
                feature_impacts[feature_name] = float(clean_val)

        sorted_all_impacts = sorted(feature_impacts.items(), key=lambda item: abs(item[1]), reverse=True)
        top_25_impacts = dict(sorted_all_impacts[:25])

        # Этап 7: Фиксация результатов в СУБД PostgreSQL
        db_pred.predicted_offer = int(final_predicted_offer)
        db_pred.skills_completion_rate = float(input_data["skills_completion_rate"])
        db_pred.explanation_json = json.dumps(top_25_impacts, ensure_ascii=False)
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
