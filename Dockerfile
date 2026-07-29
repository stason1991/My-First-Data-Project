FROM python:3.10-slim

WORKDIR /app

# Устанавливаем минимальные системные зависимости для сборки C-библиотек (psycopg2 и др.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements.txt для кэширования слоев Docker
COPY requirements.txt .

# Блокирование CUDA-пакетов через инверсию индексов репозиториев
# Указываем CPU-индекс как первичный (--index-url). Теперь pip ищет torch только там.
# Стандартный PyPI делаем вторичным (--extra-index-url) для установки остальных библиотек.
RUN pip install --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cpu \
    --extra-index-url https://pypi.org/simple \
    -r requirements.txt

# Копируем исходный код проекта
COPY . .

# Открываем порт для бэкенда FastAPI
EXPOSE 8000
