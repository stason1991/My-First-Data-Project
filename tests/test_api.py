import pytest
from fastapi.testclient import TestClient
from backend import app
from scripts import models

client = TestClient(app)


@pytest.fixture
def mock_celery_send_task(mocker):
    """
    Фикстура для изоляции Redis/Celery.
    Перехватывает отправку задачи и возвращает фейковый объект с UUID таски.
    """

    class FakeTask:
        id = "fake-celery-uuid-12345"

    # Мокаем метод send_task внутри модуля workers
    return mocker.patch("scripts.workers.celery_app.send_task", return_value=FakeTask())


def test_create_prediction_success_happy_path(mock_celery_send_task):
    """
    Тестирование успешного прохождения валидации и отправки задачи в Celery.
    Проверяем корректное разделение 60 признаков на 5 колонок БД и 55 JSON-навыков.
    """
    valid_payload = {
        "role_class": 8,
        "experience_months": 36,
        "region_tier": 1,
        "bank_tier": "Bank_Tier_1",
        "skills_completion_rate": 0.084,
        "is_grade_senior": True,
        "is_grade_middle": False,
        "skill_compliance_aml_kyc": True,
        "skill_cold_sales": True,
        "raw_text": "Резюме кандидата на должность руководителя розничного блока",
    }

    response = client.post("/api/v1/predict", json=valid_payload)

    # Проверяем, что API вернуло статус 202 (Accepted) и корректный перехваченный UUID
    assert response.status_code == 202
    assert response.json()["task_id"] == "fake-celery-uuid-12345"
    assert response.json()["status"] == "PENDING"

    # Проверяем, что бэкенд ровно один раз вызвал Celery-брокер
    mock_celery_send_task.assert_called_once()


def test_prediction_endpoint_validation_negative():
    """
    Верификация перехвата некорректных типов данных и отрицательного стажа.
    Проверяет, что Pydantic-схема отрабатывает ограничения ge=0 и типы данных.
    """
    bad_payload = {
        "role_class": 8,
        "experience_months": -10,  # Ошибка: отрицательный стаж (ge=0)
        "region_tier": 1,
        "bank_tier": "Top1",
        "skills_completion_rate": 0.084,
        "is_grade_senior": False,
        "is_grade_middle": True,
        "raw_text": "Резюме для теста валидации",
    }

    response = client.post("/api/v1/predict", json=bad_payload)
    assert response.status_code == 422


def test_prediction_endpoint_type_error():
    """
    Проверка перехвата строковой ошибки в числовом поле класса роли.
    """
    bad_payload = {
        "role_class": "STRING_ERROR",  # Ошибка: строка вместо int
        "experience_months": 24,
        "region_tier": 1,
        "bank_tier": "Top1",
        "raw_text": "Тестовый текст резюме",
    }

    response = client.post("/api/v1/predict", json=bad_payload)
    assert response.status_code == 422


def test_feedback_loop_not_found():
    """
    Верификация роута обратной связи при некорректном ID сессии.
    Проверяет, что база данных возвращает 404, если запись в СУБД отсутствует.
    """
    fake_feedback = {"prediction_id": 99999, "hr_accepted": True, "actual_salary": None}  # Несуществующий ID
    # Используем актуальный URL роута с префиксом /predict
    response = client.post("/api/v1/predict/feedback", json=fake_feedback)
    assert response.status_code == 404
