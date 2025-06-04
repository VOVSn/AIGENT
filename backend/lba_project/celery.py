import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
# This must come before creating the Celery app instance.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lba_project.settings')

# Create the Celery application instance.
# 'lba_project' is the name of our Django project.
app = Celery('lba_project')

# Configure Celery using settings from Django settings.py.
# The namespace='CELERY' means all Celery configuration keys
# in settings.py should be prefixed with "CELERY_" (e.g., CELERY_BROKER_URL).
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover task modules from all registered Django apps.
# Celery will look for a tasks.py file in each app.
app.autodiscover_tasks()

# Example debug task (optional, can be removed later)
@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Celery Request: {self.request!r}')