import os

from .base import *  # noqa: F401,F403

DEBUG = os.getenv("DJANGO_DEBUG", "True") == "True"
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "http"

# >>> api
# Pruebas desde el celular por Tailscale: nombres *.ts.net y los hosts de DJANGO_ALLOWED_HOSTS.
ALLOWED_HOSTS += [host for host in [".ts.net"] + lista_env("DJANGO_ALLOWED_HOSTS") if host not in ALLOWED_HOSTS]
# <<< api

# >>> fase-10c
# runserver atiende cada peticion en un hilo nuevo: con conexiones persistentes cada hilo deja una conexion
# abierta hasta 10 minutos y se agota el pool de Supabase (EMAXCONNSESSION: max clients reached in session mode).
# En desarrollo cada conexion se cierra al terminar la peticion.
DATABASES["default"]["CONN_MAX_AGE"] = 0
DATABASES["default"]["CONN_HEALTH_CHECKS"] = False
# <<< fase-10c
