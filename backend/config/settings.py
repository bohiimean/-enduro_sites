"""Настройки Django. Всё окружение читается из переменных, значения по
умолчанию рассчитаны на локальный docker-compose."""
import os
import sys
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


def _list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = _list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,backend")
CSRF_TRUSTED_ORIGINS = _list("DJANGO_CSRF_TRUSTED_ORIGINS", "http://localhost:8080")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    # Регистрация, вход, подтверждение почты и сброс пароля. socialaccount не
    # ставим сознательно: соцвход не нужен, а headless — это JSON-API для SPA
    # на обычных сессиях Django, то есть ровно наша схема с httpOnly-cookie.
    "allauth",
    "allauth.account",
    "allauth.headless",
    "accounts",
    "catalog",
    "orders",
    "payments",
    "pricing",
    "worker",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Обязательна начиная с allauth 65: без неё приложение не проходит check.
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # Тут лежат русские письма allauth (templates/account/email/*).
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": dj_database_url.parse(
        os.environ.get("DATABASE_URL", "postgres://enduro:enduro@postgres:5432/enduro"),
        conn_max_age=60,
    )
}

# Кеш на таблице PostgreSQL, а не LocMem. Лимиты попыток входа и будущий
# rate-limit на запрос статуса KYC должны быть общими для всех процессов
# gunicorn — в LocMem они размножились бы по числу воркеров. Таблица создаётся
# командой `manage.py createcachetable` (она в command бэкенда в compose).
# Redis для этого по-прежнему не нужен.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
    }
}

AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = [
    # Нужен для входа в админку и для проверки прав.
    "django.contrib.auth.backends.ModelBackend",
    # Вход по почте для пользователей сайта.
    "allauth.account.auth_backends.AuthenticationBackend",
    # Сюда добавится вход по номеру телефона (этап 6). USERNAME_FIELD задаёт
    # только способ по умолчанию, поэтому второй бэкенд не требует ни миграций,
    # ни переделки сессий. Пускать он будет только подтверждённые номера.
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Вход и регистрация (allauth) -------------------------------------------
# Логин — почта. Номер телефона остаётся ключом KYC у alfabit и появится вторым
# способом входа на этапе 6 (CLAUDE.md, «Личный кабинет»).
ACCOUNT_LOGIN_METHODS = {"email"}
# У нашего пользователя нет поля username, и allauth об этом надо сказать прямо:
# по умолчанию он лезет за User._meta.get_field("username") и падает на
# регистрации с FieldDoesNotExist.
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_USER_MODEL_EMAIL_FIELD = "email"
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
# Ворота жёсткие: до подтверждения адреса вход не пускает. Отсюда следует, что
# повторная отправка письма обязана работать без входа — иначе сбой SMTP
# запирает пользователя насмерть. В headless это `POST /_allauth/browser/v1/
# auth/email/verify/resend`, доступный неавторизованной сессии.
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
# Подтверждение кодом, а не ссылкой (решено 27.09.2026). Причина не в красоте:
# в режиме ссылки allauth не заводит человека в кабинет после перехода — и не
# должен, иначе любой, кому попало письмо, получает вход. Код вводится в той же
# вкладке, где шла регистрация, поэтому вход после подтверждения безопасен и
# происходит сам (см. flows/email_verification.login_on_verification).
# Заодно: работает с телефона, где почта открывает ссылки в своём браузере;
# появляется штатная кнопка «прислать заново» (в режиме ссылки её нет вообще);
# и в письме больше нет URL — то есть домен и порт в нём сломаться не могут.
# Код живёт 15 минут, на ввод три попытки (значения allauth по умолчанию).
ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED = True
# По умолчанию allauth выдаёт восемь заглавных латинских букв с дефисом
# («GWPH-WRRF»). Нам нужны цифры: на телефоне открывается цифровая клавиатура,
# и такой код проще продиктовать по телефону, если человек позвонит менеджеру.
ACCOUNT_EMAIL_VERIFICATION_BY_CODE_FORMAT = {"length": 6, "numeric": True, "dashed": False}
# Переотправка кода по умолчанию ВЫКЛЮЧЕНА: квота нулевая, и эндпоинт
# `auth/email/verify/resend` отвечает 409, ничего не объясняя. Имя настройки при
# этом не «...MAX_RESEND_COUNT» — то читается из этого значения. Три кода на одну
# попытку: дальше человек входит заново, и отсчёт начинается с нуля.
ACCOUNT_EMAIL_VERIFICATION_SUPPORTS_RESEND = 3
ACCOUNT_UNIQUE_EMAIL = True
# Не подсказывать, зарегистрирован ли адрес.
ACCOUNT_PREVENT_ENUMERATION = True
# Пустой префикс: тема письма пишется в шаблоне по-русски, «[example.com]»
# в ней не нужен.
ACCOUNT_EMAIL_SUBJECT_PREFIX = ""
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "http" if DEBUG else "https"
# Лимиты. Живут в кеше — поэтому кеш обязан быть общим для всех процессов
# gunicorn, см. CACHES выше.
#
# `confirm_email` здесь сознательно не переопределяется. Это пауза между
# отправками письма с кодом, и allauth сам подбирает её под режим: для кода —
# одно письмо в 10 секунд на адрес. Своё значение тут вредит: кнопка «прислать
# заново» должна работать, когда человек её нажал, а код и так живёт 15 минут.
ACCOUNT_RATE_LIMITS = {
    "login_failed": "5/5m/ip,5/5m/key",
    "signup": "10/h/ip",
    "reset_password": "5/h/ip,3/h/key",
}

# Классических страниц входа у нас нет — только JSON-API для Nuxt.
HEADLESS_ONLY = True
# Ссылки в письмах ведут на фронтенд, а не в Django. Пути относительные:
# allauth сам достроит их до абсолютных по хосту запроса, поэтому домен
# нигде не зашит и на локальной машине письма работают без настройки.
HEADLESS_FRONTEND_URLS = {
    # Нужен только режиму подтверждения ссылкой, который мы выключили: в письме
    # с кодом никакого URL нет. Запись оставлена потому, что при HEADLESS_ONLY
    # allauth требует её наличия. Если когда-нибудь вернёмся к ссылке — под этот
    # путь придётся вернуть и страницу с ключом в адресе.
    "account_confirm_email": "/account/verify-email/{key}",
    "account_reset_password": "/account/password/reset",
    "account_reset_password_from_key": "/account/password/reset/{key}",
    "account_signup": "/account/signup",
}

# --- Почта ------------------------------------------------------------------
# Письма уходят синхронно, прямо в HTTP-запросе (таблица-outbox отклонена как
# лишняя при наших объёмах). Поэтому таймаут короткий: провайдер не должен
# подвешивать регистрацию. Страховка от потерянного письма — кнопка повторной
# отправки, работающая без входа.
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend"
    if DEBUG
    else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "1") == "1"
EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT", "5"))
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@localhost")

LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    # Аутентификация — сессия в httpOnly-cookie. SessionAuthentication сама
    # требует CSRF-токен на небезопасных методах.
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    # Закрыто по умолчанию: публичное (курс, каталог, health) открывается явно
    # через permission_classes. Иначе забытый эндпоинт кабинета молча
    # оказывается публичным.
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 20,
}

# --- Cookie и HTTPS ---------------------------------------------------------
# Nuxt и Django стоят за одним nginx, origin один — CORS не нужен вообще.
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
# Остаётся False умышленно: фронтенд читает csrftoken из cookie и кладёт его
# в заголовок X-CSRFToken. Сессия при этом httpOnly, а CSRF-токен секретом
# не является.
CSRF_COOKIE_HTTPONLY = False
# Мы за nginx: без этого Django считает соединение незашифрованным и ломает
# и secure-cookie, и проверку CSRF-origin.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Фоновые задачи (worker). На этапе 1 расписание пустое.
RATE_SERVICE_URL = os.environ.get("RATE_SERVICE_URL", "")
RATE_SERVICE_TOKEN = os.environ.get("RATE_SERVICE_TOKEN", "")
RATE_REFRESH_MINUTES = int(os.environ.get("RATE_REFRESH_MINUTES", "20"))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {"format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "default"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}

# В тестах каждый ожидаемый 401/403 пишет WARNING в django.request, и за этим
# шумом не видно итога прогона.
if "test" in sys.argv[1:2]:
    LOGGING["loggers"] = {
        "django.request": {"level": "ERROR"},
        # Тест на запрос без CSRF-токена отказ ждёт — предупреждение лишнее.
        "django.security.csrf": {"level": "ERROR"},
    }
