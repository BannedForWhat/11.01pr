# docker/Dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# системные библиотеки для psycopg и pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc libpq-dev musl-dev \
    libjpeg62-turbo-dev zlib1g-dev libpng-dev \
    curl bash && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# requirements (если есть отдельный файл — лучше скопировать сначала для кеша)
COPY requirements.txt ./requirements.txt
RUN tr -d '\000' < requirements.txt > requirements.utf8.txt && mv requirements.utf8.txt requirements.txt \
    && pip install --upgrade pip && pip install -r requirements.txt \
    && pip install gunicorn psycopg2-binary

# копируем весь проект
COPY . .

# В проекте manage.py лежит в TabletopStoreUP/, поднимем PYTHONPATH
ENV PYTHONPATH=/app/TabletopStoreUP \
    DJANGO_SETTINGS_MODULE=TabletopStoreUP.settings

# статические файлы будут собираться сюда
ENV STATIC_ROOT=/app/staticfiles \
    MEDIA_ROOT=/app/media \
    BACKUPS_DIR=/app/backups

# entrypoint скрипт
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

CMD ["/entrypoint.sh"]
