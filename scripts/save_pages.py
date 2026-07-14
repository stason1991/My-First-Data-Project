import os
import re
import time
import random
import urllib.parse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains

# === НАСТРОЙКИ ГЛУБИННОГО СБОРА ===
TARGET_PAGES = 1  # Сколько страниц выдачи обработать за запрос
OUTPUT_ROOT = r"C:\Users\Asus\OneDrive\Рабочий стол\Project ML ITMO\Модуль №3 ML System Design and MFDP\MFDP\data\raw\hh_pages"
OUTPUT_DIR = OUTPUT_ROOT

# Укомплектованная ролевая сетка ИТМО (31 класс)
TARGET_ROLES = {
    1: {"queries": ["специалист доставка карт", "выездной специалист банк", "представитель банк", "доставка банковских карт", "мобильный специалист банк", "курьер в банк"], "desc": "Мобильный фронт / Доставка карт", "grades": False},
    2: {"queries": ["прямые продажи банк", "менеджер ГПП", "выездной менеджер банк", "активные продажи банк", "полевой менеджер банк", "коммерческий лидер банк"], "desc": "Менеджер прямых продаж (ГПП)", "grades": False},
    3: {"queries": ["руководитель курьеров", "супервайзер курьеров", "логист курьерская служба банк", "координатор доставки банк", "начальник выездного сервиса банк"], "desc": "Руководитель мобильного фронта", "grades": False},
    4: {"queries": ["руководитель группы прямых продаж", "начальник ГПП", "руководитель отдела продаж банк", "superviser гпп", "тимлид активных продаж банк"], "desc": "Руководитель ГПП / Лидер продаж", "grades": False},
    5: {"queries": ["администратор зала банк", "хостес банк", "встречающий менеджер банк", "консультант зала банк", "администратор отделения банк"], "desc": "Администратор зала отделений", "grades": False},
    6: {"queries": ["операционист бэк-офис банк", "специалист сопровождения банк", "специалист бэк-офиса банк", "операционист отделения", "сервисный менеджер банк", "специалист операционного отдела"], "desc": "Операционист (Сервис / Бэк-офис)", "grades": False},
    7: {"queries": ["кассир операционист", "старший кассир банк", "заведующий кассой банк", "кассир отделения банк", "специалист по кассовым операциям"], "desc": "Кассир-операционист отделения", "grades": False},
    8: {"queries": ["клиентский менеджер банк", "менеджер розничных продаж банк", "специалист окон банк", "менеджер по работе с физическими лицами", "консультант по продажам банк", "фронт-менеджер банк"], "desc": "Менеджер по продажам (Масс-Фронт)", "grades": False},
    9: {"queries": ["главный клиентский менеджер", "top-продавец банк", "ведущий менеджер продаж банк", "главный менеджер розничного бизнеса", "senior sales manager bank"], "desc": "Главный менеджер продаж", "grades": False},
    10: {"queries": ["операционист премиум сегмент", "сервис VIP клиентов банк", "премиальное обслуживание банк", "персональный ассистент VIP банк", "менеджер premium сегмента"], "desc": "Premium-операционист розницы", "grades": False},
    11: {"queries": ["персональный менеджер private", "инвестиционный консультант банк", "премиум менеджер bank", "финансовый консультант private banking", "управляющий активами банк", " wealth management bank"], "desc": "Персональный менеджер VIP / Private", "grades": False},
    12: {"queries": ["привлечение юридических лиц банк", "клиентский менеджер b2b банк", "менеджер по развитию корпоративного бизнеса", "хантер b2b банк", "активные продажи юр лицам банк", "открытие рко банк"], "desc": "Менеджер по привлечению ЮЛ (Hunter)", "grades": False},
    13: {"queries": ["обслуживание юридических лиц банк", "сопровождение b2b банк", "фермер b2b банк", "аккаунт менеджер b2b банк", "менеджер малого и среднего бизнеса банк", "сопровождение малого бизнеса"], "desc": "Менеджер по обслуживанию ЮЛ (Farmer)", "grades": False},
    14: {"queries": ["руководитель направления b2b банк", "начальник отдела корпоративного бизнеса", "директор департамента юридических лиц банк", "руководитель малого бизнеса банк"], "desc": "Руководитель направления ЮЛ", "grades": False},
    15: {"queries": ["ипотечный менеджер", "специалист ипотечного кредитования", "менеджер по ипотеке", "эксперт по ипотечным сделкам", "андеррайтер ипотеки"], "desc": "Ипотечный менеджер отделений", "grades": False},
    16: {"queries": ["руководитель ипотечного центра", "директор ЦИК банк", "начальник отдела ипотечного кредитования", "руководитель центра ипотечного бизнеса"], "desc": "Руководитель ипотечного отдела / ЦИК", "grades": False},
    17: {"queries": ["клиентский менеджер группы резерва банк", "группа резерва", "подменный менеджер банк"], "desc": "Менеджер группы резерва", "grades": False},
    18: {"queries": ["главный менеджер резерва банк", "ведущий менеджер группы резерва", "главный подменный менеджер", "ведущий подменный менеджер"], "desc": "Главный менеджер группы резерва", "grades": False},
    19: {"queries": ["заместитель руководителя офиса банк", "заместитель директора отделения банк"], "desc": "Заместитель руководителя офиса", "grades": False},
    20: {"queries": ["руководитель офиса банк", "директор отделения банк", "директор дополнительного офиса банк", "управляющий дополнительным офисом", "начальник отделения банка"], "desc": "Руководитель офиса (P&L)", "grades": False},
    21: {"queries": ["Data Scientist банк", "Machine Learning Engineer банк", "ML Engineer", "Аналитик данных", "Data аналитик", "Data engineer", "AI"], "desc": "Data Scientist / ML Engineer", "grades": True},
    22: {"queries": ["Data Engineer банк", "инженер данных банк"], "desc": "Data Engineer / DWH Developer", "grades": True},
    23: {"queries": ["Java разработчик банк"], "desc": "Java Developer (Backend)", "grades": True},
    24: {"queries": ["Системный аналитик банк"], "desc": "Системный аналитик ИТ", "grades": True},
    25: {"queries": ["DevOps инженер банк"], "desc": "DevOps / SRE Engineer", "grades": True},
    26: {"queries": ["аналитик рисков банк", "риск-аналитик", "risk", "риск"], "desc": "Аналитик рисков (Кредитные/Рыночные)", "grades": False},
    27: {"queries": ["андеррайтер банк", "андеррайтер кредитный"], "desc": "Андеррайтер (b2c / b2b)", "grades": False},
    28: {"queries": ["инвестиционный аналитик", "аналитик инвестиционного департамента"], "desc": "Инвестиционный аналитик (CFA/ФСФР)", "grades": False},
    29: {"queries": ["комплаенс контроль банк", "финансовый мониторинг комплаенс", "комплаенс офицер", "AML officer"], "desc": "Специалист по комплаенсу (115-ФЗ)", "grades": False},
    30: {"queries": ["информационная безопасность банк", "кибербезопасность"], "desc": "ИБ", "grades": False},
    31: {"queries": ["HR менеджер банк", "IT рекрутер банк", "специалист по подбору персонала банк", " HR директор банк"], "desc": "HR-специалист / Рекрутер / HRBP", "grades": False}
}

os.makedirs(OUTPUT_DIR, exist_ok=True)

print("Запуск Chrome браузера... Настройка маскировки антифрода...")
options = webdriver.ChromeOptions()
options.add_argument("--incognito")
options.add_argument("--disable-blink-features=AutomationControlled")

# Изолированный профиль для сохранения кук и "человеческого" цифрового следа
profile_path = os.path.join(os.environ["LOCALAPPDATA"], "Google", "Chrome", "User Data Full Scraper")
options.add_argument(f"--user-data-dir={profile_path}")
options.add_argument("--profile-directory=Default")
options.add_argument("--ignore-certificate-errors")

driver = webdriver.Chrome(options=options)
driver.maximize_window()

# --- ГЛАВНЫЙ ИНТЕРАКТИВНЫЙ ЦИКЛ ПО ВСЕМ КЛАССАМ ---
for class_id, role_info in TARGET_ROLES.items():
    
    # 1. Лаконичные, безопасные имена папок для защиты от лимитов путей Windows
    # Папки будут называться строго: class_01, class_02, class_31
    current_class_dir = os.path.join(OUTPUT_DIR, f"class_{class_id:02d}")
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

    # Генерация пула запросов с учетом IT-грейдов
    final_queries_pool = []
    
    for raw_query in role_info["queries"]:
        clean_query = raw_query.strip()
        
        # Если у класса стоит флаг грейдов (только для IT классов 21-25)
        if role_info.get("grades", False):
            for grade in ["Junior", "Middle", "Senior"]:
                final_queries_pool.append(f"{grade} {clean_query}")
        else:
            # Для массового персонала (Курьеры, Кассиры) грейды НЕ ДОБАВЛЯЮТСЯ
            final_queries_pool.append(clean_query)
            
    print(f"   [INFO] Сформирован изолированный пул из {len(final_queries_pool)} запросов для Класса №{class_id:02d}")

    # ВНУТРЕННИЙ ЦИКЛ ПОИСКОВЫХ ЗАПРОСОВ
    for search_query in final_queries_pool:
        search_query_clean = search_query.strip()
        
        print(f"\n [ЭМУЛЯЦИЯ] Заходим на главную страницу для чистого поиска...")
        driver.get("https://spb.hh.ru/search/vacancy?text=&search_field=name&search_field=company_name&search_field=description&enable_snippets=false&hhtmSourceLabel=vacancy_search_list&L_save_area=true")
        time.sleep(random.uniform(3.0, 4.5)) # Даем сайту полностью прогрузиться
        
        try:
            # Ищем реальное текстовое поле поиска на экране по официальным селекторам HH
            search_input = None
            selectors = [
                'input[data-qa="search-input"]',
                'input[name="text"]',
                '.search-input',
                '//input[@placeholder="Профессия, должность, company"]'
            ]
            
            for selector in selectors:
                try:
                    if selector.startswith('//'):
                        search_input = driver.find_element(By.XPATH, selector)
                    else:
                        search_input = driver.find_element(By.CSS_SELECTOR, selector)
                    if search_input:
                        break
                except:
                    continue
            
            if not search_input:
                raise Exception("Не удалось найти поле поиска на странице.")
                
            # Имитируем поведение человека: кликаем, очищаем и вбиваем текст
            search_input.click()
            time.sleep(0.3)
            search_input.clear()
            time.sleep(0.5)
            
            print(f" ⌨️ [ЭМУЛЯЦИЯ] Вбиваем запрос буква за буквой: '{search_query_clean}'")
            for char in search_query_clean:
                search_input.send_keys(char)
                time.sleep(random.uniform(0.05, 0.15)) # Рваная пауза между нажатиями клавиш
                
            print("\n🚨 [РУЧНОЙ ПЕРЕХВАТ] Текст успешно вбит в строку поиска!")
            
        except Exception as search_error:
            print(f" ⚠️ Ошибка авто-ввода: {search_error}")
            print(f" Пожалуйста, введите запрос '{search_query_clean}' в строку поиска ВРУЧНУЮ.")
            
        print("\n=== ВАШИ ДЕЙСТВИЯ В БРАУЗЕРЕ CHROME ===")
        print("1. Перейдите в открытое окно браузера Chrome.")
        print("2. Решите капчу / Cloudflare прямо сейчас, если они появились на экране.")
        print("3. НАЖМИТЕ СИНЮЮ КНОПКУ 'НАЙТИ' НА САЙТЕ МЫШКОЙ (или нажмите Enter на клавиатуре).")
        print("4. Убедитесь, что перед вами открылся чистый список вакансий (курьеры, доставка).")
        print("5. Вернитесь сюда, введите 'start' и нажмите Enter для запуска сбора.")
        print("=======================================\n")
        
        # БЕСКОНЕЧНОЕ ОЖИДАНИЕ: Скрипт не сбросит капчу, пока вы сами не нажмете кнопку на сайте и не напишете start
        while True:
            if input(f"Запустить сбор для '{search_query}'? (введите 'start'): ").strip().lower() == "start":
                break
                
        # Сохраняем получившийся URL поисковой выдачи для дальнейших возвратов
        search_url = driver.current_url
                
        # ЦИКЛ ПОСТРАНИЧНОГО ОБХОДА ВЫДАЧИ
        for page in range(1, TARGET_PAGES + 1):
            print(f"   [Выдача: Страница {page}/{TARGET_PAGES}] Извлекаем ссылки на вакансии...")
            
            # Плавный скролл для прогрузки динамических элементов Lazy-Load
            for scroll_step in range(6):
                driver.execute_script(f"window.scrollTo(0, {scroll_step * 1200});")
                time.sleep(0.3)
                
            # --- ЭТАП 1: Извлечение ссылок через универсальный XPath (ИСПРАВЛЕННЫЙ) ---
            vacancy_links = []
            
            # Находим все элементы вакансий на странице
            elements = driver.find_elements(By.XPATH, '//a[contains(@href, "/vacancy/")]')
            
            # Стоп-слова для полной блокировки ритейла, доставок еды и складов
            retail_stop_words = [
                "озон", "ozon", "яндекс", "yandex", "самокат", "пятерочка", "магнит", "Ozon", "Пятёрочку", 
                "x5", "wildberries", "вайлдберриз", "сдек", "cdek", "суши", "пицца", 
                "доставка еды", "склад", "комплектовщик", "грузчик", "автокурьер", "пятерочку", "пвз", "аптеки"
            ]
            
            for el in elements:
                try:
                    href = el.get_attribute("href")
                    if href:
                        clean_href = href.split("?")[0]
                        
                        if "/vacancy/" in clean_href and clean_href not in vacancy_links:
                            vacancy_id = clean_href.split("/vacancy/")[-1]
                            
                            if vacancy_id.isdigit():
                                # КРИТИЧЕСКИЙ ФИЛЬТР: Проверяем текст самой карточки вакансии в выдаче
                                # Поднимаемся к родительскому контейнеру карточки, чтобы прочитать её описание
                                try:
                                    card_element = el.find_element(By.XPATH, './ancestor::div[contains(@class, "vacancy-card") or contains(@class, "serp-item")]')
                                    card_text = card_element.text.lower()
                                except:
                                    # Если класс контейнера изменился, берем текст самого элемента ссылки
                                    card_text = el.text.lower()
                                
                                # Проверяем, есть ли стоп-слова ритейла в карточке
                                has_retail = any(word in card_text for word in retail_stop_words)
                                
                                if has_retail:
                                    print(f"   [ОТКЛОНЕНО] Пропущена ритейл-вакансия ID: {vacancy_id} (найдено стоп-слово)")
                                    continue # Скрипт игнорирует эту ссылку и идет дальше
                                    
                                vacancy_links.append(clean_href)
                except:
                    continue
                    
            print(f"Найдено {len(vacancy_links)} ЧИСТЫХ БАНКОВСКИХ вакансий на странице. Начинаем глубокое скачивание...")
            
            # --- ЭТАП 2: Переход по ссылкам во вкладках и скачивание развёрнутого HTML (ФИКС ИНДЕКСОВ) ---
            for idx, link in enumerate(vacancy_links, 1):
                try:
                    vacancy_id = link.split("/vacancy/")[-1]
                    file_name = f"vacancy_{vacancy_id}.html"
                    file_path = os.path.join(current_class_dir, file_name)
                    
                    if os.path.exists(file_path):
                        continue
                        
                    # Открываем карточку вакансии в новой вкладке, сохраняя стейт выдачи
                    driver.execute_script(f"window.open('{link}', '_blank');")
                    
                    # ИСПРАВЛЕНО: Переключаемся строго на ВТОРУЮ вкладку (индекс 1)
                    driver.switch_to.window(driver.window_handles[1]) 
                    time.sleep(random.uniform(3.5, 5.5))  # Симуляция чтения текста человеком
                    
                    # Прокрутка до середины для принудительной прогрузки скрытого хард-стека
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 3);")
                    time.sleep(0.5)
                    
                    # Скачиваем монолитный развёрнутый HTML
                    full_html = driver.page_source
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(full_html)
                    print(f"      [{idx}/{len(vacancy_links)}] Сохранена полная вакансия ID: {vacancy_id}")
                    
                    # Закрываем вкладку вакансии
                    driver.close()
                    
                    # ИСПРАВЛЕНО: Возвращаемся строго на ПЕРВУЮ вкладку с поиском (индекс 0)
                    driver.switch_to.window(driver.window_handles[0]) 
                    
                    time.sleep(random.uniform(1.5, 3.0))
                except Exception as card_error:
                    print(f"      ❌ Ошибка при обработке карточки {link}: {card_error}")
                    # Аварийный сброс: если застряли во второй вкладке, закрываем её и возвращаемся на первую
                    while len(driver.window_handles) > 1:
                        driver.switch_to.window(driver.window_handles[-1])
                        driver.close()
                    driver.switch_to.window(driver.window_handles[0])
                    continue
                    
            if page == TARGET_PAGES:
                print(f" Успешно собрано {TARGET_PAGES} страниц для запроса '{search_query}'")
                break

print("\n ВСЕ КЛАССЫ ДОЛЖНОСТЕЙ УСПЕШНО ОБРАБОТАНЫ!")
# driver.quit()  # ЗАКОММЕНТИРОВАНО, ЧТОБЫ БРАУЗЕР НЕ ЗАКРЫВАЛСЯ