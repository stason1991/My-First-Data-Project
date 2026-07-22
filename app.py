import streamlit as st
import requests
import time

st.set_page_config(page_title="AI Talent Hub Salary Calc", layout="wide")

st.title("Интеллектуальная система оценки кандидатов и зарплатного оффера")
st.caption("Микросервисный контур: FastAPI + Celery + PostgreSQL | Модель: XGBoost (MAPE 21.8%)")

BACKEND_URL = "http://salary_fastapi_backend:8000/api/v1"

# 17 Репрезентативных классов должностей банковской сферы из EDA
ROLES = {
    1: "Представители банка/Мобильные менеджеры/Доставка карт", 
    2: "Прямые продажи / DSA",
    6: "Операционисты / Сервис-менеджеры", 
    7: "Кассиры",
    8: "Менеджер по продажам розничного блока", 
    9: "Главный менеджер по продажам розничного блока",
    11: "Персональный менеджер VIP / Private / Привилегия", 
    13: "Менеджер по обслуживанию юридическим лиц", 
    14: "Руководитель блока юридических лиц", 
    15: "Ипотечный менеджер",
    20: "Руководитель дополнительного офиса", 
    21: "Data Scientist / ML Engineer", 
    23: "Промышленная Backend-разработка на Java", 
    24: "Системный аналитик", 
    25: "DevOps Engineer", 
    31: "HR-менеджер"
}

col1, col2 = st.columns(2)

with col1:
    st.subheader("Паспорт кандидата и резюме")
    role_id = st.selectbox(
        "Целевая роль в банке (Класс):", 
        options=list(ROLES.keys()), 
        format_func=lambda x: f"Класс {x:02d} — {ROLES[x]}"
    )
    experience = st.slider("Подтвержденный стаж работы (в месяцах):", 0, 120, 24)
    region_tier = st.selectbox("Регион найма (Локация):", ["Tier-1", "Tier-2", "Tier-3", "Tier-4"])
    bank_tier = st.selectbox("Тир текущей финансовой организации:", ["Bank_Tier_1", "Bank_Tier_2", "Bank_Tier_3"])
    
    raw_resume_text = st.text_area(
        "Скопируйте сюда полный текст резюме соискателя (опыт, обязанности, навыки):",
        value="Опыт работы в Альфа-Банке 2 года. Ведение b2b-клиентов, подготовка коммерческих предложений, знание SQL на уровне написания простых JOIN запросов, базовый Python для автоматизации выгрузок. Работа в Jupyter Notebook.",
        height=300
    )

with col2:
    st.subheader("Верификация компетенций на интервью")
    st.write("Отметьте навыки, которые кандидат подтвердил на технических и софт-собеседованиях:")
    
    # Распределяем все 45 навыков по четырем логическим b2b-вкладкам
    tab_soft, tab_hard, tab_biz, tab_infra = st.tabs([
        "Soft Skills", "Hard Skills", "Business Skills", "Образование и наличие автомобиля"
    ])
    
    with tab_soft:
        st.caption("Коммуникабельность")
        s_gen_neg = st.checkbox("Деловые переговоры / Общая коммуникация", key="s_gen_neg")
        s_vip_neg = st.checkbox("VIP-переговоры / Работа с первыми лицами", key="s_vip_neg")
        s_act_list = st.checkbox("Активное слушание / Эмпатия / Клиентоцентричность", key="s_act_list")
        s_persuasion = st.checkbox("Техники убеждения и сильная аргументация", key="s_persuasion")
        s_public = st.checkbox("Публичные выступления / Навыки презентации", key="s_public")
        s_correspondence = st.checkbox("Деловая переписка (КП / E-mail)", key="s_correspondence")
        s_cold = st.checkbox("Холодные продажи", key="s_cold")
        s_tele = st.checkbox("Телефонные продажи / Обзвоны", key="s_tele")
        s_objection = st.checkbox("Работа с возражениями", key="s_objection")
        s_cross = st.checkbox("Кросс-продажи", key="s_cross")
        s_diff_cli = st.checkbox("Работа со сложными клиентами", key="s_diff_cli")
        s_conflict = st.checkbox("Навыки разрешения конфликтов", key="s_conflict")
        s_stress = st.checkbox("Стрессоустойчивость", key="s_stress")
        s_adapt = st.checkbox("Адаптивность / Быстрая обучаемость", key="s_adapt")
        s_team = st.checkbox("Работа в команде", key="s_team")
        s_res_def = st.checkbox("Защита результатов и обоснование KPI", key="s_res_def")
        s_mentor = st.checkbox("Наставничество", key="s_mentor")
        s_proactive = st.checkbox("Проактивность", value=True, key="s_proactive")

    with tab_hard:
        st.caption("Цифровой стек, автоматизация, базы данных и финансы")
        h_pc = st.checkbox("Уверенный пользователь ПК и планшетов", key="h_pc")
        h_abs = st.checkbox("Работа в банковских АБС / СУБД / CRM-системах", key="h_abs")
        h_excel = st.checkbox("Продвинутый Excel (ВПР, Сводные таблицы, Макросы)", key="h_excel")
        h_python = st.checkbox("Автоматизация процессов на Python (Pandas / Скрипты)", key="h_python")
        h_sql = st.checkbox("Написание сложных SQL-запросов (JOIN / Выгрузки)", key="h_sql")
        h_bi = st.checkbox("BI-аналитика и построение дашбордов (PowerBI / Tableau)", key="h_bi")
        h_eda = st.checkbox("Разведочный анализ данных (EDA / Jupyter Notebook)", key="h_eda")
        h_pred = st.checkbox("Прогнозное моделирование и ML (скоринг / классификация)", key="h_pred")
        h_java = st.checkbox("Промышленная Backend-разработка на Java (Spring Boot)", key="h_java")
        h_devops = st.checkbox("DevOps инфраструктура и CI/CD пайплайны (Docker / k8s)", key="h_devops")
        h_bigdata = st.checkbox("Стек Больших Данных (Hadoop / Spark / Hive / Kafka)", key="h_bigdata")
        h_cfa = st.checkbox("Международная сертификация CFA (уровни)", key="h_cfa")
        h_frm = st.checkbox("Сертификат по управлению рисками FRM", key="h_frm")
        h_fsfr = st.checkbox("Квалификационный аттестат ЦБ РФ (ФСФР)", key="h_fsfr")

    with tab_biz:
        st.caption("Управление эффективностью, метрики, комплаенс и ВНД")
        b_kpi_mgmt = st.checkbox("Выставление и трекинг задач (Jira / Confluence / OKR)", key="b_kpi_mgmt")
        b_kpi_trouble = st.checkbox("Траблшутинг воронок и поиск узких мест", key="b_kpi_trouble")
        b_sales_book = st.checkbox("Работа по Книге продаж / Анализ конкурентов", key="b_sales_book")
        b_res_def_data = st.checkbox("Защита результатов на основе данных (Data-driven)", key="b_res_def_data")
        b_roleplay = st.checkbox("Успешное прохождение ролевых игр", key="b_roleplay")
        b_field_adapt = st.checkbox("Знание нормативных документов", key="b_field_adapt")
        b_learning = st.checkbox("Прохождение внутренних аттестаций", key="b_learning")
        b_pnl = st.checkbox("Управление P&L / Бюджетирование / Unit-экономика / Метрики", key="b_pnl")
        b_basel = st.checkbox("Управление рисками", key="b_basel")
        b_compliance = st.checkbox("Комплаенс (115-ФЗ / AML / KYC / Валютный контроль)", key="b_compliance")
        b_hr = st.checkbox("Управление человеческим капиталом и HR-аналитика", key="b_hr")

    with tab_infra:
        st.caption("Образование, наличие автомобиля, формат работы")
        i_edu = st.checkbox("Высшее профильное / Техническое образование (ведущие вузы)", value=True, key="i_edu")
        i_car = st.checkbox("Наличие личного автомобиля и водительских прав категории B", key="i_car")
        i_remote = st.checkbox("Предпочтение удаленного или гибридного формата работы", key="i_remote")

st.write("---")

# Финальный запуск асинхронного расчета
if st.button("Запустить комплексный расчет оффера кандидата", type="primary"):
    # Формируем полный payload, передавая 100% признаков в FastAPI бэкенд
    payload = {
        "role_class": role_id,
        "experience_months": experience,
        "region_tier": region_tier,
        "bank_tier": bank_tier,
        "skills_completion_rate": 0.084,  # Дефолт, воркер пересчитает по тексту
        
        # Передаем все верифицированные на интервью бинарные флаги
        "skill_general_negotiations": s_gen_neg, "skill_vip_negotiations": s_vip_neg,
        "skill_active_listening": s_act_list, "skill_persuasion_argumentation": s_persuasion,
        "skill_public_presentation": s_public, "skill_business_correspondence": s_correspondence,
        "skill_cold_sales": s_cold, "skill_telemarketing": s_tele,
        "skill_objection_handling": s_objection, "skill_cross_sales": s_cross,
        "skill_difficult_clients": s_diff_cli, "skill_conflict_resolution": s_conflict,
        "skill_stress_resistance": s_stress, "skill_adaptability_flexibility": s_adapt,
        "skill_teamwork": s_team, "skill_result_defense": s_res_def,
        "skill_mentoring_coaching": s_mentor, "skill_initiative_proactivity": s_proactive,
        
        "skill_pc_tablet_advanced": h_pc, "skill_abs_crm": h_abs,
        "skill_advanced_excel": h_excel, "skill_python_automation": h_python,
        "skill_sql_queries": h_sql, "skill_bi_analytics": h_bi,
        "skill_business_eda": h_eda, "skill_predictive_modeling": h_pred,
        "skill_java_backend": h_java, "skill_devops_cicd": h_devops,
        "skill_big_data_stack": h_bigdata, "skill_finance_cert_cfa": h_cfa,
        "skill_finance_cert_frm": h_frm, "skill_finance_cert_fsfr": h_fsfr,
        
        "skill_kpi_system_management": b_kpi_mgmt, "skill_kpi_troubleshooting_eda": b_kpi_trouble,
        "skill_sales_book_analysis": b_sales_book, "skill_result_defense_data": b_res_def_data,
        "skill_roleplay_defense": b_roleplay, "skill_dynamic_field_adaptation": b_field_adapt,
        "skill_rapid_learning_testing": b_learning, "skill_pnl_product_metrics": b_pnl,
        "skill_banking_regulation_basel": b_basel, "skill_compliance_aml_kyc": b_compliance,
        "skill_hr_analytics_metrics": b_hr,
        
        # Интегрируем группу социальные триггеры строго по именам колонок матрицы X
        "edu_level_encoded": i_edu,
        "has_car_and_driver_license": i_car,
        "has_remote_hybrid_schedule": i_remote,
        
        "raw_text": raw_resume_text  # Передаем сырой текст резюме для BERT + PCA + Regex парсинга
    }

    start_time = time.time()
    try:
        res = requests.post(f"{BACKEND_URL}/predict", json=payload).json()
        task_id = res["task_id"]
        
        with st.spinner("Воркеры Celery анализируют резюме через RuBERT и рассчитывают оклад в XGBoost..."):
            while True:
                status_res = requests.get(f"{BACKEND_URL}/predict/status/{task_id}").json()
                if status_res["status"] == "SUCCESS":
                    offer = status_res["predicted_offer"]
                    break
                elif status_res["status"] == "FAILURE":
                    st.error("Критический сбой воркера при инференсе модели!")
                    st.stop()
                time.sleep(0.4)
        
        calc_time = time.time() - start_time
        st.success(f"Рекомендованный рыночный оффер: {int(offer):,} рублей".replace(',', ' '))
        st.info(f"Скорость расчета (Time to Offer): {calc_time:.2f} сек. (Целевой b2b-лимит: ≤ 10 минут)")
        
        st.session_state["pred_id"] = status_res["id"]
    except Exception as e:
        st.error(f"Не удалось связаться с микросервисной архитектурой: {e}")

# Блок сбора обратной связи для расчета Acceptance Rate
# Блок сбора обратной связи для расчета Acceptance Rate
if "pred_id" in st.session_state:
    st.subheader("Оценка качества подсказки (Мониторинг Acceptance Rate)")
    
    # Проверяем, не отправлен ли фидбек уже в рамках этой сессии
    if st.session_state.get("feedback_submitted"):
        st.success("Решение успешно залогировано для мониторинга продуктовой эффективности MVP")
        if st.button("Оценить нового кандидата"):
            # Очищаем состояния для следующего расчета
            del st.session_state["pred_id"]
            st.session_state["feedback_submitted"] = False
            st.rerun()
    else:
        with st.form("feedback_form"):
            accepted = st.radio(
                "Согласны ли вы и нанимающий менеджер с предложенной ставкой?", 
                ["Да, оффер утвержден и отправлен кандидату", "Нет, ставка отклонена бизнесом"]
            )
            actual_val = st.number_input(
                "Итоговый согласованный оклад (если отличается от ИИ-рекомендации):", 
                min_value=0, 
                value=0
            )
            
            if st.form_submit_button("Зафиксировать решение в СУБД"):
                fb_payload = {
                    "prediction_id": st.session_state["pred_id"],
                    "hr_accepted": True if "Да" in accepted else False,
                    "actual_salary": float(actual_val) if actual_val > 0 else None
                }
                
                try:
                    response = requests.post(f"{BACKEND_URL}/feedback", json=fb_payload, timeout=10)
                    
                    if response.status_code in [200, 201]:
                        # Помечаем, что фидбек отправлен, чтобы переключить интерфейс
                        st.session_state["feedback_submitted"] = True
                        st.rerun()
                    else:
                        st.error(f"Бэкенд не смог сохранить фидбек (Код {response.status_code}): {response.text}")
                
                except requests.exceptions.RequestException as e:
                    st.error(f"Ошибка соединения при отправке фидбека: {e}")