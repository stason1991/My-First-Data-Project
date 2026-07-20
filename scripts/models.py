from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from scripts.database import Base

class VacancyPrediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String, unique=True, index=True, nullable=True)
    role_class = Column(Integer, nullable=False)
    experience_months = Column(Integer, nullable=False)
    region_tier = Column(String, nullable=False)
    bank_tier = Column(String, nullable=False)
    skills_completion_rate = Column(Float, nullable=False)
    skill_vip_negotiations = Column(Boolean, default=False)
    skill_cold_sales = Column(Boolean, default=False)
    skill_initiative_proactivity = Column(Boolean, default=False)
    predicted_offer = Column(Float, nullable=True)
    status = Column(String, default="PENDING")

    feedbacks = relationship("Feedback", back_populates="prediction")

class Feedback(Base):
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True, index=True)
    prediction_id = Column(Integer, ForeignKey("predictions.id"))
    hr_accepted = Column(Boolean, nullable=False)
    actual_salary = Column(Float, nullable=True)

    prediction = relationship("VacancyPrediction", back_populates="feedbacks")