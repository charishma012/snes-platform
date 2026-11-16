import os
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
load_dotenv(BASE_DIR / '.env')

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

DEBUG = os.getenv('DJANGO_DEBUG', 'True').lower() in ('true', '1', 't')

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'django-insecure-dev-fallback-key'
    else:
        raise ImproperlyConfigured('DJANGO_SECRET_KEY environment variable is required when DJANGO_DEBUG=False.')

# Allowed Hosts & CSRF Trusted Origins
raw_hosts = os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,.onrender.com')
ALLOWED_HOSTS = [
    host.strip()
    for host in raw_hosts.split(',')
    if host.strip()
]
if 'testserver' not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append('testserver')

raw_csrf = os.getenv('DJANGO_CSRF_TRUSTED_ORIGINS', 'https://*.onrender.com')
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in raw_csrf.split(',')
    if origin.strip()
]

# Security settings & SSL hardening
X_FRAME_OPTIONS = 'SAMEORIGIN'

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'True').lower() in ('true', '1', 't')

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party apps
    'django_htmx',
    'storages',
    # Local apps
    'notes',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
]

ROOT_URLCONF = 'config.urls'

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

WSGI_APPLICATION = 'config.wsgi.application'

# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    'default': dj_database_url.config(
        default=os.getenv('DATABASE_URL', f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
    )
}

# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images) & WhiteNoise
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Media files & Storage backends (Local vs. S3/Supabase)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

USE_S3_STORAGE = os.getenv('USE_S3_STORAGE', 'False').lower() in ('true', '1', 't')

if USE_S3_STORAGE:
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_ENDPOINT_URL = os.getenv('AWS_S3_ENDPOINT_URL')
    AWS_S3_REGION_NAME = os.getenv('AWS_S3_REGION_NAME', 'auto')
    AWS_QUERYSTRING_AUTH = False

    # Build Supabase public delivery domain automatically from endpoint URL
    AWS_S3_CUSTOM_DOMAIN = os.getenv('AWS_S3_CUSTOM_DOMAIN') or None
    if not AWS_S3_CUSTOM_DOMAIN and AWS_S3_ENDPOINT_URL and '.supabase.co' in AWS_S3_ENDPOINT_URL:
        project_host = AWS_S3_ENDPOINT_URL.split('//')[1].split('/')[0]
        AWS_S3_CUSTOM_DOMAIN = f"{project_host}/storage/v1/object/public/{AWS_STORAGE_BUCKET_NAME}"

    s3_options = {
        'access_key': AWS_ACCESS_KEY_ID,
        'secret_key': AWS_SECRET_ACCESS_KEY,
        'bucket_name': AWS_STORAGE_BUCKET_NAME,
        'endpoint_url': AWS_S3_ENDPOINT_URL,
        'region_name': AWS_S3_REGION_NAME,
        'querystring_auth': AWS_QUERYSTRING_AUTH,
        'addressing_style': 'path',
    }
    if AWS_S3_CUSTOM_DOMAIN:
        s3_options['custom_domain'] = AWS_S3_CUSTOM_DOMAIN

    STORAGES = {
        'default': {
            'BACKEND': 'storages.backends.s3.S3Storage',
            'OPTIONS': s3_options,
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
        },
    }

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Authentication redirects
LOGIN_URL = 'notes:login'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'
