from pydantic import BaseModel, Field
from typing import Optional

class PredictionRequest(BaseModel):
    # Мета-параметры позиции
    role_class: int = Field(..., example=8)
    experience_months: int = Field(..., ge=0, le=120)
    region_tier: str = Field(..., example="Tier-1")
    bank_tier: str = Field(..., example="Bank_Tier_1")
    skills_completion_rate: float = Field(0.084, ge=0.0, le=1.0)
    
    # 1. Группа Soft Skills
    skill_general_negotiations: bool = False
    skill_vip_negotiations: bool = False
    skill_active_listening: bool = False
    skill_persuasion_argumentation: bool = False
    skill_public_presentation: bool = False
    skill_business_correspondence: bool = False
    skill_cold_sales: bool = False
    skill_telemarketing: bool = False
    skill_objection_handling: bool = False
    skill_cross_sales: bool = False
    skill_difficult_clients: bool = False
    skill_conflict_resolution: bool = False
    skill_stress_resistance: bool = False
    skill_adaptability_flexibility: bool = False
    skill_teamwork: bool = False
    skill_result_defense: bool = False
    skill_mentoring_coaching: bool = False
    skill_initiative_proactivity: bool = False
    
    # 2. Группа Hard Skills
    skill_pc_tablet_advanced: bool = False
    skill_abs_crm: bool = False
    skill_advanced_excel: bool = False
    skill_python_automation: bool = False
    skill_sql_queries: bool = False
    skill_bi_analytics: bool = False
    skill_business_eda: bool = False
    skill_predictive_modeling: bool = False
    skill_java_backend: bool = False
    skill_devops_cicd: bool = False
    skill_big_data_stack: bool = False
    skill_finance_cert_cfa: bool = False
    skill_finance_cert_frm: bool = False
    skill_finance_cert_fsfr: bool = False
    
    # 3. Группа Business Skills
    skill_kpi_system_management: bool = False
    skill_kpi_troubleshooting_eda: bool = False
    skill_sales_book_analysis: bool = False
    skill_result_defense_data: bool = False
    skill_roleplay_defense: bool = False
    skill_dynamic_field_adaptation: bool = False
    skill_rapid_learning_testing: bool = False
    skill_pnl_product_metrics: bool = False
    skill_banking_regulation_basel: bool = False
    skill_compliance_aml_kyc: bool = False
    skill_hr_analytics_metrics: bool = False
    
    # 4. Группа SOCIAL_INFRA_TRIGGERS
    edu_level_encoded: bool = True
    has_car_and_driver_license: bool = False
    has_remote_hybrid_schedule: bool = False
    
    # Текст резюме для BERT + PCA + Regex разбора на воркере
    raw_text: str = Field(..., example="Полный текст резюме соискателя")

class PredictionResponse(BaseModel):
    task_id: str
    status: str

# Добавляем класс FeedbackRequest для восстановления бэкенда FastAPI
class FeedbackRequest(BaseModel):
    prediction_id: int
    hr_accepted: bool
    actual_salary: Optional[float] = None

    class Config:
        from_attributes = True