import os
import sys
import re
import glob
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
import torch
from transformers import AutoTokenizer, AutoModel
from tqdm import tqdm
from sklearn.decomposition import PCA

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Интегрирован импорт BANK_TIERS из центрального конфигурационного файла
try:
    from skills_vocabulary import (
        ROLE_PATTERNS, SOFT_SKILLS_TRIGGERS, HARD_SKILLS_TRIGGERS, 
        BUSINESS_SKILLS_TRIGGERS, SOCIAL_INFRA_TRIGGERS, GEOGRAPHIC_TIERS,
        BANK_TIERS
    )
except ImportError:
    from skills_vocabulary import (
        ROLE_PATTERNS, SOFT_SKILLS_TRIGGERS, HARD_SKILLS_TRIGGERS, 
        BUSINESS_SKILLS_TRIGGERS, SOCIAL_INFRA_TRIGGERS, GEOGRAPHIC_TIERS,
        BANK_TIERS
    )

# СИСТЕМНЫЕ НАСТРОЙКИ ПУТЕЙ ПРОЕКТА ИТМО
INPUT_DIR = r"C:\Users\Asus\OneDrive\Рабочий стол\Project ML ITMO\Модуль №3 ML System Design and MFDP\MFDP\data\raw\hh_pages"
OUTPUT_INTERIM_GRADES = r"C:\Users\Asus\OneDrive\Рабочий стол\Project ML ITMO\Модуль №3 ML System Design and MFDP\MFDP\data\interim\data_interim_vacancies.csv"

print("[NLP-ENGINE] Загрузка локальной нейросети RuBERT-tiny...")
MODEL_NAME = "cointegrated/rubert-tiny"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModel.from_pretrained(MODEL_NAME)

def get_embedding(text):
    """Превращает предложение в семантический вектор (эмбеддинг)"""
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512, padding=True)
    with torch.no_grad():
        outputs = model(**inputs)
    return outputs.last_hidden_state.mean(dim=1).numpy().flatten()

def calculate_similarity(vector_a, vector_b):
    """Рассчитывает косинусное сходство между векторами предложений"""
    tensor_a = torch.tensor(vector_a)
    tensor_b = torch.tensor(vector_b)
    return torch.cosine_similarity(tensor_a.unsqueeze(0), tensor_b.unsqueeze(0)).item()

def parse_html_experience(text):
    """Восстановление требуемого стажа работы (в месяцах)"""
    text = text.lower().strip()
    if any(x in text for x in ["нет опыта", "без опыта"]): return 0
    if "1–3 года" in text or "1 года" in text or "1-3 года" in text or "1–3" in text: return 24
    if "3–6 лет" in text or "3 лет" in text or "3-6 лет" in text or "3–6" in text: return 54
    return 96 if any(x in text for x in ["более 6 лет", "6 лет", "более 6"]) else 0

def parse_html_salary(salary_text):
    """
    Интеллектуальный мультивалютный b2b-конвертер.
    Конвертирует валюту в рубли ДО разделения границ, гарантируя
    возврат изолированных чисел float и жестко выжигая МРОТ-шум (3, 4, 6) в None.
    """
    if not salary_text or "не указана" in salary_text.lower():
        return None, None, 0
    text = salary_text.replace("\u202f", "").replace("\xa0", "").replace(" ", "").lower()
    
    # Сбор всех чисел (включая дробные)
    nums = [float(n.replace(',', '.')) for n in re.findall(r'\d+(?:[\.,]\d+)?', text)]
    if not nums: 
        return None, None, 0
        
    EXCHANGE_RATES = {
        'usd': 92.5, '$': 92.5, 'eur': 101.2, '€': 101.2,
        'kzt': 0.20, 'тенге': 0.20, 'aed': 25.2, 'дирхам': 25.2,
        'bye': 28.5, 'byn': 28.5, 'бел.руб': 28.5
    }
    is_foreign_currency = 0
    conversion_factor = 1.0
    for currency_key, rate in EXCHANGE_RATES.items():
        if currency_key in text:
            conversion_factor = rate
            is_foreign_currency = 1
            break
            
    # Конвертируем абсолютно все найденные числа в рубли СРАЗУ
    nums = [n * conversion_factor for n in nums]
    
    # Превращаем любые мусорные цифры меньше 27 000 руб. в None сразу
    clean_nums = [n if n >= 27000 else None for n in nums]
    
    s_from, s_to = None, None
    
    # Распределяем границы строго как изолированные числа float (берём [0] элемент списка)
    if "от" in text and "до" in text and len(clean_nums) >= 2:
        s_from = clean_nums[0]
        s_to = clean_nums[-1]
    elif "от" in text and len(clean_nums) >= 1:
        s_from = clean_nums[0]  #б ерем число, не список
        s_to = None
    elif "до" in text and len(clean_nums) >= 1:
        valid_to_nums = [n for n in clean_nums if n is not None]
        s_to = valid_to_nums[-1] if valid_to_nums else None
        s_from = None
    elif len(clean_nums) == 2:
        s_from = clean_nums[0]
        s_to = clean_nums[-1]
    elif len(clean_nums) == 1:
        s_from = clean_nums[0]
        s_to = clean_nums[0]
        
    return s_from, s_to, is_foreign

def determine_role_class(title_text):
    """Ликвидация размытых границ классов на основе селективного ROLE_PATTERNS"""
    title_lower = title_text.lower().strip()
    for role_id, pattern in ROLE_PATTERNS.items():
        if re.search(pattern, title_lower): return role_id
    return None

def determine_region_tier_from_html(html_content, title_text):
    """Четырехуровневый извлекатель макроэкономических тиров по скрытым JSON-метаданным"""
    city_match = re.search(r'"areaName"\s*:\s*"([^"]+)"', html_content) or \
                 re.search(r'"cityName"\s*:\s*"([^"]+)"', html_content) or \
                 re.search(r'area:\s*\{\s*name:\s*"([^"]+)"', html_content) or \
                 re.search(r'"area"\s*:\s*\{\s*"name"\s*:\s*"([^"]+)"', html_content)
    city_name = city_match.group(1).lower().strip() if city_match else ""
    full_geo_context = f"{title_text.lower().strip()} {city_name}"
    if any(m_city in full_geo_context for m_city in GEOGRAPHIC_TIERS['Tier-4']): return 'Tier-4'
    if any(tier1_city in full_geo_context for tier1_city in GEOGRAPHIC_TIERS['Tier-1']): return 'Tier-1'
    if any(tier2_city in full_geo_context for tier2_city in GEOGRAPHIC_TIERS['Tier-2']): return 'Tier-2'
    return 'Tier-3'

def determine_bank_tier(soup):
    """Извлекатель тира банковского бренда по словарю BANK_TIERS из skills_vocabulary.py"""
    comp_el = soup.find(attrs={"data-qa": "vacancy-company-name"}) or soup.find(class_=re.compile("company-name"))
    comp_text = comp_el.text.lower().strip() if comp_el else ""
    if any(b_name in comp_text for b_name in BANK_TIERS['Bank_Tier_1']):
        return "Bank_Tier_1"
    if any(b_name in comp_text for b_name in BANK_TIERS['Bank_Tier_2']):
        return "Bank_Tier_2"
    return "Bank_Tier_3"

GLOBAL_THRESHOLD = 0.72 
print("[NLP-ENGINE] Пре-эмбеддинг абстрактных концептов из SOFT_SKILLS_TRIGGERS...")
SKILL_VECTORS = {}
for skill_name, phrases in SOFT_SKILLS_TRIGGERS.items():
    SKILL_VECTORS[skill_name] = [get_embedding(phrase) for phrase in phrases]

if __name__ == "__main__":
    print("[NLP П ПАРСЕР] Запуск сквозного b2b-конвейера...")
    if not os.path.exists(INPUT_DIR):
        print(f"[ОШИБКА] Директория {INPUT_DIR} не найдена!")
        exit(1)
        
    html_files = glob.glob(os.path.join(INPUT_DIR, "class_*", "vacancy_*.html"))
    
    dataset = []
    all_description_embeddings = [] # Накопитель семантических векторов описаний вакансий
    
    for file_path in tqdm(sorted(html_files), desc="Семантическая разметка матрицы X"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                html_content = f.read()
                soup = BeautifulSoup(html_content, "html.parser")
                
            title_el = soup.find("h1") or soup.find(attrs={"data-qa": "vacancy-title"})
            title = title_el.text.strip() if title_el else "Не указано"
            
            final_class_id = determine_role_class(title)
            if final_class_id is None: continue
            
            salary_el = soup.find(attrs={"data-qa": "vacancy-salary"}) or soup.find(class_=re.compile("salary|compensation"))
            salary_raw_text = salary_el.text.strip() if salary_el else ""
            
            s_from, s_to, is_foreign = parse_html_salary(salary_raw_text)
            if s_from is None and s_to is None: continue

            # Восстановление таргета с применением коэффициентов 1.15 и 0.85
            if s_from is not None and s_to is not None: y_offer = (s_from + s_to) / 2
            elif s_from is not None: y_offer = s_from * 1.15
            else: y_offer = s_to * 0.85

            exp_el = soup.find(attrs={"data-qa": "vacancy-experience"}) or soup.find(class_=re.compile("experience"))
            exp_text = exp_el.text.strip() if exp_el else ""
            if not exp_text:
                exp_match = re.search(r"(опыт|требуемый опыт|без опыта)[^\n]+", soup.text.lower())
                exp_text = exp_match.group(0) if exp_match else ""
                
            geo_tier = determine_region_tier_from_html(html_content, title)
            bank_tier = determine_bank_tier(soup) # Маркируем бренд банка
            
            desc_el = soup.find(attrs={"data-qa": "vacancy-description"}) or soup.find(class_=re.compile("description"))
            if not desc_el: continue

            clean_description = " ".join(desc_el.get_text().lower().split())
            
            # ВНЕДРЕНИЕ ИДЕИ В: Плотный семантический эмбеддинг всего текста описания
            desc_vector = get_embedding(clean_description[:512])
            
            sentences = re.split(r"[.!?;\n]", clean_description)
            sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
            sentence_vectors = [get_embedding(s) for s in sentences]

            skill_flags = {}
            FULL_PROJECT_VOCABULARY = {
                **SOFT_SKILLS_TRIGGERS, **HARD_SKILLS_TRIGGERS, 
                **BUSINESS_SKILLS_TRIGGERS, **SOCIAL_INFRA_TRIGGERS
            }
            commercial_soft_skills = [
                'skill_objection_handling', 'skill_cold_sales', 'skill_telemarketing',
                'skill_cross_sales', 'skill_sales_book_analysis', 'skill_roleplay_defense',
                'skill_vip_negotiations', 'skill_difficult_clients'
            ]
            
            for skill_name, phrases_to_search in FULL_PROJECT_VOCABULARY.items():
                skill_detected = 0
                if skill_name in SOFT_SKILLS_TRIGGERS:
                    # Переменная CURRENT_THRESHOLD честно задействована в косинусном сходстве!
                    CURRENT_THRESHOLD = 0.82 if skill_name in commercial_soft_skills else GLOBAL_THRESHOLD
                    for s_vec in sentence_vectors:
                        if skill_name in SKILL_VECTORS:
                            for t_vec in SKILL_VECTORS[skill_name]:
                                if calculate_similarity(s_vec, t_vec) >= CURRENT_THRESHOLD:
                                    skill_detected = 1
                                    break
                        if skill_detected: break
                
                if not skill_detected:
                    for phrase in phrases_to_search:
                        pattern = r'\b' + re.escape(phrase.lower().strip()) + r'\b'
                        if re.search(pattern, clean_description, re.IGNORECASE):
                            skill_detected = 1
                            break
                skill_flags[skill_name] = skill_detected
            
            # ВНЕДРЕНИЕ ИДЕИ Б: ЗНАНИЕ ИНОСТРАННЫХ ЯЗЫКОВ (РЕГЕКС ФИЧА)
            is_english = 1 if re.search(r"\benglish\b|английск|upper\s*intermediate|advanced|b2|c1|fluent", clean_description) else 0
            skill_flags['skill_english_proficiency'] = is_english
            
            # Грейды и менеджмент
            title_lower = title.lower().strip()
            is_grade_management = 1 if re.search(r"руководитель|директор|заместитель|начальник|заведующий|тимлид|team\s*lead|lead|управляющий", title_lower) else 0
            is_grade_junior = 1 if (is_grade_management == 0) and re.search(r"начинающий|стажер|стажёр|junior|джуниор|начальный.*уровень|без\s*опыта", title_lower) else 0
            is_grade_senior = 1 if (is_grade_management == 0) and re.search(r"главный|ведущий|senior|сеньор|сеньёр|эксперт|руководитель.*направления", title_lower) else 0
            is_grade_middle = 1 if (is_grade_junior == 0 and is_grade_senior == 0 and is_grade_management == 0) else 0

            # РАСШИФРОВКА И КВАНТИЗАЦИЯ ПРИЗНАКА ОБРАЗОВАНИЯ (edu_level_encoded)
            edu_level = 3 
            if "среднее профессиональное" in html_content or "колледж" in html_content or "техникум" in html_content: edu_level = 1
            elif "неполное высшее" in html_content: edu_level = 2
            elif "высшее" in html_content: edu_level = 3
            elif "магистратура" in html_content or "кандидат" in html_content: edu_level = 4
            elif "среднее образование" in html_content: edu_level = 0

            row = {
                "role_name_raw": title, "role_class": final_class_id,
                "experience_months": parse_html_experience(exp_text), "region_tier": geo_tier,
                "bank_tier": bank_tier, "is_foreign_currency": is_foreign,
                "is_grade_junior": is_grade_junior, "is_grade_middle": is_grade_middle,
                "is_grade_senior": is_grade_senior, "is_grade_management": is_grade_management,
                "edu_level_encoded": edu_level, "salary_from": s_from, "salary_to": s_to, "y_offer": y_offer, "is_vacancy": 1
            }
            row.update(skill_flags)
            
            found_skills = sum(row[s] for s in skill_flags.keys())
            row['skills_completion_rate'] = found_skills / len(skill_flags) if skill_flags else 0.0
            
            dataset.append(row)
            all_description_embeddings.append(desc_vector)
            
        except Exception as file_error: continue

    if dataset:
        df_final = pd.DataFrame(dataset)
        
        # СЖАТИЕ ЭМБЕДДИНГОВ ВСЕГО ТЕКСТА ОПИСАНИЯ ЧЕРЕЗ PCA ДО 3 ГЛАВНЫХ КОМПОНЕНТ
        print("\n[NLP-ENGINE] Сжатие семантических эмбеддингов текстов через PCA...")
        pca = PCA(n_components=3, random_state=42)
        pca_features = pca.fit_transform(np.array(all_description_embeddings))
        
        df_final['text_pca_1'] = pca_features[:, 0]
        df_final['text_pca_2'] = pca_features[:, 1]
        df_final['text_pca_3'] = pca_features[:, 2]
        
        os.makedirs(os.path.dirname(OUTPUT_INTERIM_GRADES), exist_ok=True)
        df_final.to_csv(OUTPUT_INTERIM_GRADES, index=False, encoding='utf-8-sig')
        print(f"\n Промышленный пайплайн выполнен! Стерильный файл сохранен: {OUTPUT_INTERIM_GRADES}")
        print(f"Итоговая размерность новой матрицы признаков X: {df_final.shape}")