from pathlib import Path
from datetime import timedelta
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-change-me-in-production')
DEBUG = os.getenv('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    # Jazzmin admin
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third party
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'channels',

    # Local apps
    'users',
    'chat',
    'practice',
    'ielts_mock',
    'cefr_mock',
    'vocabulary',
    'premium',
    'leaderboard',
    'notifications',
    'webapp',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    }
}

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_USER_MODEL = 'users.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Tashkent'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# JWT
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=7),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
    'ROTATE_REFRESH_TOKENS': True,
}

# CORS
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

# CSRF & Session — Telegram WebApp / ngrok uchun
CSRF_TRUSTED_ORIGINS = [
    'https://*.ngrok-free.app',
    'https://*.ngrok.io',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_HTTPONLY = False   # JS cookie'ni o'qiy olsin
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = 'ALLOWALL'  # Telegram WebApp iframe ichida ishlaydi

# OpenAI
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
BOT_SECRET = os.getenv('BOT_SECRET', 'speaking-bot-secret-key-2024')
ADMIN_CHAT_IDS = os.getenv('ADMIN_CHAT_IDS', '')

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_PAYMENT_CHAT = os.getenv('TELEGRAM_PAYMENT_CHAT', '@nodirbek_shukurov1')
BOT_USERNAME = os.getenv('BOT_USERNAME', '')

# Free limits
FREE_CHAT_SEARCH_LIMIT = 2

# Web App
WEBAPP_URL = os.getenv('WEBAPP_URL', 'http://localhost:8000/webapp/')

# Jazzmin admin panel
JAZZMIN_SETTINGS = {
    "site_title": "Speaking Bot Admin",
    "site_header": "🎓 Speaking Bot",
    "site_brand": "Speaking Bot",
    "welcome_sign": "Xush kelibsiz, Admin!",
    "copyright": "Speaking Bot © 2024",
    "search_model": ["users.User", "users.BotActivity"],
    "topmenu_links": [
        {"name": "Bosh sahifa", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"name": "Foydalanuvchilar", "url": "admin:users_user_changelist"},
        {"name": "Bot Faoliyat", "url": "admin:users_botactivity_changelist"},
    ],
    "usermenu_links": [
        {"name": "Profilim", "url": "admin:users_user_change", "icon": "fas fa-user"},
    ],
    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [],
    "hide_models": [],
    "order_with_respect_to": [
        "users", "users.User", "users.BotActivity", "users.Referral",
        "webapp", "webapp.AppSettings", "webapp.PaymentCard", "webapp.RequiredChannel",
        "webapp.VoiceRoom", "webapp.VoiceRating",
        "ielts_mock", "cefr_mock", "vocabulary",
        "premium", "notifications",
    ],
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "users.User": "fas fa-user-graduate",
        "users.BotActivity": "fas fa-chart-bar",
        "users.Referral": "fas fa-share-alt",
        "ielts_mock.IELTSQuestion": "fas fa-file-alt",
        "ielts_mock.IELTSSession": "fas fa-clipboard-check",
        "cefr_mock.CEFRQuestion": "fas fa-tasks",
        "cefr_mock.CEFRSession": "fas fa-star",
        "vocabulary.Word": "fas fa-book",
        "vocabulary.UserWord": "fas fa-bookmark",
        "premium.PremiumPlan": "fas fa-crown",
        "premium.PremiumPurchase": "fas fa-shopping-cart",
        "notifications.Broadcast": "fas fa-bullhorn",
        "notifications.DailyReport": "fas fa-calendar-check",
        "webapp": "fas fa-mobile-alt",
        "webapp.AppSettings": "fas fa-cog",
        "webapp.PaymentCard": "fas fa-credit-card",
        "webapp.RequiredChannel": "fas fa-broadcast-tower",
        "webapp.VoiceRoom": "fas fa-phone",
        "webapp.VoiceRating": "fas fa-star",
    },
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
    "related_modal_active": False,
    "custom_css": "admin/custom.css",
    "custom_js": None,
    "use_google_fonts_cdn": True,
    "show_ui_builder": False,
    "changeform_format": "horizontal_tabs",
    "changeform_format_overrides": {
        "auth.user": "collapsible",
        "auth.group": "vertical_tabs",
    },
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-primary",
    "accent": "accent-primary",
    "navbar": "navbar-dark",
    "no_navbar_border": False,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-primary",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "darkly",
    "dark_mode_theme": "darkly",
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },
}
