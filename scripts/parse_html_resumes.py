import os
import re
import pandas as pd
from bs4 import BeautifulSoup

# Импортируем укомплектованные словари из вашего общего модуля
from skills_vocabulary import (
    ROLE_PATTERNS, 
    SOFT_SKILLS_TRIGGERS, 
    HARD_SKILLS_TRIGGERS, 
    BUSINESS_SKILLS_TRIGGERS,
    SOCIAL_INFRA_TRIGGERS
)

# Настройки путей и файлов
INPUT_DIR = "hh_resumes"
OUTPUT_INTERIM = "data_interim_resumes.csv"

# Объединяем все текстовые блоки навыков для сквозного поиска в карточке
ALL_TEXT_SKILLS = {}
ALL_TEXT_SKILLS.update(SOFT_SKILLS_TRIGGERS)
ALL_TEXT_SKILLS.update(HARD_SKILLS_TRIGGERS)
ALL_TEXT_SKILLS.update(BUSINESS_SKILLS_TRIGGERS)

def parse_resume_experience(exp_text):
    """
    Извлекает текстовый опыт из карточки кандидата вида:
    'Опыт работы 5 лет и 3 месяца' или 'Опыт работы 8 месяцев'
    и переводит его в чистое количество месяцев.
    """
    if not exp_text:
        return 0
    
    text = exp_text.lower().replace("\u202f", "").replace("\xa0", "")
    
    # Ищем упоминания лет (лет, года, год)
    years_match = re.search(r'(\d+)\s*(?:лет|года|год)', text)
    # Ищем упоминания месяцев (месяцев, месяца, месяц)
    months_match = re.search(r'(\d+)\s*(?:месяц|месяцев|месяца)', text)
    
    years = int(years_match.group(1)) if years_match else 0
    months = int(months_match.group(1)) if months_match else 0
    
    return (years * 12) + months

def determine_role_class(title_text):
    """Определяет класс должности соискателя строго от 1 до 20."""
    title_lower = title_text.lower().strip()
    for role_id, pattern in ROLE_PATTERNS.items():
        if re.search(pattern, title_lower):
            return role_id
    return 8  # По умолчанию отправляем в самый массовый класс фронт-линии

def determine_region_tier(geo_text):
    """Категоризирует регион проживания кандидата."""
    if not geo_text:
        return 'Tier-3'
    geo_lower = geo_text.lower().strip()
    if 'москва' in geo_lower or 'санкт-петербург' in geo_lower:
        return 'Tier-1'
        
    million_cities = [
        'новосибирск', 'екатеринбург', 'казань', 'нижний новгород', 'красноярск', 
        'челябинск', 'самара', 'уфа', 'ростов-на-дону', 'краснодар', 'пермь', 'волгоград'
    ]
    for city in million_cities:
        if city in geo_lower:
            return 'Tier-2'
    return 'Tier-3'

def check_text_patterns(text, triggers_dict):
    """Проверяет массив регулярных выражений на совпадение с текстом карточки."""
    flags = {}
    for skill_name, patterns in triggers_dict.items():
        has_skill = 0
        for pattern in patterns:
            if re.search(pattern, text):
                has_skill = 1
                break
        flags[skill_name] = has_skill
    return flags

if __name__ == "__main__":
    print("[ОФФЛАЙН ПАРСЕР] Запуск сквозной обработки папки резюме...")
    
    if not os.path.exists(INPUT_DIR):
        print(f"[ОШИБКА] Директория '{INPUT_DIR}' не найдена! Проверьте, завершился ли сбор.")
        exit(1)
        
    dataset = []
    files = [f for f in os.listdir(INPUT_DIR) if f.endswith('.html')]
    print(f" Найдено файлов для анализа: {len(files)}")

    for file_name in sorted(files):
        file_path = os.path.join(INPUT_DIR, file_name)
        print(f" -> Обработка HTML-страницы выдачи резюме: {file_name}")
        
        with open(file_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "html.parser")
            
        # Находим карточки резюме на странице (используем стандартные классы и qa-атрибуты выдачи hh)
        cards = soup.find_all(attrs={"data-qa": "resume-serp__resume"})
        if not cards:
            cards = soup.find_all(class_=re.compile("resume-search-item|serp-item"))
            
        for card in cards:
            # 1. Извлекаем желаемую должность кандидата
            title_el = card.find(attrs={"data-qa": "resume-serp__resume-title"}) or card.find(class_=re.compile("title"))
            title = title_el.text.strip() if title_el else "Не указано"
            
            # 2. Извлекаем стаж работы одной текстовой строкой
            exp_el = card.find(attrs={"data-qa": "resume-serp__resume-excavation"}) or card.find(class_=re.compile("experience"))
            exp_text = exp_el.text.strip() if exp_el else ""
            experience_months = parse_resume_experience(exp_text)
            
            # 3. Извлекаем географический регион
            geo_el = card.find(attrs={"data-qa": "resume-serp__resume-address"}) or card.find(class_=re.compile("address"))
            geo_text = geo_el.text.strip() if geo_el else ""
            region_tier = determine_region_tier(geo_text)
            
            # Приводим весь текст текущей карточки к нижнему регистру для разметки флагов
            card_text_lower = card.text.lower()
            
            # Определение класса должности (1-20)
            role_class = determine_role_class(title)
            
            # Собираем базовый профиль соискателя
            row = {
                "role_name_raw": title,
                "role_class": role_class,
                "experience_months": experience_months,
                "region_tier": region_tier,
                "salary_from": None,  # В выдаче резюме вилки часто скрыты, заполним средним на шаге слияния
                "salary_to": None,
                "is_vacancy": 0       # Важный маркер: это профиль кандидата, а не объявление работодателя
            }
            
            # 4. Размечаем 33 текстовых бинарных флага (Soft + Hard + Business)
            skill_flags = check_text_patterns(card_text_lower, ALL_TEXT_SKILLS)
            row.update(skill_flags)
            
            # Считаем плотность заполнения навыков для модели
            skill_cols = list(ALL_TEXT_SKILLS.keys())
            row['skills_completion_rate'] = sum(row[s] for s in skill_cols) / len(skill_cols)
            
            # 5. Размечаем социальные и инфраструктурные маркеры соискателя из Блока 5
            social_flags = check_text_patterns(card_text_lower, SOCIAL_INFRA_TRIGGERS)
            row.update(social_flags)
            
            dataset.append(row)

    # Сохраняем промежуточный датасет
    df_resumes = pd.DataFrame(dataset)
    df_resumes.to_csv(OUTPUT_INTERIM, index=False, encoding='utf-8-sig')
    print("\n" + "="*50)
    print(f"[УСПЕХ] Модуль parse_html_resumes завершил работу.")
    print(f"Всего извлечено анкет кандидатов: {len(df_resumes)} строк.")
    print(f"Данные сохранены в промежуточный файл: {OUTPUT_INTERIM}")
    print("="*50)