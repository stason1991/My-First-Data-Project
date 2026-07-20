from fastapi.testclient import TestClient
from backend import app

client = TestClient(app)

def test_prediction_endpoint_validation():
    # Проверка перехвата некорректных типов данных и отрицательного стажа
    bad_payload = {
        "role_class": "STRING_ERROR",
        "experience_months": -10,
        "region_tier": "Tier-1",
        "bank_tier": "Bank_Tier_1"
    }
    response = client.post("/api/v1/predict", json=bad_payload)
    assert response.status_code == 422

def test_feedback_loop_not_found():
    # Верификация роута обратной связи при некорректном ID сессии
    fake_feedback = {
        "prediction_id": 99999,
        "hr_accepted": True
    }
    response = client.post("/api/v1/feedback", json=fake_feedback)
    assert response.status_code == 404