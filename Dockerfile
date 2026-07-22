FROM python:3.10-slim

WORKDIR /app

# Устанавливаем системные зависимости сборщика C-библиотек
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

# КРИТИЧЕСКИЙ ШАГ: Сначала копируем только requirements.txt
COPY requirements.txt .

# Принудительно ставим легковесный torch+cpu, блокируя PyPI и NVIDIA-пакеты
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Ставим остальные зависимости из списка пакетов
RUN pip install --no-cache-dir -r requirements.txt

# И только в самом конце копируем остальной код проекта
COPY . .

EXPOSE 8000