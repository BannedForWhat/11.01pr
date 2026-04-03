#!/usr/bin/env bash
set -e

# Ожидаем БД
if [ -n "$DB_HOST" ]; then
  echo "Waiting for database at $DB_HOST:$DB_PORT ..."
  until python - <<PY
import sys, socket, os
host = os.environ.get("DB_HOST","localhost")
port = int(os.environ.get("DB_PORT","5432"))
s=socket.socket(); s.settimeout(1.0)
try:
    s.connect((host, port)); print("db up")
except Exception as e:
    print(e); sys.exit(1)
finally:
    s.close()
PY
  do
    sleep 1
  done
fi

# миграции
echo "Running migrations..."
python TabletopStoreUP/manage.py migrate --noinput

# статические (если нужно)
echo "Collecting static..."
python TabletopStoreUP/manage.py collectstatic --noinput || true

# демо-данные (по желанию флагом)
if [ "${SEED_DEMO:-0}" = "1" ]; then
  echo "Seeding demo data..."
  python TabletopStoreUP/manage.py seed_demo || true
fi

# запуск gunicorn
echo "Starting gunicorn..."
exec gunicorn TabletopStoreUP.wsgi:application \
  --bind 0.0.0.0:8000 --workers ${GUNICORN_WORKERS:-3} --timeout 120
