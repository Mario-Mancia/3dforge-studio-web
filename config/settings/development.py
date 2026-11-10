import os

from .base import *  # noqa: F401,F403

DEBUG = os.getenv("DJANGO_DEBUG", "True") == "True"
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "http"

# >>> api
# Pruebas desde el celular por Tailscale: nombres *.ts.net y los hosts de DJANGO_ALLOWED_HOSTS.
ALLOWED_HOSTS += [host for host in [".ts.net"] + lista_env("DJANGO_ALLOWED_HOSTS") if host not in ALLOWED_HOSTS]
# <<< api
