try:
    from celery import Celery
    import os
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartspend_project.settings')
    app = Celery('smartspend_project')
    app.config_from_object('django.conf:settings', namespace='CELERY')
    app.autodiscover_tasks()
except ImportError:
    app = None
