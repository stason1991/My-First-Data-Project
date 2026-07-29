import streamlit as st
import requests
import time
import pandas as pd
import json
import altair as alt

# Настройка визуального пространства jupyter-подобного веб-интерфейса
st.set_page_config(page_title="AI Talent Hub Salary Calc", layout="wide", initial_sidebar_state="expanded")

st.title("Интеллектуальная система оценки кандидатов и прогноза зарплатного оффера")
st.caption("Микросервисный контур: FastAPI + Celery + PostgreSQL | Модель: XGBoost (XAI SHAP Top-25)")

# Базовый URL микросервисного бэкенда FastAPI
BACKEND_URL = "http://salary_fastapi_backend:8000/api/v1"

# 16 Репрезентативных базовых классов должностей банковской сферы из EDA
ROLES = {
    1: "Представители банка / Мобильные менеджеры / Доставка карт",
    2: "Прямые продажи / DSA",
    6: "Операционисты / Сервис-менеджеры",
    7: "Кассиры",
    8: "Менеджер по продажам розничного блока",
    9: "Главный менеджер по продажам розничного блока",
    11: "Персональный менеджер VIP / Private / Привилегия",
    13: "Менеджер по обслуживанию юридических лиц",
    14: "Руководитель блока юридических лиц",
    15: "Ипотечный менеджер",
    20: "Руководитель дополнительного офиса",
    21: "Data Scientist / ML Engineer",
    23: "Промышленная Backend-разработка на Java",
    24: "Системный аналитик",
    25: "DevOps Engineer",
    31: "HR-менеджер",
}

# Мэппинг текстовых опций интерфейса в те значения (числа и строки), которые ожидает воркер
REGION_MAPPING = {
    "Москва/Санкт-Петербург": 1,
    "Города миллионники": 2,
    "Все прочие населенные пункты": 3,
    "Зарубежье": 4,
}

BANK_MAPPING = {
    "Крупнейшие системообразующие банки": "Bank_Tier_1",
    "Крупные региональные банки": "Bank_Tier_2",
    "Все прочие банки": "Bank_Tier_3",
}

# Разделение экрана на две рабочие колонки
col1, col2 = st.columns(2)

with col1:
    st.subheader("Паспорт кандидата и резюме")

    # Селектбокс роли с выводом понятного b2b-текста
    role_id = st.selectbox(
        "Целевая роль в банке (Класс):", options=list(ROLES.keys()), format_func=lambda x: f"Класс {x:02d} — {ROLES[x]}"
    )

    experience = st.slider("Подтвержденный стаж работы (в месяцах):", 0, 120, 24)

    region_ui = st.selectbox("Регион найма (Локация):", list(REGION_MAPPING.keys()))
    bank_ui = st.selectbox("Уровень бренда текущей финансовой организации:", list(BANK_MAPPING.keys()))

    # Синхронизация типов данных: конвертируем UI-выбор в строгое представление для СУБД/модели
    region_tier = REGION_MAPPING[region_ui]
    bank_tier = BANK_MAPPING[bank_ui]

    # Интерфейс ручной верификации квалификационного грейда
    st.write("**Квалификационный грейд кандидата:**")
    cg1, cg2 = st.columns(2)
    with cg1:
        g_junior = st.checkbox("Junior", key="g_junior")
        g_middle = st.checkbox("Middle", value=True, key="g_middle")  # Пресет нормы
    with cg2:
        g_senior = st.checkbox("Senior", key="g_senior")
        g_mgmt = st.checkbox("Management / Руководитель", key="g_mgmt")

    # Тестовое резюме со встроенными маркерами под регулярные выражения воркера
    raw_resume_text = st.text_area(
        "Скопируйте сюда полный текст резюме соискателя (опыт, обязанности, навыки):",
        value=(
            "Опыт работы в Сбере 4 года. Продажи в зале, консультирование клиентов по банковским продуктам, "
            "продажи в должности менеджера по продажам. Выполнение планов на 100%. Опыт работы в Альфа-банке "
            "в выездном канале 1,5 года. Выезды к клиентам на личном автомобиле, выполнение планов продаж. "
            "Опыт работы в ВТБ 4 года. Из них 6 месяцев DSA, выезды в организации, проведение презентаций, "
            "проведение переговоров с первыми лицами, холодные продажи на телефоне кредитных продуктов. "
            "Год в роли клиенсткого менеджера, продажи на фронт-линии, выполнение планов на 120%, непрерывное "
            "обучение и командная работа. Повышен до главного клиенсткого менеджера, в этой должности работаю "
            "почти 2 года. Помимо продаж инвестиционных продуктов, составляю отчетность для руководителя, "
            "анализирую результаты."
        ),
        height=300,
    )

with col2:
    st.subheader("Верификация компетенций на интервью")
    st.write("Отметьте навыки, которые кандидат подтвердил на технических и софт-собеседованиях:")

    # Распределяем все навыки по четырем логическим b2b-вкладкам
    tab_soft, tab_hard, tab_biz, tab_infra = st.tabs(
        ["Soft Skills", "Hard Skills", "Business Skills", "Higher education / Own vehicle / Work format"]
    )

    with tab_soft:
        st.caption("Мягкие навыки")
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
        st.caption("Технические навыки")
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
        h_cfa = st.checkbox("Международная сертификация CFA", key="h_cfa")
        h_frm = st.checkbox("Сертификат по управлению рисками FRM", key="h_frm")
        h_fsfr = st.checkbox("Квалификационный аттестат ЦБ РФ (ФСФР)", key="h_fsfr")

    with tab_biz:
        st.caption("Бизнес навыки")
        b_kpi_mgmt = st.checkbox("Управление через Jira/Confluence/OKR", key="b_kpi_mgmt")
        b_kpi_trouble = st.checkbox("Анализ воронок продаж и бизнес-метрик", key="b_kpi_trouble")
        b_sales_book = st.checkbox("Анализ конкурентной среды рынка", key="b_sales_book")
        b_res_def_data = st.checkbox("Защита результатов работы на основе данных", key="b_res_def_data")
        b_roleplay = st.checkbox("Успешное прохождение бизнес-ролевых игр", key="b_roleplay")
        b_field_adapt = st.checkbox("Знание базовых нормативных документов ЦБ", key="b_field_adapt")
        b_learning = st.checkbox("Прохождение внутренних аттестаций и тестов", key="b_learning")
        b_pnl = st.checkbox("Управление P&L / Бюджетирование / Unit-экономика", key="b_pnl")
        b_basel = st.checkbox("Управление рисками в рамках Базель III", key="b_basel")
        b_compliance = st.checkbox("Комплаенс-контроль / ПОД/ФТ", key="b_compliance")
        b_hr = st.checkbox("Управление человеческим капиталом и HR-аналитика", key="b_hr")

    with tab_infra:
        st.caption("Образование/наличие автомобиля/формат работы")
        i_edu = st.checkbox("Высшее профильное / Техническое или экономическое образование", value=True, key="i_edu")
        i_car = st.checkbox("Наличие личного автомобиля и водительских прав категории B", key="i_car")
        i_remote = st.checkbox("Предпочтение удаленного или гибридного формата работы", key="i_remote")

st.write("---")

# Финальный запуск асинхронного расчета
# Финальный запуск асинхронного расчета
if st.button("Запустить комплексный расчет оффера кандидата", type="primary"):
    # Сборка payload строго в соответствии со спецификацией PredictionRequest
    payload = {
        "role_class": int(role_id),
        "experience_months": int(experience),
        "region_tier": int(region_tier),
        "bank_tier": str(bank_tier),
        "skills_completion_rate": 0.084,  # Воркер перезапишет по факту разбора словаря
        "is_grade_junior": bool(g_junior),
        "is_grade_middle": bool(g_middle),
        "is_grade_senior": bool(g_senior),
        "is_grade_management": bool(g_mgmt),
        "skill_general_negotiations": bool(s_gen_neg),
        "skill_vip_negotiations": bool(s_vip_neg),
        "skill_active_listening": bool(s_act_list),
        "skill_persuasion_argumentation": bool(s_persuasion),
        "skill_public_presentation": bool(s_public),
        "skill_business_correspondence": bool(s_correspondence),
        "skill_cold_sales": bool(s_cold),
        "skill_telemarketing": bool(s_tele),
        "skill_objection_handling": bool(s_objection),
        "skill_cross_sales": bool(s_cross),
        "skill_difficult_clients": bool(s_diff_cli),
        "skill_conflict_resolution": bool(s_conflict),
        "skill_stress_resistance": bool(s_stress),
        "skill_adaptability_flexibility": bool(s_adapt),
        "skill_teamwork": bool(s_team),
        "skill_result_defense": bool(s_res_def),
        "skill_mentoring_coaching": bool(s_mentor),
        "skill_initiative_proactivity": bool(s_proactive),
        "skill_pc_tablet_advanced": bool(h_pc),
        "skill_abs_crm": bool(h_abs),
        "skill_advanced_excel": bool(h_excel),
        "skill_python_automation": bool(h_python),
        "skill_sql_queries": bool(h_sql),
        "skill_bi_analytics": bool(h_bi),
        "skill_business_eda": bool(h_eda),
        "skill_predictive_modeling": bool(h_pred),
        "skill_java_backend": bool(h_java),
        "skill_devops_cicd": bool(h_devops),
        "skill_big_data_stack": bool(h_bigdata),
        "skill_finance_cert_cfa": bool(h_cfa),
        "skill_finance_cert_frm": bool(h_frm),
        "skill_finance_cert_fsfr": bool(h_fsfr),
        "skill_kpi_system_management": bool(b_kpi_mgmt),
        "skill_kpi_troubleshooting_eda": bool(b_kpi_trouble),
        "skill_sales_book_analysis": bool(b_sales_book),
        "skill_result_defense_data": bool(b_res_def_data),
        "skill_roleplay_defense": bool(b_roleplay),
        "skill_dynamic_field_adaptation": bool(b_field_adapt),
        "skill_rapid_learning_testing": bool(b_learning),
        "skill_pnl_product_metrics": bool(b_pnl),
        "skill_banking_regulation_basel": bool(b_basel),
        "skill_compliance_aml_kyc": bool(b_compliance),
        "skill_hr_analytics_metrics": bool(b_hr),
        "edu_level_encoded": bool(i_edu),
        "has_car_and_driver_license": bool(i_car),
        "has_remote_hybrid_schedule": bool(i_remote),
        "raw_text": raw_resume_text,
    }

    start_time = time.time()
    try:
        # Отправка POST-запроса на бэкенд для постановки задачи в очередь Celery
        res = requests.post(f"{BACKEND_URL}/predict", json=payload).json()
        task_id = res["task_id"]

        explanation_data = {}
        offer = 0
        status_res = {}

        with st.spinner("Воркеры Celery анализируют резюме через RuBERT и рассчитывают оклад в XGBoost..."):
            while True:
                status_res = requests.get(f"{BACKEND_URL}/predict/status/{task_id}").json()
                if status_res["status"] == "SUCCESS":
                    offer = status_res["predicted_offer"]

                    # Извлекаем сырые данные SHAP
                    raw_shap = status_res.get("explanation_json")

                    if raw_shap:
                        # Если это строка, принудительно декодируем её в словарь Python
                        if isinstance(raw_shap, str):
                            try:
                                explanation_data = json.loads(raw_shap)
                                # Если строка была дважды экранирована (такое бывает в FastAPI/PostgreSQL),
                                # парсим её ещё раз, пока она не станет словарём
                                if isinstance(explanation_data, str):
                                    explanation_data = json.loads(explanation_data)
                            except Exception:
                                explanation_data = {}
                        else:
                            explanation_data = raw_shap
                    break
                elif status_res["status"] == "FAILURE":
                    st.error("Критический сбой воркера при инференсе модели!")
                    st.stop()
                time.sleep(0.4)

        calc_time = time.time() - start_time

        # Вывод результатов точечного прогноза
        st.success(f"Рекомендованный рыночный оффер: {int(offer):,} рублей".replace(",", " "))
        st.caption(f"Скорость расчета (Time to Offer): {calc_time:.2f} сек. (Целевой b2b-лимит: ≤ 10 минут)")

        # Фиксируем id транзакции в сессии для формы фидбека и запоминаем сумму оффера
        st.session_state["pred_id"] = status_res.get("id") or status_res.get("prediction_id")
        st.session_state["current_offer"] = int(offer)

        # Проверяем, что пришли реальные вклады фичей, а не текстовые заглушки INFO/WARNING
        has_valid_shap = (
            explanation_data
            and isinstance(explanation_data, dict)
            and "INFO" not in explanation_data
            and "WARNING" not in explanation_data
        )

        # Отрисовка ТОп-25 признаков
        if has_valid_shap:
            st.write("---")
            st.subheader("Объяснение прогноза: ТОП-25 факторов ценообразования (XAI SHAP)")
            st.markdown(
                "График показывает, на сколько рублей конкретный навык или параметр **изменил базовую рыночную стоимость** должности."
            )

            # Конвертируем словарь SHAP-вкладов в DataFrame с латинскими ключами
            shap_rows = [{"feature": str(k), "value": float(v)} for k, v in explanation_data.items()]
            df_shap = pd.DataFrame(shap_rows)

            # Выделяем до 25 самых сильных признаков (сортировка по модулю)
            df_shap["abs_val"] = df_shap["value"].abs()
            df_shap = df_shap.sort_values(by="abs_val", ascending=False).head(25)

            # Разворачиваем для красивого отображения сверху вниз (сильные вверху)
            df_shap = df_shap.iloc[::-1].reset_index(drop=True)

            # Маркер цвета: Зеленый для позитивного влияния, Красный — для негативного
            df_shap["Влияние"] = df_shap["value"].apply(
                lambda x: "Положительное (+)" if x >= 0 else "Отрицательное (-)"
            )

            # Построение кастомизированной диаграммы Altair на латинских осях с русскими тайтлами
            chart = (
                alt.Chart(df_shap)
                .mark_bar()
                .encode(
                    x=alt.X("value:Q", title="Вклад в рублевый эквивалент оклада (руб.)"),
                    y=alt.Y("feature:N", sort=None, title="Идентификатор навыка / признака"),
                    color=alt.Color(
                        "Влияние:N",
                        scale=alt.Scale(
                            domain=["Положительное (+)", "Отрицательное (-)"], range=["#2ecc71", "#e74c3c"]
                        ),
                    ),
                    tooltip=[
                        alt.Tooltip("feature:N", title="Фактор / Компетенция"),
                        alt.Tooltip("value:Q", title="Вклад в оффер (руб.)", format=",.0f"),
                    ],
                )
                .properties(height=400)
            )  # Динамическая b2b высота под текущий набор фичей

            st.altair_chart(chart, use_container_width=True)

            # Текстовый реестр вкладов (переименовываем колонки обратно в кириллицу специально для рекрутера)
            with st.expander("Посмотреть текстовый реестр вкладов всех факторов"):
                df_readable = df_shap.copy().drop(columns=["abs_val"])
                df_readable.columns = ["Фактор / Компетенция", "Вклад в оффер (руб.)", "Влияние"]
                st.dataframe(
                    df_readable.sort_values(by="Вклад в оффер (руб.)", ascending=False).reset_index(drop=True),
                    use_container_width=True,
                )
        else:
            st.warning("Внимание: Данные SHAP недоступны для этой транзакции.")

    except Exception as e:
        st.error(f"Не удалось связаться с микросервисной архитектурой: {e}")

# Блок обратной связи
# Блок находится вне условия нажатия кнопки, чтобы оставаться на экране после перезагрузки
if "pred_id" in st.session_state:
    st.write("---")
    st.subheader("Оценка качества подсказки (Мониторинг Acceptance Rate)")

    # Проверяем, не отправлен ли фидбек уже в рамках текущей сессии оценки
    if st.session_state.get("feedback_submitted"):
        st.success("Решение успешно залогировано для мониторинга продуктовой эффективности MVP")
        if st.button("Оценить нового кандидата"):
            # Очищаем состояния сессии для подготовки к следующему расчету
            del st.session_state["pred_id"]
            if "current_offer" in st.session_state:
                del st.session_state["current_offer"]
            st.session_state["feedback_submitted"] = False
            st.rerun()
    else:
        # Обязательная инкапсуляция элементов ввода внутри st.form
        with st.form("feedback_form"):
            accepted_ui = st.radio(
                "Согласны ли вы и нанимающий менеджер с предложенной ставкой?",
                ["Да, оффер утвержден и отправлен кандидату", "Нет, ставка отклонена бизнесом"],
            )

            # Подтягиваем предсказанный оклад из сессии как дефолтное значение для удобства рекрутера
            default_val = st.session_state.get("current_offer", 0)

            actual_val = st.number_input(
                "Итоговый согласованный оклад (если отличается от ИИ-рекомендации):",
                min_value=0,
                value=int(default_val),
                step=5000,
            )

            # Добавлена триггерная кнопка отправки формы на бэкенд
            submit_feedback = st.form_submit_button("Отправить фидбек в систему мониторинга")
