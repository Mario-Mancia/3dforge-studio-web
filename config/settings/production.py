from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import lista_env

DEBUG = False

ALLOWED_HOSTS = lista_env("DJANGO_ALLOWED_HOSTS")
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS es obligatorio en produccion.")

SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"
