import os
import time
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- НАСТРОЙКИ ---
TARGET_PAGES = 30           # Сколько страниц результатов собрать
OUTPUT_DIR = "hh_pages"     # Папка для сохранения HTML-файлов

# Создаем папку, если её еще нет
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Инициализируем браузер Chrome
print("Запуск браузера... Пожалуйста, подождите.")
options = webdriver.ChromeOptions()
# Отключаем флаг автоматизации, чтобы hh.ru меньше подозревал робота
options.add_argument("--disable-blink-features=AutomationControlled")
driver = webdriver.Chrome(options=options)

# Открываем hh.ru, чтобы вы могли войти в аккаунт
driver.get("https://hh.ru")

print("\n=== ИНСТРУКЦИЯ ДЛЯ ВАС ===")
print("1. Войдите в свой личный аккаунт на hh.ru в открывшемся окне браузера.")
print("2. Введите нужный поисковый запрос (например: 'Менеджер по продажам банк').")
print("3. Настройте все необходимые фильтры и убедитесь, что вы находитесь на 1-й странице выдачи.")
print("4. Вернитесь в эту консоль и введите 'start'.")
print("==========================\n")

while True:
    user_input = input("Введите 'start' для запуска автоматического сбора: ").strip().lower()
    if user_input == "start":
        break

print("\n🚀 Старт сбора страниц...")

for page in range(1, TARGET_PAGES + 1):
    current_url = driver.current_url
    print(f"[{page}/{TARGET_PAGES}] Сохраняем страницу: {current_url}")
    
    # 1. Плавный скролл вниз, чтобы прогрузились все элементы динамической выдачи
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(1.5)
    
    # 2. Забираем полный HTML-код страницы
    html_content = driver.page_source
    
    # 3. Сохраняем файл на диск
    file_name = f"page_{page:02d}.html"  # форматирование page_01.html, page_02.html
    file_path = os.path.join(OUTPUT_DIR, file_name)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    # Если это была последняя страница — выходим из цикла
    if page == TARGET_PAGES:
        print("\n🎉 Успех! Все 30 страниц сохранены в папку:", OUTPUT_DIR)
        break
        
    # 4. Поиск кнопки "Дальше" и переход
    try:
        # Ждем появления пагинатора чуть дольше (до 10 секунд)
        wait = WebDriverWait(driver, 10)
        
        # Пробуем найти кнопку по альтернативным селекторам, которые использует hh.ru
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
            raise Exception("Кнопка 'Дальше' не найдена на странице")

        # Прокручиваем страницу точно к кнопке, чтобы она была в зоне видимости
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
        time.sleep(1)
        
        # Кликаем через JavaScript (это обходит многие защиты от роботов)
        driver.execute_script("arguments[0].click();", next_button)
        
        # Рандомная пауза побольше (от 4 до 7 секунд), чтобы hh.ru не паниковал
        delay = random.uniform(4.0, 7.0)
        print(f"Успешно перешли. Ожидаем {delay:.2f} сек. перед следующей страницей...")
        time.sleep(delay)
        
    except Exception as e:
        print(f"\n⚠️ Не удалось перейти на страницу {page + 1}. Ошибка: {e}")
        print("Окно браузера оставлено открытым для проверки. Посмотрите, что пошло не так.")
        break

# driver.quit()  # ЗАКОММЕНТИРОВАНО, ЧТОБЫ БРАУЗЕР НЕ ЗАКРЫВАЛСЯ