import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


def variable_requerida(nombre):
    valor = os.getenv(nombre)
    if not valor:
        raise ImproperlyConfigured(f"Falta la variable de entorno {nombre}.")
    return valor


def lista_env(nombre, defecto=""):
    return [item.strip() for item in os.getenv(nombre, defecto).split(",") if item.strip()]


SECRET_KEY = variable_requerida("DJANGO_SECRET_KEY")
DEBUG = os.getenv("DJANGO_DEBUG", "False") == "True"
ALLOWED_HOSTS = lista_env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
ADMIN_URL = os.getenv("DJANGO_ADMIN_URL", "admin").strip("/") + "/"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "axes",
    "apps.core",
    "apps.usuarios",
    "apps.clientes",
    "apps.catalogo",
    "apps.cotizaciones",
    "apps.encargos",
    "apps.facturacion",
    "apps.pagos",
    "apps.crm",
    "apps.notificaciones",
]

SITE_ID = 1
AUTH_USER_MODEL = "usuarios.Usuario"

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.negocio",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": dj_database_url.parse(
        variable_requerida("DATABASE_URL"),
        conn_max_age=600,
        conn_health_checks=True,
    )
}
DATABASES["default"]["ATOMIC_REQUESTS"] = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es"
TIME_ZONE = "America/El_Salvador"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.console.EmailBackend",
    },
}

LOGIN_URL = "guest:acceso"
LOGIN_REDIRECT_URL = "customer:panel"
LOGOUT_REDIRECT_URL = "guest:inicio"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 8
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_TRUSTED_ORIGINS = lista_env("DJANGO_CSRF_TRUSTED_ORIGINS")
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
FILE_UPLOAD_PERMISSIONS = 0o640
MAX_ARCHIVO_BYTES = 50 * 1024 * 1024

ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_USER_MODEL_EMAIL_FIELD = "correo"
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_UNIQUE_EMAIL = True
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
        "APP": {
            "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
            "secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
            "key": "",
        },
    }
}

AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=30)
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_PARAMETERS = [["ip_address", "username"]]
AXES_USERNAME_CALLABLE = "apps.usuarios.seguridad.obtener_identificador"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.getenv("DJANGO_LOG_LEVEL", "INFO")},
}

# >>> fases-0-3
from decimal import Decimal

TASA_IMPUESTO = Decimal(os.getenv("TASA_IMPUESTO", "0.13"))
MONEDA = "USD"

ACCOUNT_ADAPTER = "apps.usuarios.adapters.CuentaAdapter"
SOCIALACCOUNT_ADAPTER = "apps.usuarios.adapters.SocialAdapter"
ACCOUNT_FORMS = {"signup": "apps.usuarios.forms.registro.RegistroForm"}
ACCOUNT_SESSION_REMEMBER = None
ACCOUNT_LOGOUT_ON_GET = False
ACCOUNT_PREVENT_ENUMERATION = True
ACCOUNT_LOGOUT_REDIRECT_URL = "guest:inicio"

LOGIN_URL = "guest:acceso"
LOGIN_REDIRECT_URL = "redirigir"
LOGOUT_REDIRECT_URL = "guest:inicio"

AXES_LOCKOUT_TEMPLATE = "errors/bloqueado.html"
IMAGEN_MAX_BYTES = 2 * 1024 * 1024


# --------------------------------------------------------------------------
# CONFIGURACIÓN DE CORREO ELECTRÓNICO
# --------------------------------------------------------------------------

if os.getenv("MAIL_HOST"):
    MAILERS = {
        "default": {
            "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
            "OPTIONS": {
                "host": os.getenv("MAIL_HOST"),
                "port": int(os.getenv("MAIL_PORT", "587")),
                "username": os.getenv("MAIL_USER", ""),
                "password": os.getenv("MAIL_PASSWORD", ""),
                "use_tls": os.getenv("MAIL_USE_TLS", "True") == "True",
                "use_ssl": False,
            },
        },
    }
else:
    MAILERS = {
        "default": {
            "BACKEND": "django.core.mail.backends.console.EmailBackend",
        },
    }

DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    os.getenv("MAIL_USER", "no-responder@3dforge.studio"),
)

SERVER_EMAIL = DEFAULT_FROM_EMAIL


# <<< fases-0-3

# >>> fase-4
PRIVATE_MEDIA_ROOT = Path(os.getenv("PRIVATE_MEDIA_ROOT", str(BASE_DIR / "private_media")))
COTIZACION_VIGENCIA_DIAS = int(os.getenv("COTIZACION_VIGENCIA_DIAS", "15"))
COTIZACION_MAX_ARCHIVOS = 5
# <<< fase-4
