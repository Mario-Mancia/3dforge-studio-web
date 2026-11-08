import os

from .base import *  # noqa: F401,F403

DEBUG = os.getenv("DJANGO_DEBUG", "True") == "True"
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "http"
