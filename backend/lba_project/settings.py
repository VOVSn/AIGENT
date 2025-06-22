# backend/lba_project/settings.py

import os
from pathlib import Path
import environ # For loading .env variables

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Initialize django-environ
env = environ.Env(
    DJANGO_DEBUG=(bool, False) # Set casting and default value for DJANGO_DEBUG
)

# Attempt to read .env file from the project root
dotenv_path = BASE_DIR.parent / '.env'
if dotenv_path.exists():
    environ.Env.read_env(str(dotenv_path))

# Django Core Settings
SECRET_KEY = env('DJANGO_SECRET_KEY')
DEBUG = env('DJANGO_DEBUG')

ALLOWED_HOSTS_str = env('DJANGO_ALLOWED_HOSTS', default='localhost 127.0.0.1')
ALLOWED_HOSTS = ALLOWED_HOSTS_str.split(' ')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt',
    'django_celery_beat',
    'users.apps.UsersConfig',
    'aigents.apps.AigentsConfig',
    'tools.apps.ToolsConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'lba_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'lba_project.wsgi.application'

# Database
DATABASES = {
    'default': env.db('DATABASE_URL')
}
DATABASES['default']['ENGINE'] = 'django.db.backends.postgresql'


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    # BASE_DIR / "static",
]

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'users.User'

# Django REST Framework Settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
}

# Celery Configuration
CELERY_BROKER_URL = env('CELERY_BROKER_URL')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_TASK_TRACK_STARTED = True

# --- NEW, SIMPLIFIED LOGGING CONFIGURATION ---
# This configuration ONLY logs to the console (stdout/stderr), which is the
# standard Docker practice. This completely avoids file permission and
# file-vs-directory issues with volume mounts.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        # Handler for all logs EXCEPT the LLM interactions. Outputs to console.
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        # Handler specifically for LLM interactions. Outputs to a file.
        'llm_file': {
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'llm_interaction.log', # Correct path inside the container
            'formatter': 'verbose',
        },
    },
    'loggers': {
        # Standard Django logger
        'django': {
            'handlers': ['console'],
            'level': env('DJANGO_LOG_LEVEL', default='INFO'),
            'propagate': True,
        },
        # General application loggers
        'users': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'aigents': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'celery': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
        # The special logger for LLM interactions
        'llm_logger': {
            'handlers': ['llm_file'], # <-- This is the key change
            'level': 'INFO',
            'propagate': False, # <-- Crucial: prevents logs from also going to console
        }
    },
    # Root logger catches everything else
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    }
}

# Ollama Settings
OLLAMA_DEFAULT_ENDPOINT = env('OLLAMA_DEFAULT_ENDPOINT', default='http://localhost:11434')

# CORS Configuration
CORS_ALLOWED_ORIGINS = [
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "https://aigent.vovsn.com", # Add your production domain
]
CORS_ALLOW_CREDENTIALS = True

# --- SECURITY SETTINGS FOR REVERSE PROXY ---
# This tells Django to trust the 'X-Forwarded-Proto' header from our Nginx proxy
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# This tells Django that any cookie it sets as "secure" is safe to use.
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# This is the most important setting: It tells Django which domains are allowed
# to make POST requests.
CSRF_TRUSTED_ORIGINS = [
    'https://aigent.vovsn.com',
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]