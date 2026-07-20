FROM python:3.10-slim

WORKDIR /app

# Устанавливаем системные зависимости сборщика C-библиотек
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

# КРИТИЧЕСКИЙ МЛОПС ШАГ: Сначала копируем только requirements и ставим пакеты.
# Это позволит намертво закэшировать torch+cpu в памяти Docker.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# И только в самом конце копируем остальной код проекта
COPY . .

EXPOSE 8000