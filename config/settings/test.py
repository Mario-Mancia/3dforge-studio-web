from .base import *  # noqa: F401,F403


TEST_RUNNER = "config.test_runner.CleanConnectionsRunner"

# --------------------------------------------------------------------------
# CONFIGURACIÓN DE BASE DE DATOS
# --------------------------------------------------------------------------

DATABASES["default"]["CONN_MAX_AGE"] = 0
DATABASES["default"]["CONN_HEALTH_CHECKS"] = False


# --------------------------------------------------------------------------
# CONFIGURACIÓN DE CORREO
# --------------------------------------------------------------------------

MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.locmem.EmailBackend",
    },
}


# --------------------------------------------------------------------------
# CONFIGURACIÓN GENERAL
# --------------------------------------------------------------------------

DEBUG = False
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# --------------------------------------------------------------------------
# CONFIGURACIÓN DE CONEXIONES
# --------------------------------------------------------------------------

DATABASES["default"]["CONN_MAX_AGE"] = 0
DATABASES["default"]["CONN_HEALTH_CHECKS"] = False