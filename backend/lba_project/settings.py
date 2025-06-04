import os
from pathlib import Path
import environ # For loading .env variables

# Build paths inside the project like this: BASE_DIR / 'subdir'.
# BASE_DIR is AIGENT/backend/
BASE_DIR = Path(__file__).resolve().parent.parent

# Initialize django-environ
env = environ.Env(
    DJANGO_DEBUG=(bool, False) # Set casting and default value for DJANGO_DEBUG
)

# Attempt to read .env file from the project root (AIGENT/.env)
# This is mainly for local development if not using Docker's env_file or if running manage.py locally.
# In Docker, docker-compose's env_file directive handles populating environment variables.
dotenv_path = BASE_DIR.parent / '.env' # Path should be AIGENT/.env
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

    # Third-party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'django_celery_beat', # For Celery Beat (scheduled tasks)

    # Local apps (we will create these in the next steps)
    'users.apps.UsersConfig',     # For the custom User model
    'aigents.apps.AigentsConfig', # For Aigent, Prompt, ChatHistory models
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
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
        'DIRS': [BASE_DIR / 'templates'], # Project-level templates directory
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
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases
DATABASES = {
    'default': env.db('DATABASE_URL') # Reads from DATABASE_URL in .env
}
DATABASES['default']['ENGINE'] = 'django.db.backends.postgresql'


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators
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
# STATIC_ROOT = BASE_DIR / "staticfiles" # Uncomment and configure for production collectstatic

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model (app_name.ModelName)
AUTH_USER_MODEL = 'users.User'

# Django REST Framework Settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    # Add other DRF settings like pagination, permissions later if needed
}

# Simple JWT Settings (optional customization)
# from datetime import timedelta
# SIMPLE_JWT = {
#     'ACCESS_TOKEN_LIFETIME': timedelta(minutes=env.int('JWT_ACCESS_TOKEN_LIFETIME_MINUTES', default=60)),
#     'REFRESH_TOKEN_LIFETIME': timedelta(days=env.int('JWT_REFRESH_TOKEN_LIFETIME_DAYS', default=1)),
#     'ROTATE_REFRESH_TOKENS': False, # If True, a new refresh token is issued when the old one is used
#     'BLACKLIST_AFTER_ROTATION': True, # Requires 'rest_framework_simplejwt.token_blacklist' app if ROTATE_REFRESH_TOKENS is True
#     'UPDATE_LAST_LOGIN': True, # If True, updates the user's last_login field upon successful token refresh
#
#     'ALGORITHM': 'HS256', # Default
#     'SIGNING_KEY': settings.SECRET_KEY, # Default
#     'VERIFYING_KEY': None, # Default
#     'AUDIENCE': None, # Default
#     'ISSUER': None, # Default
#     'JWK_URL': None, # Default
#     'LEEWAY': 0, # Default
#
#     'AUTH_HEADER_TYPES': ('Bearer',), # Default, e.g., "Authorization: Bearer <token>"
#     'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION', # Default
#     'USER_ID_FIELD': 'id', # Default (User model's primary key field name)
#     'USER_ID_CLAIM': 'user_id', # Default
#     'USER_AUTHENTICATION_RULE': 'rest_framework_simplejwt.authentication.default_user_authentication_rule', # Default
#
#     'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',), # Default
#     'TOKEN_TYPE_CLAIM': 'token_type', # Default
#     'TOKEN_USER_CLASS': 'rest_framework_simplejwt.models.TokenUser', # Default
#
#     'JTI_CLAIM': 'jti', # Default
#
#     'SLIDING_TOKEN_REFRESH_EXP_CLAIM': 'refresh_exp', # Default
#     'SLIDING_TOKEN_LIFETIME': timedelta(minutes=5), # Default, for sliding tokens (not used by default)
#     'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=1), # Default, for sliding tokens
# }

# Celery Configuration
CELERY_BROKER_URL = env('CELERY_BROKER_URL')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE # Use Django's timezone
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_TASK_TRACK_STARTED = True # Useful for monitoring task progress

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {filename} {lineno:d} {message}',
            'style': '{',
        },
        'llm_formatter': {
            'format': '{asctime} {levelname} [LLM_INTERACTION] {message}',
            'style': '{',
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        # Paths below are relative to WORKDIR /app in the container
        'app_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/app/app.log', # Log file inside the container at /app/app.log
            'maxBytes': 1024 * 1024 * 5,  # 5 MB
            'backupCount': 3,
            'formatter': 'verbose',
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/app/error.log', # Log file inside the container at /app/error.log
            'maxBytes': 1024 * 1024 * 5,  # 5 MB
            'backupCount': 3,
            'formatter': 'verbose',
        },
        'llm_interaction_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/app/llm_interaction.log', # Log file inside the container at /app/llm_interaction.log
            'maxBytes': 1024 * 1024 * 10,  # 10 MB
            'backupCount': 5,
            'formatter': 'llm_formatter',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'app_file', 'error_file'],
            'level': env('DJANGO_LOG_LEVEL', default='INFO'),
            'propagate': True,
        },
        # Configure loggers for your apps ('users', 'aigents') when they are created
        'users': {
            'handlers': ['console', 'app_file', 'error_file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'aigents': {
            'handlers': ['console', 'app_file', 'error_file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'celery': { # Logger for Celery itself
            'handlers': ['console', 'app_file', 'error_file'],
            'level': 'INFO',
            'propagate': True,
        },
        'llm_logger': { # Custom logger for LLM interactions
            'handlers': ['llm_interaction_file', 'console' if DEBUG else 'llm_interaction_file'],
            'level': 'INFO',
            'propagate': False,
        }
    },
    'root': { # Catch-all for other loggers not explicitly configured
        'handlers': ['console', 'app_file', 'error_file'],
        'level': 'WARNING',
    }
}

# Ollama Settings (loaded from .env)
OLLAMA_DEFAULT_ENDPOINT = env('OLLAMA_DEFAULT_ENDPOINT', default='http://localhost:11434') # Fallback if not in .env