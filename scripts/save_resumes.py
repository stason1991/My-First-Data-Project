import os
import time
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- НАСТРОЙКИ ---
TARGET_PAGES = 25           # 25 страниц * 20 резюме = 500 резюме кандидатов
OUTPUT_DIR = "hh_resumes"   # Папка для сохранения HTML-файлов резюме

os.makedirs(OUTPUT_DIR, exist_ok=True)

print("Запуск браузера для сбора РЕЗЮМЕ...")
options = webdriver.ChromeOptions()
options.add_argument("--disable-blink-features=AutomationControlled")
driver = webdriver.Chrome(options=options)

# Открываем раздел поиска резюме
driver.get("https://hh.ru")

print("\n=== ИНСТРУКЦИЯ ДЛЯ СБОРА РЕЗЮМЕ ===")
print("1. В браузере войдите в аккаунт (можно обычный аккаунт соискателя).")
print("2. Перейдите в поиск резюме (кнопка 'Найти сотрудников' или вбейте должность).")
print("3. Настройте фильтры (например: 'Руководитель офиса' или 'Курьер').")
print("4. Убедитесь, что вы на 1-й странице выдачи резюме.")
print("5. Вернитесь сюда, введите 'start' и нажмите Enter.")
print("===================================\n")

while True:
    user_input = input("Введите 'start' для запуска сбора резюме: ").strip().lower()
    if user_input == "start":
        break

print("\n🚀 Старт сбора страниц резюме...")

for page in range(1, TARGET_PAGES + 1):
    current_url = driver.current_url
    print(f"[{page}/{TARGET_PAGES}] Сохраняем страницу резюме: {current_url}")
    
    # Плавный скролл вниз, так как резюме подгружаются лениво (lazy-load)
    for scroll in range(4):
        driver.execute_script(f"window.scrollTo(0, {scroll * 1500});")
        time.sleep(0.8)
    
    # Сохраняем HTML-код выдачи
    html_content = driver.page_source
    file_name = f"resume_page_{page:02d}.html"
    file_path = os.path.join(OUTPUT_DIR, file_name)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    if page == TARGET_PAGES:
        print("\n🎉 Сбор резюме завершен! Файлы в папке:", OUTPUT_DIR)
        break
        
    # Переход на следующую страницу выдачи
    try:
        wait = WebDriverWait(driver, 10)
        
        # Селекторы кнопки "Дальше" в выдаче резюме
        selectors = [
            '[data-qa="pager-next"]',
            'a[data-qa="pager-next"]',
            '.bloko-button[data-qa="pager-next"]'
        ]
        
        next_button = None
        for selector in selectors:
            try:
                next_button = driver.find_element(By.CSS_SELECTOR, selector)
                if next_button:
                    break
            except:
                continue
                
        if not next_button:
            raise Exception("Кнопка 'Дальше' не найдена")

        # ИСПРАВЛЕНО: Скроллинг к кнопке с правильным регистром букв (scrollIntoView)
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
        time.sleep(1)
        
        # Кликаем через JS
        driver.execute_script("arguments[0].click();", next_button)
        
        # Рваная пауза от 5 до 8 секунд
        delay = random.uniform(5.0, 8.0)
        print(f"Успешно перешли. Ожидаем {delay:.2f} сек. перед следующей страницей...")
        time.sleep(delay)
        
    except Exception as e:
        print(f"\n⚠️ Остановка на странице {page}. Причина: {e}")
        print("Проверьте, не появилась ли капча hh.ru или не закончились ли страницы.")
        break