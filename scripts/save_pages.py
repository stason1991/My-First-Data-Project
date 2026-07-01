import os
import time
import random
from urllib.parse import quote
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# === НАСТРОЙКИ СБОРА ===
TARGET_PAGES = 5          # Сколько страниц результатов собрать
# Рекомендуется заменить hh_pages на vacancies, чтобы данные не перемешались с резюме
OUTPUT_DIR = r"C:\Users\Asus\OneDrive\Рабочий стол\Project ML ITMO\Модуль №3 ML System Design and MFDP\MFDP\data\raw\hh_pages"     

os.makedirs(OUTPUT_DIR, exist_ok=True)

TARGET_ROLES = {
    # --- РОЗНИЧНЫЙ И МАССОВЫЙ БЛОК (01 - 10) ---
    1: {
        "queries": [
            "специалист доставка карт", "выездной специалист банк", "представитель банк", 
            "доставка банковских карт", "мобильный специалист банк", "курьер в банк"
        ], 
        "desc": "Мобильный фронт / Доставка карт", "grades": False
    },
    2: {
        "queries": [
            "прямые продажи банк", "менеджер ГПП", "выездной менеджер банк", 
            "активные продажи банк", "полевой менеджер банк", "коммерческий лидер банк"
        ], 
        "desc": "Менеджер прямых продаж (ГПП)", "grades": False
    },
    3: {
        "queries": [
            "руководитель курьеров", "супервайзер курьеров", "логист курьерская служба банк", 
            "координатор доставки банк", "начальник выездного сервиса банк"
        ], 
        "desc": "Руководитель мобильного фронта", "grades": False
    },
    4: {
        "queries": [
            "руководитель группы прямых продаж", "начальник ГПП", "руководитель отдела продаж банк", 
            "superviser гпп", "тимлид активных продаж банк"
        ], 
        "desc": "Руководитель ГПП / Лидер продаж", "grades": False
    },
    5: {
        "queries": [
            "администратор зала банк", "хостес банк", "встречающий менеджер банк", 
            "консультант зала банк", "администратор отделения банк"
        ], 
        "desc": "Администратор зала отделений", "grades": False
    },
    6: {
        "queries": [
            "операционист бэк-офис банк", "специалист сопровождения банк", "специалист бэк-офиса банк", 
            "операционист отделения", "сервисный менеджер банк", "специалист операционного отдела"
        ], 
        "desc": "Операционист (Сервис / Бэк-офис)", "grades": False
    },
    7: {
        "queries": [
            "кассир операционист", "старший кассир банк", "заведующий кассой банк", 
            "кассир отделения банк", "специалист по кассовым операциям"
        ], 
        "desc": "Кассир-операционист отделения", "grades": False
    },
    8: {
        "queries": [
            "клиентский менеджер банк", "менеджер розничных продаж банк", "специалист окон банк", 
            "менеджер по работе с физическими лицами", "консультант по продажам банк", "фронт-менеджер банк"
        ], 
        "desc": "Менеджер по продажам (Масс-Фронт)", "grades": False
    },
    9: {
        "queries": [
            "главный клиентский менеджер", "топ-продавец банк", "ведущий менеджер продаж банк", 
            "главный специалист розничного бизнеса", "senior sales manager bank"
        ], 
        "desc": "Главный менеджер продаж", "grades": False
    },
    10: {
        "queries": [
            "операционист премиум сегмент", "сервис VIP клиентов банк", "премиальное обслуживание банк", 
            "персональный ассистент VIP банк", "менеджер premium сегмента"
        ], 
        "desc": "Premium-операционист розницы", "grades": False
    },

    # --- ПРЕМИУМ, КОРПОРАТИВНЫЙ И ИПОТЕЧНЫЙ БЛОК (11 - 20) ---
    11: {
        "queries": [
            "персональный менеджер private", "инвестиционный консультант банк", "премиум менеджер bank", 
            "финансовый консультант private banking", "управляющий активами банк", " wealth management bank"
        ], 
        "desc": "Персональный менеджер VIP / Private", "grades": False
    },
    12: {
        "queries": [
            "привлечение юридических лиц банк", "клиентский менеджер b2b банк", "менеджер по развитию корпоративного бизнеса", 
            "хантер b2b банк", "активные продажи юр лицам банк", "открытие рко банк"
        ], 
        "desc": "Менеджер по привлечению ЮЛ (Hunter)", "grades": False
    },
    13: {
        "queries": [
            "обслуживание юридических лиц банк", "сопровождение b2b банк", "фермер b2b банк", 
            "аккаунт менеджер b2b банк", "менеджер малого и среднего бизнеса банк", "сопровождение малого бизнеса"
        ], 
        "desc": "Менеджер по обслуживанию ЮЛ (Farmer)", "grades": False
    },
    14: {
        "queries": [
            "руководитель направления b2b банк", "начальник отдела корпоративного бизнеса", 
            "директор департамента юридических лиц банк", "руководитель малого бизнеса банк"
        ], 
        "desc": "Руководитель направления ЮЛ", "grades": False
    },
    15: {
        "queries": [
            "ипотечный менеджер", "специалист ипотечного кредитования", "менеджер по ипотеке", 
            "эксперт по ипотечным сделкам", "андеррайтер ипотеки"
        ], 
        "desc": "Ипотечный менеджер отделений", "grades": False
    },
    16: {
        "queries": [
            "руководитель ипотечного центра", "директор ЦИК банк", "начальник отдела ипотечного кредитования", 
            "руководитель центра ипотечного бизнеса"
        ], 
        "desc": "Руководитель ипотечного отдела / ЦИК", "grades": False
    },
    17: {
        "queries": [
            "менеджер мобильного резерва банк", "универсальный специалист банк", "подменный менеджер банк", 
            "сотрудник мобильной группы банк"
        ], 
        "desc": "Менеджер мобильного резерва", "grades": False
    },
    18: {
        "queries": [
            "главный менеджер мобильного резерва банк", "ведущий специалист мобильного резерва", 
            "антикризисный менеджер отделений"
        ], 
        "desc": "Главный менеджер мобильного резерва", "grades": False
    },
    19: {
        "queries": [
            "заместитель руководителя офиса банк", "ЗРО банк", "заместитель директора отделения банк", 
            "операционный директор дополнительного офиса"
        ], 
        "desc": "Заместитель руководителя офиса", "grades": False
    },
    20: {
        "queries": [
            "руководитель офиса банк", "директор отделения банк", "директор ДО банк", 
            "управляющий дополнительным офисом", "начальник отделения банка"
        ], 
        "desc": "Руководитель офиса (P&L)", "grades": False
    },

    # --- ВЫСОКОТЕХНОЛОГИЧНЫЙ IT-БЛОК БАНКА (21 - 25) ---
    21: {
        "queries": [
            "Data Scientist банк", "Machine Learning Engineer банк", "ML-инженер банк", 
            "аналитик данных куб банк", " Data Scientist Fintech"
        ], 
        "desc": "Data Scientist / ML Engineer", "grades": True  # Включает Junior/Middle/Senior умножение
    },
    22: {
        "queries": [
            "Data Engineer банк", "инженер данных банк", "разработчик DWH банк", 
            "ETL разработчик банк", "аналитик DWH банк"
        ], 
        "desc": "Data Engineer / DWH Developer", "grades": True
    },
    23: {
        "queries": [
            "Java разработчик банк", "Java developer bank", "Java backend банк", 
            "разработчик Джава банк", " Java Spring developer"
        ], 
        "desc": "Java Developer (Backend)", "grades": True
    },
    24: {
        "queries": [
            "Системный аналитик банк", "System Analyst банк", "Бизнес-аналитик IT банк", 
            "аналитик ИТ систем банк", " SA банк"
        ], 
        "desc": "Системный аналитик ИТ", "grades": True
    },
    25: {
        "queries": [
            "DevOps инженер банк", "DevOps Engineer банк", "SRE инженер банк", 
            "инженер инфраструктуры банк", " Site Reliability Engineer"
        ], 
        "desc": "DevOps / SRE Engineer", "grades": True
    },

    # --- БЛОК РИСКОВ, АНДЕРРАЙТИНГА И АНАЛИТИКИ (26 - 28) ---
    26: {
        "queries": [
            "аналитик рисков банк", "Risk Analyst bank", "квант риски банк", 
            "валидатор моделей рисков банк", "риск-менеджер банк"
        ], 
        "desc": "Аналитик рисков (Кредитные/Рыночные)", "grades": False
    },
    27: {
        "queries": [
            "андеррайтер банк", "главный андеррайтер кредитный", "андеррайтер юридических лиц", 
            "андеррайтер крупного бизнеса банк", "риск-андеррайтер"
        ], 
        "desc": "Андеррайтер (b2c / b2b)", "grades": False
    },
    28: {
        "queries": [
            "инвестиционный аналитик", "аналитик инвестиционного департамента", "аналитик IB банк", 
            "Investment Analyst bank", "аналитик рынка ценных бумаг"
        ], 
        "desc": "Инвестиционный аналитик (CFA/ФСФР)", "grades": False
    },

    # --- БЛОК БЕЗОПАСНОСТИ, КОМПЛАЕНСА И АНТИФРОДА (29 - 30) ---
    29: {
        "queries": [
            "специалист 115-ФЗ", "комплаенс контроль банк", "финансовый мониторинг комплаенс", 
            "експерт ПОД ФТ", "санкционный комплаенс банк", " Compliance officer bank"
        ], 
        "desc": "Специалист по комплаенсу (115-ФЗ)", "grades": False
    },
    30: {
        "queries": [
            "аналитик антифрод банк", "специалист по борьбе с мошенничеством", "информационная безопасность банк", 
            " Fraud Analyst bank", "мониторинг фрод операций банк"
        ], 
        "desc": "Аналитик антифрода / ИБ", "grades": False
    },

    # --- БЛОК HR И УПРАВЛЕНИЯ ЧЕЛОВЕЧЕСКИМ КАПИТАЛОМ (31) ---
    31: {
        "queries": [
            "HR менеджер банк", "IT рекрутер банк", "специалист по подбору персонала банк", 
            "HRBP банк", "менеджер по компенсациям и льготам банк", "специалист по кадровому делопроизводству",
            " HR директор банк", "рекрутер финтех", " C&B специалист банк"
        ], 
        "desc": "HR-специалист / Рекрутер / HRBP", "grades": False
    }
}

print("Запуск браузера... Пожалуйста, подождите.")
options = webdriver.ChromeOptions()
options.add_argument("--disable-blink-features=AutomationControlled")
driver = webdriver.Chrome(options=options)

# --- ГЛАВНЫЙ ИНТЕРАКТИВНЫЙ ЦИКЛ ПО ВСЕМ КЛАССАМ ---
for class_id, role_info in TARGET_ROLES.items():
    
    # 1. Создание изолированной подпапки для текущего класса
    clean_desc = role_info["desc"].replace(" ", "_").replace("/", "_")
    current_class_dir = os.path.join(OUTPUT_DIR, f"class_{class_id:02d}_{clean_desc}")
    os.makedirs(current_class_dir, exist_ok=True)
    
    print(f"\n=======================================================")
    print(f" ПОДГОТОВКА КЛАССА №{class_id:02d}: {role_info['desc']}")
    print(f"=======================================================")
    
    user_action = input("Введите 'start' для запуска класса или 'skip' для пропуска: ").strip().lower()
    if user_action == "skip": 
        continue
    elif user_action != "start": 
        print("Сбор остановлен пользователем.")
        break

    # 2. Генерируем пул запросов с учетом IT-грейдов и очисткой от пробелов через .strip()
    final_queries_pool = []
    for raw_query in role_info["queries"]:
        clean_query = raw_query.strip()
        if role_info["grades"]:
            for grade in ["Junior", "Middle", "Senior"]:
                final_queries_pool.append(f"{grade} {clean_query}")
        else:
            final_queries_pool.append(clean_query)

    # 3. ВНУТРЕННИЙ ЦИКЛ: ПОСЛЕДОВАТЕЛЬНЫЙ ПЕРЕБОР ПОИСКОВЫХ ЗАПРОСОВ
    for search_query in final_queries_pool:
        search_query_clean = search_query.strip()
        search_url=f"https://hh.ru/search/vacancy?text={quote(search_query_clean)}&items_on_page=20"
        
        # Добавляем принудительный таймаут загрузки страницы (на случай медленного интернета)
        driver.set_page_load_timeout(30) 
        
        try:
            driver.get(search_url)
        except Exception as e:
            print(f"\n Первичная попытка открыть hh.ru не удалась. Пробуем обойти блокировку сети...")
            # Альтернативный вариант, если hh.ru временно штормит: сначала зайдем на главную, потом на поиск
            driver.get("https://hh.ru")
            time.sleep(2)
            driver.get(search_url)
        
        print(f"\n👉 Браузер перешел на запрос: '{search_query}'")
        print("=== ИНСТРУКЦИЯ ДЛЯ ВАС ===")
        print("1. При необходимости пройдите капчу / авторизацию в окне Chrome.")
        print("2. Проверьте, что фильтры выставлены корректно и это 1-я страница выдачи.")
        print("3. Вернитесь в консоль, введите 'start' и нажмите Enter для запуска автоматического сбора страниц.")
        print("==========================\n")
        
        while True:
            confirm_input = input(f"Запустить сбор для '{search_query}'? (введите 'start'): ").strip().lower()
            if confirm_input == "start":
                break

        print(f"🚀 Старт автоматического сбора страниц по запросу: '{search_query}'")
        
        # 4. ЦИКЛ ПОСТРАНИЧНОГО СБОРА (Внедрен внутрь запроса)
        for page in range(1, TARGET_PAGES + 1):
            current_url = driver.current_url
            print(f"   [Страница {page}/{TARGET_PAGES}] Сохраняем: {current_url}")
            
            # Пошаговый плавный скролл вниз для обхода защиты Lazy-Load Cloudflare
            for scroll_step in range(4):
                driver.execute_script(f"window.scrollTo(0, {scroll_step * 1300});")
                time.sleep(0.4)
            
            # Забираем прогруженный HTML-код страницы
            html_content = driver.page_source
            
            # Формируем безопасное имя файла, привязанное к запросу, чтобы избежать перезаписи
            safe_query_filename = search_query.replace(" ", "_").replace("/", "_").replace("-", "_")
            file_name = f"vac_{safe_query_filename}_page_{page:02d}.html"
            file_path = os.path.join(current_class_dir, file_name)
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            
            # Если это последняя целевая страница — завершаем сбор по этому запросу
            if page == TARGET_PAGES:
                print(f" Успешно собрано {TARGET_PAGES} страниц для запроса '{search_query}'")
                break
                
            # Переход на следующую страницу (Клик по кнопке "Дальше")
            try:
                # Альтернативные селекторы кнопки "Дальше"
                selectors = [
                    '[data-qa="pager-next"]',
                    'a[data-qa="pager-next"]',
                    '.bloko-button[data-qa="pager-next"]',
                    '//span[contains(text(), "Дальше")]/..'
                ]
                
                next_button = None
                for selector in selectors:
                    try:
                        if selector.startswith('//'):
                            next_button = driver.find_element(By.XPATH, selector)
                        else:
                            next_button = driver.find_element(By.CSS_SELECTOR, selector)
                        if next_button and next_button.is_displayed():
                            break
                    except:
                        continue
                        
                if not next_button:
                    
                    print(f"Доступные страницы закончились раньше (на странице {page}). Переходим к следующему шагу.")
                    break

                # Скроллим к кнопке и кликаем через JS
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
                time.sleep(0.6)
                driver.execute_script("arguments[0].click();", next_button)
                
                # Рандомная имитация человеческой задержки для маскировки
                delay = random.uniform(5.5, 8.5)
                time.sleep(delay)
                
            except Exception as e:
                print(f"\n Не удалось автоматически перейти на страницу {page + 1}. Ошибка: {e}")
                print("Проверьте браузер (возможно, вылетела капча).")
                user_choice = input("Нажмите Enter, чтобы попробовать кликнуть заново, или 'stop' для прерывания этого запроса: ").strip().lower()
                if user_choice == 'stop':
                    break

print("\n ВСЕ КЛАССЫ ДОЛЖНОСТЕЙ УСПЕШНО ОБРАБОТАНЫ!")
# driver.quit()  # ЗАКОММЕНТИРОВАНО, ЧТОБЫ БРАУЗЕР НЕ ЗАКРЫВАЛСЯ