import os
import sys
import re
import glob
import random
import pandas as pd
from bs4 import BeautifulSoup
import torch
from transformers import AutoTokenizer, AutoModel
from tqdm import tqdm

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from skills_vocabulary import (
        ROLE_PATTERNS, 
        SOFT_SKILLS_TRIGGERS, 
        HARD_SKILLS_TRIGGERS, 
        BUSINESS_SKILLS_TRIGGERS,
        SOCIAL_INFRA_TRIGGERS,
        GEOGRAPHIC_TIERS
    )
except ImportError:
    from skills_vocabulary import (
        ROLE_PATTERNS, 
        SOFT_SKILLS_TRIGGERS, 
        HARD_SKILLS_TRIGGERS, 
        BUSINESS_SKILLS_TRIGGERS,
        SOCIAL_INFRA_TRIGGERS,
        GEOGRAPHIC_TIERS
    )

# СИСТЕМНЫЕ НАСТРОЙКИ ПУТЕЙ ПРОЕКТА
INPUT_DIR = r"C:\Users\Asus\OneDrive\Рабочий стол\Project ML ITMO\Модуль №3 ML System Design and MFDP\MFDP\data\raw\hh_pages"
OUTPUT_INTERIM = r"C:\Users\Asus\OneDrive\Рабочий стол\Project ML ITMO\Модуль №3 ML System Design and MFDP\MFDP\data\interim\data_interim_vacancies.csv"

# === ИНИЦИАЛИЗАЦИЯ ИЗОЛИРОВАННОГО ЛОКАЛЬНОГО NLP-ДВИЖКА ===
print("[NLP-ENGINE] Загрузка локальной нейросети RuBERT-tiny...")
MODEL_NAME = "cointegrated/rubert-tiny"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModel.from_pretrained(MODEL_NAME)

def get_embedding(text):
    """Превращает предложение в семантический вектор (эмбеддинг)"""
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512, padding=True)
    with torch.no_grad():
        outputs = model(**inputs)
    # Mean pooling - усредняем токены для извлечения контекста всего предложения
    return outputs.last_hidden_state.mean(dim=1)

def calculate_similarity(vector_a, vector_b):
    """Рассчитывает косинусное сходство между векторами предложений"""
    return torch.cosine_similarity(vector_a, vector_b).item()

# ВСПОМОГАТЕЛЬНЫЕ МОДУЛИ ИЗЪЯТИЯ ФИЧ ИЗ ТЕКСТА И МЕТАДАННЫХ

def parse_html_experience(text):
    """Восстановление дисперсии требуемого стажа работы (в месяцах)"""
    text = text.lower().strip()
    if any(x in text for x in ["нет опыта", "без опыта"]): return 0
    if "1–3 года" in text or "1 года" in text or "1-3 года" in text or "1–3" in text: return 24
    if "3–6 лет" in text or "3 лет" in text or "3-6 лет" in text or "3–6" in text: return 54
    return 96 if any(x in text for x in ["более 6 лет", "6 лет", "более 6"]) else 0

def parse_html_salary(salary_text):
    """
    Мультивалютный b2b-конвертер признаков.
    Автоматически пересчитывает иностранные оклады в рубли по фиксированному курсу
    и возвращает бинарный маркер валюты для защиты от выбросов.
    """
    if not salary_text or "не указана" in salary_text.lower():
        return None, None, 0
    
    # Нормализуем текст (удаляем пробелы и невидимые символы)
    text = salary_text.replace("\u202f", "").replace("\xa0", "").replace(" ", "").lower()
    
    # Извлекаем все группы цифр
    nums = [float(n) for n in re.findall(r'\d+', text)]
    if not nums: 
        return None, None, 0
        
    s_from, s_to = None, None

    # Извлекаем конкретные числовые значения nums[0] и nums[-1], не передаём сырые значения в мат. операции
    if "от" in text and len(nums) >= 1: 
        s_from = nums[0]
    if "до" in text and len(nums) >= 1: 
        s_to = nums[-1]
        
    if len(nums) == 2 and s_from is None and s_to is None:
        s_from, s_to = nums[0], nums[1]
    elif len(nums) == 1 and s_from is None and s_to is None:
        s_from = nums[0]
        
    # МОДУЛЬ ВАЛЮТНОЙ КОНВЕРТАЦИИ ЧЕРЕЗ ФИКСИРОВАННЫЕ МАКРО-КУРСЫ
    EXCHANGE_RATES = {
        'usd': 92.5, '$': 92.5,
        'eur': 101.2, '€': 101.2,
        'kzt': 0.20, 'тенге': 0.20,
        'aed': 25.2, 'дирхам': 25.2,
        'bye': 28.5, 'byn': 28.5, 'бел.руб': 28.5
    }
    
    is_foreign_currency = 0
    conversion_factor = 1.0
    
    # Сканируем строку на наличие признаков иностранных валют
    for currency_key, rate in EXCHANGE_RATES.items():
        if currency_key in text:
            conversion_factor = rate
            is_foreign_currency = 1
            break # Нашли точное совпадение валюты
            
    # Конвертируем границы вилки в рубли на лету
    if s_from: s_from = s_from * conversion_factor
    if s_to: s_to = s_to * conversion_factor
    
    return s_from, s_to, is_foreign_currency

def determine_role_class(title_text):
    """Ликвидация размытых границ классов на основе селективного ROLE_PATTERNS"""
    title_lower = title_text.lower().strip()
    for role_id, pattern in ROLE_PATTERNS.items():
        if re.search(pattern, title_lower): 
            return role_id
    return None  # Жесткий мусороотсекатель: возвращает None для последующего удаления строки

def determine_region_tier_from_html(html_content, title_text):
    """
    Четырехуровневый извлекатель макроэкономических тиров по скрытым JSON-метаданным.
    Выделяет международный финтех (Tier-4) для изоляции валютных выбросов.
    """
    # Сканируем Hydration State стейты на наличие программных тегов городов
    city_match = re.search(r'"areaName"\s*:\s*"([^"]+)"', html_content) or \
                 re.search(r'"cityName"\s*:\s*"([^"]+)"', html_content) or \
                 re.search(r'area:\s*\{\s*name:\s*"([^"]+)"', html_content) or \
                 re.search(r'"area"\s*:\s*\{\s*"name"\s*:\s*"([^"]+)"', html_content)
                 
    city_name = city_match.group(1).lower().strip() if city_match else ""
    
    # Объединяем название вакансии и скрытый город для сквозного поиска релокации и стран
    full_geo_context = f"{title_text.lower().strip()} {city_name}"
        
    # 1. ПРОВЕРКА TIER-4 (МЕЖДУНАРОДНЫЙ СТЕК): Проверяем в первую очередь
    if any(m_city in full_geo_context for m_city in GEOGRAPHIC_TIERS['Tier-4']):
        return 'Tier-4'
    # 2. ПРОВЕРКА TIER-1 (СТОЛИЦЫ)
    if any(tier1_city in full_geo_context for tier1_city in GEOGRAPHIC_TIERS['Tier-1']):
        return 'Tier-1'
    # 3. ПРОВЕРКА TIER-2 (МИЛЛИОННИКИ И ЛИДЕРЫ СУБМИЛЛИОННИКОВ)
    if any(tier2_city in full_geo_context for tier2_city in GEOGRAPHIC_TIERS['Tier-2']):
        return 'Tier-2'
        
    return 'Tier-3'

# ПРЕ-ЭМБЕДДИНГ СЛОВАРЯ СОФТ-СКИЛЛОВ
THRESHOLD = 0.72 
print("[NLP-ENGINE] Пре-эмбеддинг абстрактных концептов из SOFT_SKILLS_TRIGGERS...")
SKILL_VECTORS = {}
for skill_name, phrases in SOFT_SKILLS_TRIGGERS.items():
    SKILL_VECTORS[skill_name] = [get_embedding(phrase) for phrase in phrases]

# === ГЛАВНЫЙ ИСПОЛНЯЕМЫЙ КОНВЕЙЕР ПРОЕКТА ===
if __name__ == "__main__":
    print("[NLP ПАРСЕР] Запуск сквозной обработки полных HTML страниц...")
    if not os.path.exists(INPUT_DIR):
        print(f"[ОШИБКА] Директория {INPUT_DIR} не найдена!")
        exit(1)

    # Собираем файлы рекурсивно по всем вложенным папкам class_XX
    html_files = glob.glob(os.path.join(INPUT_DIR, "class_*", "vacancy_*.html"))
    total_files = len(html_files)
    print(f" Найдено полных карточек для глубокого анализа: {total_files}")
    
    dataset = []
    
    # Обработка с динамическим визуальным прогресс-баром tqdm
    for file_path in tqdm(sorted(html_files), desc="Семантическая разметка матрицы X"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                soup = BeautifulSoup(f.read(), "html.parser")
                
            # Считываем развернутое название вакансии из тега h1 полных страниц
            title_el = soup.find("h1") or soup.find(attrs={"data-qa": "vacancy-title"})
            title = title_el.text.strip() if title_el else "Не указано"
            
            # Жестко пересчитываем класс ролей, устраняя пересечения
            final_class_id = determine_role_class(title)

            # Если вакансия не подходит под сетку классов — полностью выкидываем её (мусороотсекатель)
            if final_class_id is None:
                continue
            
            # Извлечение и расчет зарплатных характеристик
            salary_el = soup.find(attrs={"data-qa": "vacancy-salary"}) or soup.find(class_=re.compile("salary|compensation"))
            salary_raw_text = salary_el.text.strip() if salary_el else ""
            
            # Разбор числовых значений и флага мультивалютности
            s_from, s_to, is_foreign = parse_html_salary(salary_raw_text)
            
            # Игнорируем карточки без указания зарплат для валидности регрессии XGBoost
            if s_from is None and s_to is None: 
                continue

            # Оффлайн расчет таргета: Вычисляем y_offer строго на основе числовых границ вилки
            if s_from and s_to: 
                y_offer = (s_from + s_to) / 2
            elif s_from: 
                y_offer = s_from * 1.15
            else: 
                y_offer = s_to * 0.85

            # Извлечение требуемого стажа работы
            exp_el = soup.find(attrs={"data-qa": "vacancy-experience"}) or soup.find(class_=re.compile("experience"))
            exp_text = exp_el.text.strip() if exp_el else ""
            if not exp_text:
                exp_match = re.search(r"(опыт|требуемый опыт|без опыта)[^\n]+", soup.text.lower())
                exp_text = exp_match.group(0) if exp_match else ""
                
            # Сбор географической локации по скрытым системным JSON-метаданным (Чтение 1 раз!)
            with open(file_path, "r", encoding="utf-8") as geo_f:
                html_content = geo_f.read()
                
            geo_tier = determine_region_tier_from_html(html_content, title)
            
            # Находим блок описания вакансии
            desc_el = soup.find(attrs={"data-qa": "vacancy-description"}) or soup.find(class_=re.compile("description"))
            if not desc_el:
                continue

            # Очищаем текст описания от HTML разметки и лишних пробельных переносов
            clean_description = " ".join(desc_el.get_text().lower().split())
            
            # Нарезаем монолитный текст на предложения для точечной сверки контекста софт-скиллов
            sentences = re.split(r"[.!?;\n]", clean_description)
            sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
            
            # Переводим предложения текущей вакансии в семантические эмбеддинги RuBERT-tiny
            sentence_vectors = [get_embedding(s) for s in sentences]

            # ГИБРИДНЫЙ ПАРСИНГ: РАССЧЕТ БИНАРНЫХ ФЛАГОВ НАВЫКОВ (НЕЙРОСЕТЬ + РЕГЕКС)
            skill_flags = {}
            
            FULL_PROJECT_VOCABULARY = {
                **SOFT_SKILLS_TRIGGERS, 
                **HARD_SKILLS_TRIGGERS, 
                **BUSINESS_SKILLS_TRIGGERS, 
                **SOCIAL_INFRA_TRIGGERS
            }
            
            for skill_name, phrases_to_search in FULL_PROJECT_VOCABULARY.items():
                skill_detected = 0
                
                # 1. Сначала пробуем извлечь софт-навыки с помощью нейросети RuBERT-tiny
                if skill_name in SOFT_SKILLS_TRIGGERS:
                    for s_vec in sentence_vectors:
                        if skill_name in SKILL_VECTORS:
                            for t_vec in SKILL_VECTORS[skill_name]:
                                if calculate_similarity(s_vec, t_vec) >= THRESHOLD:
                                    skill_detected = 1
                                    break
                        if skill_detected:
                            break
                
                # 2. ПРОМЫШЛЕННЫЙ ФОЛБЭК: Если нейросеть пропустила хард/бизнес или софт, 
                # запускаем прямой, сверхточный и регистронезависимый RegEx-поиск по синонимам
                if not skill_detected:
                    for phrase in phrases_to_search:
                        # Защищаем короткие теги (SQL, ВШЭ, МГУ, ДМС) жесткими границами \b 
                        # с экранированием, предотвращая ложные срабатывания внутри других слов
                        if len(phrase.strip()) <= 4:
                            pattern = r'\b' + re.escape(phrase.lower().strip()) + r'\b'
                        else:
                            pattern = r'\b' + re.escape(phrase.lower().strip()) + r'\b'
                            
                        if re.search(pattern, clean_description, re.IGNORECASE):
                            skill_detected = 1
                            break
                        
                skill_flags[skill_name] = skill_detected
                
            # Консолидация строки признаков для итоговой матрицы X
            row = {
                "role_name_raw": title,
                "role_class": final_class_id,
                "experience_months": parse_html_experience(exp_text),
                "region_tier": geo_tier,
                "is_foreign_currency": is_foreign, # Бинарный маркер валюты для защиты от выбросов
                "salary_from": s_from,
                "salary_to": s_to,
                "y_offer": y_offer,
                "is_vacancy": 1
            }
            row.update(skill_flags)
            
            # Расчет относительного показателя полноты требований (исключая бенефиты)
            found_skills = sum(row[s] for s in skill_flags.keys())
            row['skills_completion_rate'] = found_skills / len(skill_flags) if skill_flags else 0.0
            
            dataset.append(row)
            
        except Exception as file_error:
            # Предотвращаем аварийное падение конвейера при обнаружении поврежденных или пустых HTML страниц
            print(f"\n Сбой при обработке карточки {os.path.basename(file_path)}: {file_error}")
            continue

    # СБОРКА И ЭКСПОРТ ДАТАФРЕЙМА С ПОЛНОЙ ПЕРЕЗАПИСЬЮ (MODE='W')
    if dataset:
        df_final = pd.DataFrame(dataset)
        os.makedirs(os.path.dirname(OUTPUT_INTERIM), exist_ok=True)
        
        # Экспортируем в чистый CSV с полной перезаписью ('w')
        df_final.to_csv(OUTPUT_INTERIM, index=False, encoding='utf-8-sig')
        print(f"\n Глубокий ГИБРИДНЫЙ NLP-анализ успешно завершен!")
        print(f"Сформирована стерильная матрица признаков: {df_final.shape} (строк, колонок).")
        print(f"Результат сохранен в: {OUTPUT_INTERIM}")
    else:
        print("\n В ходе обработки HTML-файлов не было извлечено ни одной валидной строки.")