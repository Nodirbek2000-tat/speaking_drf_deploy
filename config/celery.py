import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('speaking_drf')

# settings.py dagi CELERY_ prefikslı config larni o'qiydi
app.config_from_object('django.conf:settings', namespace='CELERY')

# Barcha Django app lardan tasks.py larni avtomatik topadi
app.autodiscover_tasks()
