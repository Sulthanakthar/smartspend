#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "==> Running database migrations..."
python manage.py migrate --noinput

echo "==> Starting Celery background worker..."
celery -A smartspend_project worker --loglevel=info &

echo "==> Starting Daphne ASGI web server on port ${PORT:-8000}..."
exec daphne -b 0.0.0.0 -p ${PORT:-8000} smartspend_project.asgi:application
