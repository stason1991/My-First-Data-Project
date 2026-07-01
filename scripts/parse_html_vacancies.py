import os
import sys
import re
import pandas as pd
from bs4 import BeautifulSoup

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from skills_vocabulary import (
        TARGET_ROLES, 
        SOFT_SKILLS_TRIGGERS, 
        HARD_SKILLS_TRIGGERS, 
        BUSINESS_SKILLS_TRIGGERS,
        SOCIAL_INFRA_TRIGGERS
    )
except ImportError:
    from skills_vocabulary import (
        TARGET_ROLES, 
        SOFT_SKILLS_TRIGGERS, 
        HARD_SKILLS_TRIGGERS, 
        BUSINESS_SKILLS_TRIGGERS,
        SOCIAL_INFRA_TRIGGERS
    )

INPUT_DIR = r"C:\Users\Asus\OneDrive\Рабочий стол\Project ML ITMO\Модуль №3 ML System Design and MFDP\MFDP\data\raw\hh_pages"
OUTPUT_INTERIM = r"C:\Users\Asus\OneDrive\Рабочий стол\Project ML ITMO\Модуль №3 ML System Design and MFDP\MFDP\data\interim\data_interim_vacancies.csv"

ALL_TEXT_SKILLS = {**SOFT_SKILLS_TRIGGERS, **HARD_SKILLS_TRIGGERS, **BUSINESS_SKILLS_TRIGGERS}

def parse_html_experience(text):
    text = text.lower().strip()
    if any(x in text for x in ["нет опыта", "без опыта"]): return 0
    if "1–3 года" in text or "1 года" in text or "1-3 года" in text: return 24
    if "3–6 лет" in text or "3 лет" in text or "3-6 лет" in text: return 54
    return 96 if any(x in text for x in ["более 6 лет", "6 лет"]) else 0

def parse_html_salary(salary_text):
    if not salary_text or "не указана" in salary_text.lower():
        return None, None, None
    text = salary_text.replace("\u202f", "").replace("\xa0", "").replace(" ", "").lower()
    if not any(curr in text for curr in ["руб", "rur", "rub", "₽"]):
        return None, None, None
    nums = [float(n) for n in re.findall(r'\d+', text)]
    if not nums: return None, None, None
    
    if "от" in text and len(nums) == 1: return nums[0], None, "RUR"
    elif "до" in text and len(nums) == 1: return None, nums[0], "RUR"
    elif len(nums) >= 2: return nums[0], nums[1], "RUR"
    return nums[0], nums[0], "RUR"

def determine_role_class(title_text):
    title_lower = title_text.lower().strip()
    for role_id, role_info in TARGET_ROLES.items():
        for query in role_info.get("queries", []):
            pattern = re.escape(query.lower().strip())
            if re.search(pattern, title_lower): 
                return role_id
    return 8

def determine_region_tier(geo_text):
    if not geo_text: return 'Tier-3'
    geo_lower = geo_text.lower().strip()
    if any(x in geo_lower for x in ['москва', 'санкт-петербург']): return 'Tier-1'
    million_cities = ['новосибирск', 'екатеринбург', 'казань', 'нижний новгород', 'красноярск', 'челябинск', 'самара', 'уфа']
    return 'Tier-2' if any(city in geo_lower for city in million_cities) else 'Tier-3'

def check_text_patterns(text, triggers_dict):
    flags = {}
    for skill_name, patterns in triggers_dict.items():
        flags[skill_name] = 1 if any(re.search(p, text) for p in patterns) else 0
    return flags

if __name__ == "__main__":
    print("[ОФФЛАЙН ПАРСЕР] Запуск сквозной обработки папки вакансий...")
    if not os.path.exists(INPUT_DIR):
        print(f"[ОШИБКА] Директория {INPUT_DIR} не найдена!")
        exit(1)
        
    dataset = []
    html_files = []
    for root, dirs, files in os.walk(INPUT_DIR):
        for file in files:
            if file.endswith('.html'):
                html_files.append(os.path.join(root, file))
                
    total_files = len(html_files)
    print(f" Найдено файлов для анализа: {total_files}")
    print(" Начинаем расчет признаков. Пожалуйста, подождите...")

    for idx, file_path in enumerate(sorted(html_files), 1):
        # ИСПРАВЛЕНО: Индикатор прогресса в консоли, чтобы видеть динамику
        if idx % 50 == 0 or idx == total_files:
            print(f"   [Прогресс] Обработано файлов: {idx}/{total_files}...")
            
        with open(file_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "html.parser")
            
        cards = soup.find_all(attrs={"data-qa": "vacancy-serp__vacancy"}) or \
                soup.find_all(class_=re.compile("vacancy-serp-item|serp-item"))
            
        for card in cards:
            title_el = card.find(attrs={"data-qa": "vacancy-serp__vacancy-title"}) or card.find(class_=re.compile("title"))
            title = title_el.text.strip() if title_el else "Не указано"
            
            salary_el = card.find(attrs={"data-qa": "vacancy-serp__vacancy-compensation"}) or card.find(class_=re.compile("compensation|salary"))
            s_from, s_to, _ = parse_html_salary(salary_el.text.strip() if salary_el else "")
            
            if s_from is None and s_to is None: 
                continue
            
            exp_el = card.find(class_=re.compile(r"vacancy-serp__vacancy-work-experience|experience|work-experience|label___"))
            # Если селекторы классов не сработали, делаем текстовый перебор внутри карточки
            exp_text = ""
            if exp_el:
                exp_text = exp_el.text.strip()
            else:
                # Ищем упоминание ключевых слов опыта в тексте самой карточки
                exp_match = re.search(r"(опыт|требуемый опыт|без опыта)[^\n]+", card.text.lower())
                if exp_match:
                    exp_text = exp_match.group(0)
            geo_el = card.find(attrs={"data-qa": "vacancy-serp__vacancy-address"}) or card.find(class_=re.compile("address|area"))
            
            card_text_lower = card.text.lower()
            row = {
                "role_name_raw": title,
                "role_class": determine_role_class(title),
                "experience_months": parse_html_experience(exp_el.text.strip() if exp_el else ""),
                "region_tier": determine_region_tier(geo_el.text.strip() if geo_el else ""),
                "salary_from": s_from,
                "salary_to": s_to,
                "is_vacancy": 1
            }
            
            skill_flags = check_text_patterns(card_text_lower, ALL_TEXT_SKILLS)
            row.update(skill_flags)
            
            skill_cols = list(ALL_TEXT_SKILLS.keys())
            row['skills_completion_rate'] = sum(row[s] for s in skill_cols) / len(skill_cols) if skill_cols else 0
            row.update(check_text_patterns(card_text_lower, SOCIAL_INFRA_TRIGGERS))
            
            dataset.append(row)

    df = pd.DataFrame(dataset)
    os.makedirs(os.path.dirname(OUTPUT_INTERIM), exist_ok=True)
    df.to_csv(OUTPUT_INTERIM, index=False, encoding='utf-8-sig')
    print(f"[УСПЕХ] Обработано вакансий: {len(df)}. Промежуточный файл сохранен в {OUTPUT_INTERIM}")