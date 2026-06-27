web: gunicorn smartspend_project.wsgi:application --bind 0.0.0.0:$PORT --workers 4 --worker-class gthread --timeout 120
worker: celery -A smartspend_project worker --loglevel=info
