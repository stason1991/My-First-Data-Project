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
INPUT_DIR = "hh_pages"
OUTPUT_INTERIM = "data_interim_vacancies.csv"

# Объединяем все текстовые блоки навыков для сквозного поиска в карточке
ALL_TEXT_SKILLS = {}
ALL_TEXT_SKILLS.update(SOFT_SKILLS_TRIGGERS)
ALL_TEXT_SKILLS.update(HARD_SKILLS_TRIGGERS)
ALL_TEXT_SKILLS.update(BUSINESS_SKILLS_TRIGGERS)

def parse_html_experience(text):
    """
    Переводит стандартные текстовые требования к опыту из верстки hh в месяцы.
    Примеры: 'Без опыта' -> 0, 'Опыт 1–3 года' -> 24, 'Опыт 3–6 лет' -> 54
    """
    text = text.lower().strip()
    if "нет опыта" in text or "без опыта" in text: 
        return 0
    if "1–3 года" in text or "1 года" in text or "3 лет" in text and "1–3" in text: 
        return 24  # Среднее между 12 и 36 месяцами
    if "3–6 лет" in text or "3 лет" in text or "6 лет" in text and "3–6" in text: 
        return 54  # Среднее между 36 и 72 месяцами
    if "более 6 лет" in text or "6 лет" in text: 
        return 96  # Условные 8 лет стажа для ветеранов
    return 0

def parse_html_salary(salary_text):
    """
    Парсит текстовую строку зарплаты ('от 100 000 руб.', '150 000 – 200 000 руб.').
    Реализует валютный контроль (только рубли) и возвращает (от, до, валюта).
    """
    if not salary_text or "не указана" in salary_text.lower():
        return None, None, None
    
    # Очищаем строку от пробелов и неразрывных отступов
    text = salary_text.replace("\u202f", "").replace("\xa0", "").replace(" ", "").lower()
    
    # Валютный контроль: работаем строго с рублевыми позициями
    if not any(curr in text for curr in ["руб", "rur", "rub", "₽"]):
        return None, None, None
        
    nums = [float(n) for n in re.findall(r'\d+', text)]
    if not nums:
        return None, None, None
        
    if "от" in text and len(nums) == 1:
        return nums[0], None, "RUR"
    elif "до" in text and len(nums) == 1:
        return None, nums[0], "RUR"
    elif len(nums) >= 2:
        return nums[0], nums[1], "RUR"
    elif len(nums) == 1:
        return nums[0], nums[0], "RUR"
    return None, None, None

def determine_role_class(title_text):
    """Определяет класс должности по названию вакансии строго от 1 до 20."""
    title_lower = title_text.lower().strip()
    for role_id, pattern in ROLE_PATTERNS.items():
        if re.search(pattern, title_lower):
            return role_id
    return 8  # По умолчанию отправляем в массовый класс (Менеджер по продажам Фронт)

def determine_region_tier(geo_text):
    """Категоризирует регион размещения вакансии по уровням Tier."""
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
    print("[ОФФЛАЙН ПАРСЕР] Запуск сквозной обработки папки вакансий...")
    
    if not os.path.exists(INPUT_DIR):
        print(f"[ОШИБКА] Директория '{INPUT_DIR}' не найдена! Проверьте, где сохранены HTML.")
        exit(1)
        
    dataset = []
    files = [f for f in os.listdir(INPUT_DIR) if f.endswith('.html')]
    print(f" Найдено файлов для анализа: {len(files)}")

    for file_name in sorted(files):
        file_path = os.path.join(INPUT_DIR, file_name)
        print(f" -> Обработка HTML-страницы выдачи вакансий: {file_name}")
        
        with open(file_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "html.parser")
            
        # Находим карточки вакансий (используем стандартные классы и qa-атрибуты выдачи hh)
        cards = soup.find_all(attrs={"data-qa": "vacancy-serp__vacancy"})
        if not cards:
            cards = soup.find_all(class_=re.compile("vacancy-serp-item|serp-item"))
            
        for card in cards:
            # 1. Извлекаем название вакансии
            title_el = card.find(attrs={"data-qa": "vacancy-serp__vacancy-title"}) or card.find(class_=re.compile("title"))
            title = title_el.text.strip() if title_el else "Не указано"
            
            # 2. Извлекаем строку зарплаты
            salary_el = card.find(attrs={"data-qa": "vacancy-serp__vacancy-compensation"}) or card.find(class_=re.compile("compensation|salary"))
            salary_text = salary_el.text.strip() if salary_el else ""
            s_from, s_to, currency = parse_html_salary(salary_text)
            
            # 3. Извлекаем требование к опыту
            exp_el = card.find(attrs={"data-qa": "vacancy-serp__vacancy-work-experience"}) or card.find(class_=re.compile("experience"))
            exp_text = exp_el.text.strip() if exp_el else ""
            experience_months = parse_html_experience(exp_text)
            
            # 4. Извлекаем географию / адрес
            geo_el = card.find(attrs={"data-qa": "vacancy-serp__vacancy-address"}) or card.find(class_=re.compile("address|area"))
            geo_text = geo_el.text.strip() if geo_el else ""
            region_tier = determine_region_tier(geo_text)
            
            # Приводим весь текст текущей карточки вакансии к нижнему регистру для поиска ключевых слов
            card_text_lower = card.text.lower()
            
            # Определение класса должности (1-20)
            role_class = determine_role_class(title)
            
            # Собираем структуру строки датасета для вакансии
            row = {
                "role_name_raw": title,
                "role_class": role_class,
                "experience_months": experience_months,
                "region_tier": region_tier,
                "salary_from": s_from,
                "salary_to": s_to,
                "is_vacancy": 1       # Важный маркер: это объявление работодателя
            }
            
            # 5. Размечаем 33 текстовых бинарных флага (Soft + Hard + Business)
            skill_flags = check_text_patterns(card_text_lower, ALL_TEXT_SKILLS)
            row.update(skill_flags)
            
            # Считаем плотность заполнения навыков для модели
            skill_cols = list(ALL_TEXT_SKILLS.keys())
            row['skills_completion_rate'] = sum(row[s] for s in skill_cols) / len(skill_cols)
            
            # 6. Размечаем социальные маркеры (используются как дефолты 0/1 для вакансий, если они упомянуты в требованиях)
            social_flags = check_text_patterns(card_text_lower, SOCIAL_INFRA_TRIGGERS)
            row.update(social_flags)
            
            dataset.append(row)

    # Сохраняем промежуточный датасет вакансий
    df_vacancies = pd.DataFrame(dataset)
    df_vacancies.to_csv(OUTPUT_INTERIM, index=False, encoding='utf-8-sig')
    print("\n" + "="*50)
    print(f"[УСПЕХ] Модуль parse_html_vacancies завершил работу.")
    print(f"Всего извлечено вакансий от работодателей: {len(df_vacancies)} строк.")
    print(f"Данные сохранены в промежуточный файл: {OUTPUT_INTERIM}")
    print("="*50)