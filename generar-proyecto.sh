#!/usr/bin/env bash
set -Eeuo pipefail

readonly RAIZ_POR_DEFECTO="/home/mmancia/Projects/Web/3dforge-studio/3dforge-studio-web"

RAIZ=""
DIR_ACTUAL=""
RESPALDO=""
INSTALAR=0
MIGRAR=1
CREADOS=0
ACTUALIZADOS=0
SIN_CAMBIOS=0
OMITIDOS=0
AVISOS=()

info() { printf '[INFO] %s\n' "$*"; }
ok() { printf '[ OK ] %s\n' "$*"; }
advertir() { printf '[AVISO] %s\n' "$*" >&2; AVISOS+=("$*"); }
fallar() { printf '[ERROR] %s\n' "$*" >&2; exit 1; }

ayuda() {
    cat <<'__FIN__'
Uso: generar-proyecto.sh [opciones] [RAIZ_DEL_PROYECTO]

  --instalar          instala requirements.txt en el entorno activo (.venv)
  --sin-migraciones   no ejecuta makemigrations al final
  -h, --ayuda         muestra esta ayuda

Capa de datos y configuracion: se regeneran con respaldo en .respaldo/.
Vistas, plantillas, formularios, servicios y selectores: solo se crean si faltan.
__FIN__
}

validar_ruta() {
    local r="$1"
    [[ -n $r && $r != /* && $r != *..* && $r =~ ^[A-Za-z0-9_./-]+$ ]] || fallar "Ruta no permitida: '$r'"
}

rel_actual() { printf '%s' "${DIR_ACTUAL:+$DIR_ACTUAL/}$1"; }

ir_raiz() {
    DIR_ACTUAL=""
    cd -- "$RAIZ"
}

ir_a() {
    validar_ruta "$1"
    mkdir -p -- "$RAIZ/$1"
    cd -- "$RAIZ/$1"
    DIR_ACTUAL="$1"
}

leer() {
    local rel
    rel="$(rel_actual "$1")"
    validar_ruta "$rel"
    [[ -f "$RAIZ/$rel" ]] || return 1
    cat -- "$RAIZ/$rel"
}

respaldar() {
    local rel="$1"
    [[ -n $RESPALDO ]] || RESPALDO="$RAIZ/.respaldo/$(date +%Y%m%d-%H%M%S)"
    mkdir -p -- "$(dirname -- "$RESPALDO/$rel")"
    cp -p -- "$RAIZ/$rel" "$RESPALDO/$rel"
}

eliminar() {
    local rel
    rel="$(rel_actual "$1")"
    validar_ruta "$rel"
    [[ -f "$RAIZ/$rel" ]] || return 0
    respaldar "$rel"
    rm -f -- "$RAIZ/$rel"
}

escribir() {
    local rel destino tmp
    rel="$(rel_actual "$1")"
    validar_ruta "$rel"
    destino="$RAIZ/$rel"
    tmp="$(mktemp)"
    cat >"$tmp"
    mkdir -p -- "$(dirname -- "$destino")"
    if [[ -e $destino ]]; then
        if cmp -s -- "$tmp" "$destino"; then
            rm -f -- "$tmp"
            SIN_CAMBIOS=$((SIN_CAMBIOS + 1))
            return 0
        fi
        respaldar "$rel"
        rm -f -- "$destino"
        ACTUALIZADOS=$((ACTUALIZADOS + 1))
    else
        CREADOS=$((CREADOS + 1))
    fi
    mv -- "$tmp" "$destino"
    chmod 0644 -- "$destino"
}

crear_si_falta() {
    local rel destino
    rel="$(rel_actual "$1")"
    validar_ruta "$rel"
    destino="$RAIZ/$rel"
    if [[ -e $destino ]]; then
        cat >/dev/null
        OMITIDOS=$((OMITIDOS + 1))
        return 0
    fi
    escribir "$1"
}

vacio() { escribir "$1" </dev/null; }
vacio_si_falta() { crear_si_falta "$1" </dev/null; }

asegurar_lineas() {
    local archivo="$1" contenido="" linea
    shift
    [[ -f "$RAIZ/$archivo" ]] && contenido="$(<"$RAIZ/$archivo")"
    for linea in "$@"; do
        grep -qxF -- "$linea" <<<"$contenido" || contenido+=$'\n'"$linea"
    done
    printf '%s\n' "${contenido#$'\n'}" | escribir "$archivo"
}

asegurar_claves() {
    local archivo="$1" contenido="" clave
    shift
    [[ -f "$RAIZ/$archivo" ]] && contenido="$(<"$RAIZ/$archivo")"
    for clave in "$@"; do
        grep -q -- "^${clave}=" <<<"$contenido" || contenido+=$'\n'"${clave}="
    done
    printf '%s\n' "${contenido#$'\n'}" | escribir "$archivo"
}

resolver_raiz() {
    local candidato="${1:-}" aqui
    if [[ -z $candidato ]]; then
        aqui="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
        if [[ -f "$aqui/manage.py" ]]; then
            candidato="$aqui"
        elif [[ -f "$PWD/manage.py" ]]; then
            candidato="$PWD"
        else
            candidato="$RAIZ_POR_DEFECTO"
        fi
    fi
    [[ -d $candidato ]] || fallar "No existe el directorio raiz: $candidato"
    RAIZ="$(cd -- "$candidato" && pwd -P)"
    [[ -f "$RAIZ/manage.py" && -d "$RAIZ/config" ]] || fallar "No parece la raiz del proyecto Django: $RAIZ"
}

crear_app() {
    local app="$1" etiqueta="$2"
    ir_a "apps/$app"
    vacio "__init__.py"
    vacio "migrations/__init__.py"
    [[ ${3:-} == sin_apps ]] && return 0
    printf 'from django.apps import AppConfig\n\n\nclass %sConfig(AppConfig):\n    default_auto_field = "django.db.models.BigAutoField"\n    name = "apps.%s"\n    verbose_name = "%s"\n' "${app^}" "$app" "$etiqueta" | escribir "apps.py"
}

capas_app() {
    local app="$1"
    shift
    local lista="$*"
    local importacion="from apps.${app}.models import ${lista// /, }"
    vacio_si_falta "selectors/__init__.py"
    vacio_si_falta "services/__init__.py"
    vacio_si_falta "forms/__init__.py"
    printf 'from django.db.models import QuerySet\n\n%s\n' "$importacion" | crear_si_falta "selectors/${app}.py"
    printf 'from django.db import transaction\n\n%s\n' "$importacion" | crear_si_falta "services/${app}.py"
    printf 'from django import forms\n\n%s\n' "$importacion" | crear_si_falta "forms/${app}.py"
}

# ============================================================
# PASO 1: DEPENDENCIAS Y ARCHIVOS DE ENTORNO
# ============================================================

paso_dependencias() {
    info "Dependencias y archivos de entorno"
    ir_raiz
    local paquetes=("Django" "dj-database-url" "python-dotenv" "psycopg[binary]" "django-allauth[socialaccount]" "django-axes")
    local contenido="" paquete nombre patron
    if [[ -f requirements.txt ]]; then
        if ! tr -d '\000' <requirements.txt | cmp -s - requirements.txt; then
            contenido="$(iconv -f UTF-16 -t UTF-8 requirements.txt | tr -d '\r')"
        else
            contenido="$(tr -d '\r' <requirements.txt)"
        fi
    fi
    local normal
    normal="$(printf '%s' "$contenido" | tr '_' '-')"
    for paquete in "${paquetes[@]}"; do
        nombre="${paquete%%\[*}"
        patron="^${nombre}([[:space:]]|\\[|=|<|>|~|!|;|\$)"
        [[ $nombre == psycopg ]] && patron="^psycopg"
        if ! grep -iqE -- "$patron" <<<"$normal"; then
            contenido+=$'\n'"$paquete"
        fi
    done
    printf '%s\n' "${contenido#$'\n'}" | escribir "requirements.txt"
    asegurar_lineas ".gitignore" ".respaldo/" "media/" "staticfiles/" "logs/" ".env"
    asegurar_claves ".env.example" DJANGO_SECRET_KEY DJANGO_DEBUG DJANGO_ENV DJANGO_ALLOWED_HOSTS \
        DJANGO_CSRF_TRUSTED_ORIGINS DJANGO_ADMIN_URL DATABASE_URL GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET
}

# ============================================================
# PASO 2: CONFIGURACION (settings por entorno, urls, manage/asgi/wsgi)
# ============================================================

paso_configuracion() {
    info "Configuracion del proyecto"
    ir_a "config"

    if leer settings.py >/dev/null 2>&1; then
        leer settings.py | grep -q "dj_database_url" || advertir "settings.py original sin dj_database_url; se reemplaza igualmente (respaldo en .respaldo/)"
        eliminar settings.py
    fi

    ir_a "config/settings"
    vacio "__init__.py"

    escribir "base.py" <<'__FIN__'
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
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-responder@3dforge.studio")

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
__FIN__

    escribir "development.py" <<'__FIN__'
import os

from .base import *  # noqa: F401,F403

DEBUG = os.getenv("DJANGO_DEBUG", "True") == "True"
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "http"
__FIN__

    escribir "production.py" <<'__FIN__'
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
__FIN__

    ir_a "config"
    escribir "urls.py" <<'__FIN__'
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("cuenta/", include("allauth.urls")),
    path("", include("apps.portal.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
__FIN__

    local contenido
    ir_raiz
    local viejo="'config.settings')" nuevo
    nuevo="'config.settings.development')"
    contenido="$(leer manage.py)"
    printf '%s\n' "${contenido//"$viejo"/$nuevo}" | escribir "manage.py"
    chmod 0755 -- "$RAIZ/manage.py"
    ir_a "config"
    for archivo in asgi.py wsgi.py; do
        nuevo="'config.settings.production')"
        contenido="$(leer "$archivo")"
        printf '%s\n' "${contenido//"$viejo"/$nuevo}" | escribir "$archivo"
    done
}

# ============================================================
# PASO 3: CAPA DE DATOS
# ============================================================

app_core() {
    info "App core"
    crear_app core "Nucleo" sin_apps
    printf 'from django.apps import AppConfig\nfrom django.db.models.signals import post_migrate\n\n\nclass CoreConfig(AppConfig):\n    default_auto_field = "django.db.models.BigAutoField"\n    name = "apps.core"\n    verbose_name = "Nucleo"\n\n    def ready(self):\n        from apps.core.seeds import sembrar_datos_iniciales\n\n        post_migrate.connect(\n            sembrar_datos_iniciales,\n            sender=self,\n            dispatch_uid="apps.core.sembrar_datos_iniciales",\n        )\n' | escribir "apps.py"

    escribir "constants.py" <<'__FIN__'
from decimal import Decimal

CENTAVO = Decimal("0.01")
FORMATOS_ARCHIVO = ("STL", "OBJ", "3MF", "STEP", "PNG", "JPG", "PDF")
MAX_ARCHIVO_BYTES = 52428800
MAX_JSON_BYTES = 100000
__FIN__

    escribir "validators.py" <<'__FIN__'
import json
import re
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator

from apps.core.constants import MAX_ARCHIVO_BYTES, MAX_JSON_BYTES

validar_nombre_persona = RegexValidator(
    regex=r"^[^\W\d_]+(?:[ '\-.][^\W\d_]+)*$",
    message="Use solo letras, espacios, apostrofes, guiones o puntos.",
    code="nombre_invalido",
)
validar_telefono = RegexValidator(
    regex=r"^\+?[0-9][0-9 \-()]{6,24}$",
    message="Ingrese un telefono valido.",
    code="telefono_invalido",
)
validar_identificacion_fiscal = RegexValidator(
    regex=r"^[A-Za-z0-9][A-Za-z0-9 .\-]{3,29}$",
    message="Identificacion fiscal no valida.",
    code="identificacion_invalida",
)
validar_codigo = RegexValidator(
    regex=r"^[A-Za-z0-9][A-Za-z0-9\-_/]{2,39}$",
    message="Use letras, numeros, guiones, guion bajo o barra (3 a 40 caracteres).",
    code="codigo_invalido",
)

importe_no_negativo = MinValueValidator(Decimal("0"))
cantidad_minima = MinValueValidator(Decimal("0.01"))


def validar_ruta_relativa(valor):
    texto = str(valor)
    partes = re.split(r"[\\/]", texto)
    if (
        not texto
        or len(texto) > 500
        or texto != texto.strip()
        or texto.startswith(("/", "\\", "~"))
        or re.match(r"^[A-Za-z]:", texto)
        or "://" in texto
        or any(parte in ("", ".", "..") for parte in partes)
        or any(ord(caracter) < 32 for caracter in texto)
    ):
        raise ValidationError("Ruta de archivo no permitida.", code="ruta_invalida")


def validar_nombre_archivo(valor):
    texto = str(valor)
    if (
        not texto
        or texto != texto.strip()
        or texto.startswith(".")
        or re.search(r"[\\/\x00-\x1f]", texto)
    ):
        raise ValidationError("Nombre de archivo no permitido.", code="archivo_invalido")


def validar_tamano_archivo(valor):
    maximo = getattr(settings, "MAX_ARCHIVO_BYTES", MAX_ARCHIVO_BYTES)
    if valor > maximo:
        raise ValidationError(f"El archivo supera el maximo permitido de {maximo} bytes.", code="archivo_grande")


def validar_objeto_json(valor):
    if valor is None:
        return
    if not isinstance(valor, dict):
        raise ValidationError("Debe ser un objeto JSON.", code="json_invalido")
    try:
        longitud = len(json.dumps(valor, ensure_ascii=False))
    except (TypeError, ValueError):
        raise ValidationError("El objeto JSON no es serializable.", code="json_invalido")
    if longitud > MAX_JSON_BYTES:
        raise ValidationError("El objeto JSON es demasiado grande.", code="json_grande")
__FIN__

    escribir "calculos.py" <<'__FIN__'
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from apps.core.constants import CENTAVO


def redondear(valor):
    return Decimal(valor).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def importes_coherentes(subtotal, descuento, impuesto, total):
    try:
        esperado = redondear(subtotal) - redondear(descuento) + redondear(impuesto)
        return esperado == redondear(total)
    except (InvalidOperation, TypeError, ValueError):
        return True
__FIN__

    escribir "fields.py" <<'__FIN__'
from django.db import models

from apps.core.validators import cantidad_minima, importe_no_negativo


def dinero(**kwargs):
    return models.DecimalField(max_digits=12, decimal_places=2, validators=[importe_no_negativo], **kwargs)


def cantidad_decimal(**kwargs):
    return models.DecimalField(max_digits=10, decimal_places=2, validators=[cantidad_minima], **kwargs)
__FIN__

    escribir "constraints.py" <<'__FIN__'
from functools import reduce
from operator import and_

from django.db.models import CheckConstraint, Q


def en_lista(nombre, campo, valores):
    return CheckConstraint(condition=Q(**{f"{campo}__in": list(valores)}), name=nombre)


def no_negativos(*campos):
    return reduce(and_, (Q(**{f"{campo}__gte": 0}) for campo in campos))


def restriccion(nombre, condicion):
    return CheckConstraint(condition=condicion, name=nombre)
__FIN__

    escribir "admin_utils.py" <<'__FIN__'
from django.contrib import admin


def registrar(*modelos, **opciones):
    for modelo in modelos:
        atributos = {
            "list_display": [campo.name for campo in modelo._meta.concrete_fields][:6],
            "list_per_page": 50,
            "list_select_related": True,
        }
        atributos.update(opciones)
        admin.site.register(modelo, type(f"{modelo.__name__}Admin", (admin.ModelAdmin,), atributos))
__FIN__

    escribir "context_processors.py" <<'__FIN__'
from django.core.cache import cache

from apps.core.models import ConfiguracionNegocio
from apps.core.models.configuracion_negocio import CLAVE_CACHE


def negocio(request):
    configuracion = cache.get(CLAVE_CACHE)
    if configuracion is None:
        configuracion = ConfiguracionNegocio.objects.first()
        cache.set(CLAVE_CACHE, configuracion, 300)
    return {"negocio": configuracion}
__FIN__

    escribir "seeds.py" <<'__FIN__'
from django.contrib.auth.models import Group
from django.core.management.color import no_style
from django.db import connections, transaction

ESTADOS_USUARIO = (
    (1, "Activo", "Cuenta habilitada para utilizar la plataforma."),
    (2, "Inactivo", "Cuenta deshabilitada."),
    (3, "Suspendido", "Cuenta suspendida temporalmente."),
    (4, "Pendiente de verificación", "Cuenta pendiente de verificar."),
)

CATEGORIAS_SERVICIOS = (
    ("Impresión 3D", "Servicios de fabricación mediante impresión 3D."),
    ("Diseño 3D", "Diseño de piezas y productos tridimensionales."),
    ("Modelado 3D", "Creación y edición de modelos tridimensionales."),
    ("Asesorías", "Asesoría técnica y acompañamiento en proyectos."),
    ("Prototipado", "Desarrollo de prototipos y validación de diseños."),
)

METODOS_PAGO = (
    (1, "Efectivo", "Pago registrado directamente por un empleado."),
    (2, "Pasarela de pagos", "Pago electrónico mediante proveedor externo."),
)


def sembrar_datos_iniciales(sender=None, using="default", **kwargs):
    from apps.catalogo.models import CategoriaServicio
    from apps.pagos.models import MetodoPago
    from apps.usuarios.constants import GRUPOS
    from apps.usuarios.models import EstadoUsuario

    conexion = connections[using]
    existentes = set(conexion.introspection.table_names())
    requeridas = {modelo._meta.db_table for modelo in (EstadoUsuario, CategoriaServicio, MetodoPago, Group)}
    if not requeridas <= existentes:
        return

    with transaction.atomic(using=using):
        for id_, nombre, descripcion in ESTADOS_USUARIO:
            EstadoUsuario.objects.using(using).get_or_create(
                nombre=nombre, defaults={"id": id_, "descripcion": descripcion}
            )
        for id_, nombre, descripcion in METODOS_PAGO:
            MetodoPago.objects.using(using).get_or_create(
                nombre=nombre, defaults={"id": id_, "descripcion": descripcion}
            )
        for nombre, descripcion in CATEGORIAS_SERVICIOS:
            CategoriaServicio.objects.using(using).get_or_create(
                nombre=nombre, defaults={"descripcion": descripcion}
            )
        for nombre in GRUPOS:
            Group.objects.using(using).get_or_create(name=nombre)

        sentencias = conexion.ops.sequence_reset_sql(no_style(), [EstadoUsuario, MetodoPago])
        with conexion.cursor() as cursor:
            for sentencia in sentencias:
                cursor.execute(sentencia)
__FIN__

    escribir "models/__init__.py" <<'__FIN__'
from .base import ModeloValidado
from .configuracion_negocio import ConfiguracionNegocio
from .documentos import DetalleImportes, DocumentoImportes

__all__ = ["ConfiguracionNegocio", "DetalleImportes", "DocumentoImportes", "ModeloValidado"]
__FIN__

    escribir "models/base.py" <<'__FIN__'
from django.db import models


class ModeloValidado(models.Model):
    campos_texto_opcional = ()

    class Meta:
        abstract = True

    def normalizar(self):
        for campo in self.campos_texto_opcional:
            valor = getattr(self, campo)
            if isinstance(valor, str):
                setattr(self, campo, valor.strip() or None)

    def clean(self):
        super().clean()
        self.normalizar()

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if update_fields is None:
            self.full_clean()
        else:
            nombres = set(update_fields)
            excluir = [
                campo.name
                for campo in self._meta.concrete_fields
                if campo.name not in nombres and campo.attname not in nombres
            ]
            self.clean_fields(exclude=excluir)
        super().save(*args, **kwargs)
__FIN__

    escribir "models/documentos.py" <<'__FIN__'
from decimal import Decimal

from django.core.exceptions import ValidationError

from apps.core.calculos import importes_coherentes
from apps.core.fields import cantidad_decimal, dinero
from apps.core.models.base import ModeloValidado


class DocumentoImportes(ModeloValidado):
    subtotal = dinero(default=Decimal("0.00"))
    descuento = dinero(default=Decimal("0.00"))
    impuesto = dinero(default=Decimal("0.00"))
    total = dinero(default=Decimal("0.00"))

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        if not importes_coherentes(self.subtotal, self.descuento, self.impuesto, self.total):
            raise ValidationError({"total": "El total debe ser igual a subtotal - descuento + impuesto."})


class DetalleImportes(ModeloValidado):
    cantidad = cantidad_decimal()
    precio_unitario = dinero()
    descuento = dinero(default=Decimal("0.00"))
    impuesto = dinero(default=Decimal("0.00"))
    subtotal = dinero()

    class Meta:
        abstract = True
__FIN__

    escribir "models/configuracion_negocio.py" <<'__FIN__'
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models.base import ModeloValidado
from apps.core.validators import validar_identificacion_fiscal, validar_ruta_relativa, validar_telefono

CLAVE_CACHE = "configuracion_negocio"


class ConfiguracionNegocio(ModeloValidado):
    nombre_negocio = models.CharField(max_length=150)
    identificacion_fiscal = models.CharField(
        max_length=30, null=True, blank=True, validators=[validar_identificacion_fiscal]
    )
    correo = models.EmailField(max_length=150, null=True, blank=True)
    telefono = models.CharField(max_length=25, null=True, blank=True, validators=[validar_telefono])
    direccion = models.CharField(max_length=250, null=True, blank=True)
    sitio_web = models.URLField(max_length=200, null=True, blank=True)
    logo = models.TextField(null=True, blank=True, validators=[validar_ruta_relativa])
    actualizado_en = models.DateTimeField(auto_now=True)

    campos_texto_opcional = ("identificacion_fiscal", "correo", "telefono", "direccion", "sitio_web", "logo")

    class Meta:
        db_table = "configuracion_negocio"
        verbose_name = "configuración del negocio"
        verbose_name_plural = "configuración del negocio"

    def __str__(self):
        return self.nombre_negocio

    def clean(self):
        super().clean()
        if self._state.adding and ConfiguracionNegocio.objects.exists():
            raise ValidationError("Solo puede existir un registro de configuración del negocio.")

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cache.delete(CLAVE_CACHE)

    def delete(self, *args, **kwargs):
        resultado = super().delete(*args, **kwargs)
        cache.delete(CLAVE_CACHE)
        return resultado
__FIN__

    escribir "admin.py" <<'__FIN__'
from apps.core.admin_utils import registrar
from apps.core.models import ConfiguracionNegocio

registrar(ConfiguracionNegocio)
__FIN__
}

app_usuarios() {
    info "App usuarios"
    crear_app usuarios "Usuarios"

    escribir "constants.py" <<'__FIN__'
ESTADO_ACTIVO = 1
ESTADO_INACTIVO = 2
ESTADO_SUSPENDIDO = 3
ESTADO_PENDIENTE = 4
ESTADOS_BLOQUEADOS = (ESTADO_INACTIVO, ESTADO_SUSPENDIDO)

GRUPO_CLIENTE = "Customer"
GRUPO_OPERADOR = "Operator"
GRUPO_ADMINISTRADOR = "Administrator"
GRUPOS = (GRUPO_CLIENTE, GRUPO_OPERADOR, GRUPO_ADMINISTRADOR)
__FIN__

    escribir "seguridad.py" <<'__FIN__'
def obtener_identificador(request, credentials=None):
    credentials = credentials or {}
    for clave in ("correo", "email", "login", "username"):
        valor = credentials.get(clave)
        if not valor and request is not None and hasattr(request, "POST"):
            valor = request.POST.get(clave)
        if valor:
            return str(valor).strip().lower()
    return None
__FIN__

    escribir "managers.py" <<'__FIN__'
from django.contrib.auth.models import BaseUserManager

from apps.usuarios.constants import ESTADO_ACTIVO


class UsuarioManager(BaseUserManager):
    def get_by_natural_key(self, correo):
        return self.get(**{f"{self.model.USERNAME_FIELD}__iexact": correo})

    def _crear(self, correo, password, **extra):
        if not correo:
            raise ValueError("El correo es obligatorio.")
        extra.setdefault("estado_id", ESTADO_ACTIVO)
        usuario = self.model(correo=self.normalize_email(correo).lower(), **extra)
        if password:
            usuario.set_password(password)
        else:
            usuario.set_unusable_password()
        usuario.save(using=self._db)
        return usuario

    def create_user(self, correo, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._crear(correo, password, **extra)

    def create_superuser(self, correo, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        if extra.get("is_staff") is not True or extra.get("is_superuser") is not True:
            raise ValueError("El superusuario debe tener is_staff e is_superuser en True.")
        return self._crear(correo, password, **extra)
__FIN__

    escribir "models/__init__.py" <<'__FIN__'
from .empleado import Empleado
from .estado_usuario import EstadoUsuario
from .usuario import Usuario

__all__ = ["Empleado", "EstadoUsuario", "Usuario"]
__FIN__

    escribir "models/estado_usuario.py" <<'__FIN__'
from django.db import models

from apps.core.models.base import ModeloValidado


class EstadoUsuario(ModeloValidado):
    id = models.SmallAutoField(primary_key=True)
    nombre = models.CharField(max_length=40, unique=True)
    descripcion = models.CharField(max_length=150, null=True, blank=True)

    campos_texto_opcional = ("descripcion",)

    class Meta:
        db_table = "estados_usuarios"
        verbose_name = "estado de usuario"
        verbose_name_plural = "estados de usuarios"

    def __str__(self):
        return self.nombre
__FIN__

    escribir "models/usuario.py" <<'__FIN__'
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.core.models.base import ModeloValidado
from apps.core.validators import validar_nombre_persona, validar_telefono
from apps.usuarios.constants import ESTADO_ACTIVO, ESTADOS_BLOQUEADOS
from apps.usuarios.managers import UsuarioManager


class Usuario(ModeloValidado, AbstractBaseUser, PermissionsMixin):
    nombres = models.CharField(max_length=100, validators=[validar_nombre_persona])
    apellidos = models.CharField(max_length=100, validators=[validar_nombre_persona])
    correo = models.EmailField(max_length=150, unique=True)
    telefono = models.CharField(max_length=25, null=True, blank=True, validators=[validar_telefono])
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)
    estado = models.ForeignKey(
        "usuarios.EstadoUsuario",
        on_delete=models.PROTECT,
        db_column="id_estado",
        related_name="usuarios",
        default=ESTADO_ACTIVO,
    )

    objects = UsuarioManager()

    USERNAME_FIELD = "correo"
    EMAIL_FIELD = "correo"
    REQUIRED_FIELDS = ["nombres", "apellidos"]
    campos_texto_opcional = ("telefono",)

    class Meta:
        db_table = "usuarios"
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"

    def __str__(self):
        return self.correo

    @property
    def nombre_completo(self):
        return f"{self.nombres} {self.apellidos}".strip()

    def get_full_name(self):
        return self.nombre_completo

    def get_short_name(self):
        return self.nombres

    def clean(self):
        super().clean()
        if self.correo:
            self.correo = self.correo.strip().lower()
        if self.estado_id in ESTADOS_BLOQUEADOS:
            self.is_active = False

    def tiene_algun_rol(self, roles):
        if not (self.is_active and self.estado_id == ESTADO_ACTIVO):
            return False
        if self.is_superuser:
            return True
        return self.groups.filter(name__in=roles).exists()
__FIN__

    escribir "models/empleado.py" <<'__FIN__'
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models.base import ModeloValidado
from apps.core.validators import validar_codigo


class Empleado(ModeloValidado):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column="id_usuario",
        related_name="empleado",
    )
    codigo_empleado = models.CharField(max_length=30, unique=True, validators=[validar_codigo])
    cargo = models.CharField(max_length=100)
    fecha_contratacion = models.DateField(null=True, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "empleados"
        verbose_name = "empleado"
        verbose_name_plural = "empleados"

    def __str__(self):
        return f"{self.codigo_empleado} - {self.cargo}"

    def clean(self):
        super().clean()
        if self.codigo_empleado:
            self.codigo_empleado = self.codigo_empleado.strip().upper()
        if self.fecha_contratacion and self.fecha_contratacion > timezone.localdate():
            raise ValidationError({"fecha_contratacion": "La fecha de contratación no puede ser futura."})
__FIN__

    escribir "forms/__init__.py" </dev/null

    escribir "forms/admin.py" <<'__FIN__'
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from apps.usuarios.models import Usuario


class UsuarioCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = ("correo", "nombres", "apellidos", "telefono", "estado")
        field_classes = {}


class UsuarioChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = Usuario
        fields = "__all__"
        field_classes = {}
__FIN__

    escribir "admin.py" <<'__FIN__'
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from apps.core.admin_utils import registrar
from apps.usuarios.forms.admin import UsuarioChangeForm, UsuarioCreationForm
from apps.usuarios.models import Empleado, EstadoUsuario, Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    form = UsuarioChangeForm
    add_form = UsuarioCreationForm
    model = Usuario
    ordering = ("correo",)
    list_display = ("correo", "nombres", "apellidos", "estado", "is_staff", "is_active")
    list_filter = ("estado", "is_staff", "is_active", "groups")
    search_fields = ("correo", "nombres", "apellidos")
    filter_horizontal = ("groups", "user_permissions")
    readonly_fields = ("last_login", "date_joined")
    fieldsets = (
        (None, {"fields": ("correo", "password")}),
        ("Datos personales", {"fields": ("nombres", "apellidos", "telefono", "estado")}),
        ("Permisos", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Fechas", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("correo", "nombres", "apellidos", "telefono", "estado", "password1", "password2"),
            },
        ),
    )


registrar(EstadoUsuario, Empleado)
__FIN__
    capas_app usuarios EstadoUsuario Usuario Empleado
}

app_clientes() {
    info "App clientes"
    crear_app clientes "Clientes"
    escribir "models/__init__.py" <<'__FIN__'
from .cliente import Cliente, TipoCliente

__all__ = ["Cliente", "TipoCliente"]
__FIN__
    escribir "models/cliente.py" <<'__FIN__'
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.constraints import en_lista
from apps.core.models.base import ModeloValidado
from apps.core.validators import validar_identificacion_fiscal, validar_nombre_persona, validar_telefono


class TipoCliente(models.TextChoices):
    PERSONA = "PERSONA", "Persona"
    EMPRESA = "EMPRESA", "Empresa"


class Cliente(ModeloValidado):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="id_usuario",
        related_name="cliente",
    )
    tipo_cliente = models.CharField(max_length=20, choices=TipoCliente.choices)
    nombres = models.CharField(max_length=100, null=True, blank=True, validators=[validar_nombre_persona])
    apellidos = models.CharField(max_length=100, null=True, blank=True, validators=[validar_nombre_persona])
    nombre_empresa = models.CharField(max_length=150, null=True, blank=True)
    correo = models.EmailField(max_length=150)
    telefono = models.CharField(max_length=25, null=True, blank=True, validators=[validar_telefono])
    identificacion_fiscal = models.CharField(
        max_length=30, null=True, blank=True, validators=[validar_identificacion_fiscal]
    )
    direccion = models.CharField(max_length=250, null=True, blank=True)
    observaciones = models.TextField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    campos_texto_opcional = (
        "nombres",
        "apellidos",
        "nombre_empresa",
        "telefono",
        "identificacion_fiscal",
        "direccion",
        "observaciones",
    )

    class Meta:
        db_table = "clientes"
        verbose_name = "cliente"
        verbose_name_plural = "clientes"
        constraints = [en_lista("ck_clientes_tipo", "tipo_cliente", TipoCliente.values)]
        indexes = [
            models.Index(fields=["correo"], name="idx_clientes_correo"),
            models.Index(fields=["tipo_cliente"], name="idx_clientes_tipo"),
        ]

    def __str__(self):
        return self.nombre_visible

    @property
    def nombre_visible(self):
        if self.tipo_cliente == TipoCliente.EMPRESA:
            return self.nombre_empresa or self.correo
        return f"{self.nombres or ''} {self.apellidos or ''}".strip() or self.correo

    def clean(self):
        super().clean()
        errores = {}
        if self.correo:
            self.correo = self.correo.strip().lower()
        if self.tipo_cliente == TipoCliente.PERSONA:
            if not self.nombres:
                errores["nombres"] = "Los nombres son obligatorios para una persona."
            if not self.apellidos:
                errores["apellidos"] = "Los apellidos son obligatorios para una persona."
            if self.nombre_empresa:
                errores["nombre_empresa"] = "Una persona no puede tener nombre de empresa."
        elif self.tipo_cliente == TipoCliente.EMPRESA and not self.nombre_empresa:
            errores["nombre_empresa"] = "El nombre de la empresa es obligatorio."
        if errores:
            raise ValidationError(errores)
__FIN__
    escribir "admin.py" <<'__FIN__'
from apps.clientes.models import Cliente
from apps.core.admin_utils import registrar

registrar(Cliente, search_fields=("correo", "nombres", "apellidos", "nombre_empresa"))
__FIN__
    capas_app clientes Cliente
}

app_catalogo() {
    info "App catalogo"
    crear_app catalogo "Catalogo"
    escribir "models/__init__.py" <<'__FIN__'
from .categoria_servicio import CategoriaServicio
from .promocion import Promocion, TipoDescuento
from .servicio import Servicio

__all__ = ["CategoriaServicio", "Promocion", "Servicio", "TipoDescuento"]
__FIN__
    escribir "models/categoria_servicio.py" <<'__FIN__'
from django.db import models

from apps.core.models.base import ModeloValidado


class CategoriaServicio(ModeloValidado):
    nombre = models.CharField(max_length=80, unique=True)
    descripcion = models.CharField(max_length=200, null=True, blank=True)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    campos_texto_opcional = ("descripcion",)

    class Meta:
        db_table = "categorias_servicios"
        verbose_name = "categoría de servicio"
        verbose_name_plural = "categorías de servicios"

    def __str__(self):
        return self.nombre
__FIN__
    escribir "models/servicio.py" <<'__FIN__'
from django.db import models
from django.db.models import Q

from apps.core.constraints import restriccion
from apps.core.fields import dinero
from apps.core.models.base import ModeloValidado


class Servicio(ModeloValidado):
    categoria = models.ForeignKey(
        "catalogo.CategoriaServicio",
        on_delete=models.PROTECT,
        db_column="id_categoria",
        related_name="servicios",
    )
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField()
    precio_base = dinero()
    requiere_archivo = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "servicios"
        verbose_name = "servicio"
        verbose_name_plural = "servicios"
        constraints = [restriccion("ck_servicios_precio", Q(precio_base__gte=0))]
        indexes = [models.Index(fields=["activo"], name="idx_servicios_activo")]

    def __str__(self):
        return self.nombre
__FIN__
    escribir "models/promocion.py" <<'__FIN__'
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.constraints import en_lista, restriccion
from apps.core.models.base import ModeloValidado


class TipoDescuento(models.TextChoices):
    PORCENTAJE = "PORCENTAJE", "Porcentaje"
    MONTO_FIJO = "MONTO_FIJO", "Monto fijo"


class Promocion(ModeloValidado):
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField(null=True, blank=True)
    tipo_descuento = models.CharField(max_length=20, choices=TipoDescuento.choices)
    valor_descuento = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField()
    activo = models.BooleanField(default=True)

    campos_texto_opcional = ("descripcion",)

    class Meta:
        db_table = "promociones"
        verbose_name = "promoción"
        verbose_name_plural = "promociones"
        constraints = [
            en_lista("ck_promociones_tipo", "tipo_descuento", TipoDescuento.values),
            restriccion("ck_promociones_valor", Q(valor_descuento__gt=0)),
            restriccion("ck_promociones_fechas", Q(fecha_fin__gte=models.F("fecha_inicio"))),
            restriccion(
                "ck_promociones_porcentaje",
                ~Q(tipo_descuento="PORCENTAJE") | Q(valor_descuento__lte=100),
            ),
        ]
        indexes = [models.Index(fields=["activo", "fecha_inicio", "fecha_fin"], name="idx_promociones_vigencia")]

    def __str__(self):
        return self.nombre

    @property
    def vigente(self):
        return self.activo and self.fecha_inicio <= timezone.now() <= self.fecha_fin

    def clean(self):
        super().clean()
        errores = {}
        if self.fecha_inicio and self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            errores["fecha_fin"] = "La fecha final no puede ser anterior a la inicial."
        if (
            self.tipo_descuento == TipoDescuento.PORCENTAJE
            and self.valor_descuento is not None
            and self.valor_descuento > 100
        ):
            errores["valor_descuento"] = "El porcentaje no puede superar 100."
        if errores:
            raise ValidationError(errores)
__FIN__
    escribir "admin.py" <<'__FIN__'
from apps.catalogo.models import CategoriaServicio, Promocion, Servicio
from apps.core.admin_utils import registrar

registrar(CategoriaServicio, Promocion)
registrar(Servicio, list_filter=("categoria", "activo"), search_fields=("nombre",))
__FIN__
    capas_app catalogo CategoriaServicio Servicio Promocion
}

app_cotizaciones() {
    info "App cotizaciones"
    crear_app cotizaciones "Cotizaciones"
    escribir "models/__init__.py" <<'__FIN__'
from .cotizacion import Cotizacion, EstadoCotizacion
from .cotizacion_detalle import CotizacionDetalle

__all__ = ["Cotizacion", "CotizacionDetalle", "EstadoCotizacion"]
__FIN__
    escribir "models/cotizacion.py" <<'__FIN__'
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.constraints import en_lista, no_negativos, restriccion
from apps.core.models.documentos import DocumentoImportes
from apps.core.validators import validar_codigo


class EstadoCotizacion(models.TextChoices):
    BORRADOR = "BORRADOR", "Borrador"
    ENVIADA = "ENVIADA", "Enviada"
    ACEPTADA = "ACEPTADA", "Aceptada"
    RECHAZADA = "RECHAZADA", "Rechazada"
    VENCIDA = "VENCIDA", "Vencida"
    CANCELADA = "CANCELADA", "Cancelada"


class Cotizacion(DocumentoImportes):
    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.PROTECT,
        db_column="id_cliente",
        related_name="cotizaciones",
    )
    usuario_responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column="id_usuario_responsable",
        related_name="cotizaciones_a_cargo",
    )
    codigo = models.CharField(max_length=30, unique=True, validators=[validar_codigo])
    fecha_emision = models.DateTimeField(default=timezone.now)
    fecha_vencimiento = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(max_length=20, choices=EstadoCotizacion.choices, default=EstadoCotizacion.BORRADOR)
    observaciones = models.TextField(null=True, blank=True)

    campos_texto_opcional = ("observaciones",)

    class Meta:
        db_table = "cotizaciones"
        verbose_name = "cotización"
        verbose_name_plural = "cotizaciones"
        constraints = [
            en_lista("ck_cotizaciones_estado", "estado", EstadoCotizacion.values),
            restriccion("ck_cotizaciones_importes", no_negativos("subtotal", "descuento", "impuesto", "total")),
        ]
        indexes = [models.Index(fields=["estado"], name="idx_cotizaciones_estado")]

    def __str__(self):
        return self.codigo

    def clean(self):
        super().clean()
        if self.codigo:
            self.codigo = self.codigo.strip().upper()
        if self.fecha_vencimiento and self.fecha_emision and self.fecha_vencimiento < self.fecha_emision:
            raise ValidationError({"fecha_vencimiento": "El vencimiento no puede ser anterior a la emisión."})
__FIN__
    escribir "models/cotizacion_detalle.py" <<'__FIN__'
from django.db import models
from django.db.models import Q

from apps.core.constraints import no_negativos, restriccion
from apps.core.models.documentos import DetalleImportes


class CotizacionDetalle(DetalleImportes):
    cotizacion = models.ForeignKey(
        "cotizaciones.Cotizacion",
        on_delete=models.CASCADE,
        db_column="id_cotizacion",
        related_name="detalles",
    )
    servicio = models.ForeignKey(
        "catalogo.Servicio",
        on_delete=models.PROTECT,
        db_column="id_servicio",
        related_name="detalles_cotizacion",
    )
    descripcion = models.CharField(max_length=250)

    class Meta:
        db_table = "cotizaciones_detalles"
        verbose_name = "detalle de cotización"
        verbose_name_plural = "detalles de cotizaciones"
        constraints = [
            restriccion("ck_cot_det_cantidad", Q(cantidad__gt=0)),
            restriccion(
                "ck_cot_det_importes",
                no_negativos("precio_unitario", "descuento", "impuesto", "subtotal"),
            ),
        ]

    def __str__(self):
        return f"{self.cotizacion_id} - {self.descripcion}"
__FIN__
    escribir "admin.py" <<'__FIN__'
from apps.core.admin_utils import registrar
from apps.cotizaciones.models import Cotizacion, CotizacionDetalle

registrar(Cotizacion, list_filter=("estado",), search_fields=("codigo",))
registrar(CotizacionDetalle)
__FIN__
    capas_app cotizaciones Cotizacion CotizacionDetalle
}

app_encargos() {
    info "App encargos"
    crear_app encargos "Encargos"
    escribir "models/__init__.py" <<'__FIN__'
from .archivo_encargo import ArchivoEncargo, FormatoArchivo
from .encargo import Encargo, EstadoEncargo
from .encargo_detalle import EncargoDetalle
from .historial_encargo import HistorialEncargo

__all__ = [
    "ArchivoEncargo",
    "Encargo",
    "EncargoDetalle",
    "EstadoEncargo",
    "FormatoArchivo",
    "HistorialEncargo",
]
__FIN__
    escribir "models/encargo.py" <<'__FIN__'
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.constraints import en_lista, no_negativos, restriccion
from apps.core.models.documentos import DocumentoImportes
from apps.core.validators import validar_codigo


class EstadoEncargo(models.TextChoices):
    PENDIENTE = "PENDIENTE", "Pendiente"
    EN_REVISION = "EN_REVISION", "En revisión"
    APROBADO = "APROBADO", "Aprobado"
    EN_PRODUCCION = "EN_PRODUCCION", "En producción"
    EN_ESPERA = "EN_ESPERA", "En espera"
    FINALIZADO = "FINALIZADO", "Finalizado"
    ENTREGADO = "ENTREGADO", "Entregado"
    CANCELADO = "CANCELADO", "Cancelado"


class Encargo(DocumentoImportes):
    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.PROTECT,
        db_column="id_cliente",
        related_name="encargos",
    )
    cotizacion = models.OneToOneField(
        "cotizaciones.Cotizacion",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="id_cotizacion",
        related_name="encargo",
    )
    empleado_responsable = models.ForeignKey(
        "usuarios.Empleado",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="id_empleado_responsable",
        related_name="encargos",
    )
    codigo = models.CharField(max_length=30, unique=True, validators=[validar_codigo])
    fecha_solicitud = models.DateTimeField(default=timezone.now)
    fecha_entrega_estimada = models.DateTimeField(null=True, blank=True)
    fecha_entrega_real = models.DateTimeField(null=True, blank=True)
    descripcion = models.TextField()
    estado = models.CharField(max_length=25, choices=EstadoEncargo.choices, default=EstadoEncargo.PENDIENTE)
    observaciones = models.TextField(null=True, blank=True)

    campos_texto_opcional = ("observaciones",)

    class Meta:
        db_table = "encargos"
        verbose_name = "encargo"
        verbose_name_plural = "encargos"
        constraints = [
            en_lista("ck_encargos_estado", "estado", EstadoEncargo.values),
            restriccion("ck_encargos_importes", no_negativos("subtotal", "descuento", "impuesto", "total")),
        ]
        indexes = [models.Index(fields=["estado"], name="idx_encargos_estado")]

    def __str__(self):
        return self.codigo

    def clean(self):
        super().clean()
        errores = {}
        if self.codigo:
            self.codigo = self.codigo.strip().upper()
        for campo in ("fecha_entrega_estimada", "fecha_entrega_real"):
            valor = getattr(self, campo)
            if valor and self.fecha_solicitud and valor < self.fecha_solicitud:
                errores[campo] = "No puede ser anterior a la fecha de solicitud."
        if self.cotizacion_id and self.cotizacion.cliente_id != self.cliente_id:
            errores["cotizacion"] = "La cotización pertenece a otro cliente."
        if errores:
            raise ValidationError(errores)
__FIN__
    escribir "models/encargo_detalle.py" <<'__FIN__'
from django.db import models
from django.db.models import Q

from apps.core.constraints import no_negativos, restriccion
from apps.core.models.documentos import DetalleImportes
from apps.core.validators import validar_objeto_json


class EncargoDetalle(DetalleImportes):
    encargo = models.ForeignKey(
        "encargos.Encargo",
        on_delete=models.CASCADE,
        db_column="id_encargo",
        related_name="detalles",
    )
    servicio = models.ForeignKey(
        "catalogo.Servicio",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="id_servicio",
        related_name="detalles_encargo",
    )
    descripcion = models.TextField()
    especificaciones = models.JSONField(null=True, blank=True, validators=[validar_objeto_json])

    class Meta:
        db_table = "encargos_detalles"
        verbose_name = "detalle de encargo"
        verbose_name_plural = "detalles de encargos"
        constraints = [
            restriccion("ck_enc_det_cantidad", Q(cantidad__gt=0)),
            restriccion(
                "ck_enc_det_importes",
                no_negativos("precio_unitario", "descuento", "impuesto", "subtotal"),
            ),
        ]

    def __str__(self):
        return f"{self.encargo_id} - {self.descripcion[:40]}"
__FIN__
    escribir "models/archivo_encargo.py" <<'__FIN__'
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.constraints import en_lista, restriccion
from apps.core.validators import (
    validar_nombre_archivo,
    validar_ruta_relativa,
    validar_tamano_archivo,
)
from apps.core.models.base import ModeloValidado


class FormatoArchivo(models.TextChoices):
    STL = "STL", "STL"
    OBJ = "OBJ", "OBJ"
    TRES_MF = "3MF", "3MF"
    STEP = "STEP", "STEP"
    PNG = "PNG", "PNG"
    JPG = "JPG", "JPG"
    PDF = "PDF", "PDF"


EXTENSIONES_POR_FORMATO = {"JPG": ("jpg", "jpeg")}


class ArchivoEncargo(ModeloValidado):
    encargo_detalle = models.ForeignKey(
        "encargos.EncargoDetalle",
        on_delete=models.CASCADE,
        db_column="id_encargo_detalle",
        related_name="archivos",
    )
    nombre_archivo = models.CharField(max_length=150, validators=[validar_nombre_archivo])
    ruta_archivo = models.TextField(validators=[validar_ruta_relativa])
    formato = models.CharField(max_length=15, choices=FormatoArchivo.choices)
    tamano_bytes = models.BigIntegerField(validators=[MinValueValidator(0), validar_tamano_archivo])
    usuario_subida = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column="id_usuario_subida",
        related_name="archivos_subidos",
    )
    fecha_subida = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "archivos_encargos"
        verbose_name = "archivo de encargo"
        verbose_name_plural = "archivos de encargos"
        constraints = [
            restriccion("ck_archivos_tamano", Q(tamano_bytes__gte=0)),
            en_lista("ck_archivos_formato", "formato", FormatoArchivo.values),
        ]

    def __str__(self):
        return self.nombre_archivo

    def clean(self):
        super().clean()
        if self.formato:
            self.formato = self.formato.strip().upper()
        if self.nombre_archivo and self.formato:
            extension = self.nombre_archivo.rsplit(".", 1)[-1].lower() if "." in self.nombre_archivo else ""
            permitidas = EXTENSIONES_POR_FORMATO.get(self.formato, (self.formato.lower(),))
            if extension not in permitidas:
                raise ValidationError({"nombre_archivo": "La extensión no coincide con el formato indicado."})
__FIN__
    escribir "models/historial_encargo.py" <<'__FIN__'
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models.base import ModeloValidado
from apps.encargos.models.encargo import EstadoEncargo


class HistorialEncargo(ModeloValidado):
    encargo = models.ForeignKey(
        "encargos.Encargo",
        on_delete=models.CASCADE,
        db_column="id_encargo",
        related_name="historial",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column="id_usuario",
        related_name="historial_encargos",
    )
    estado_anterior = models.CharField(max_length=25, choices=EstadoEncargo.choices, null=True, blank=True)
    estado_nuevo = models.CharField(max_length=25, choices=EstadoEncargo.choices)
    comentario = models.TextField(null=True, blank=True)
    fecha_cambio = models.DateTimeField(default=timezone.now)

    campos_texto_opcional = ("estado_anterior", "comentario")

    class Meta:
        db_table = "historial_encargos"
        verbose_name = "historial de encargo"
        verbose_name_plural = "historial de encargos"
        indexes = [models.Index(fields=["encargo", "fecha_cambio"], name="idx_historial_encargo_fecha")]

    def __str__(self):
        return f"{self.encargo_id}: {self.estado_anterior} -> {self.estado_nuevo}"

    def clean(self):
        super().clean()
        if self.estado_anterior and self.estado_anterior == self.estado_nuevo:
            raise ValidationError({"estado_nuevo": "El estado nuevo debe ser distinto del anterior."})

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("El historial de encargos no se puede modificar.")
        super().save(*args, **kwargs)
__FIN__
    escribir "admin.py" <<'__FIN__'
from apps.core.admin_utils import registrar
from apps.encargos.models import ArchivoEncargo, Encargo, EncargoDetalle, HistorialEncargo

registrar(Encargo, list_filter=("estado",), search_fields=("codigo",))
registrar(EncargoDetalle, ArchivoEncargo)
registrar(HistorialEncargo, has_change_permission=lambda self, request, obj=None: False)
__FIN__
    capas_app encargos Encargo EncargoDetalle ArchivoEncargo HistorialEncargo
}

app_facturacion() {
    info "App facturacion"
    crear_app facturacion "Facturacion"
    escribir "models/__init__.py" <<'__FIN__'
from .factura import EstadoFactura, Factura
from .factura_detalle import FacturaDetalle

__all__ = ["EstadoFactura", "Factura", "FacturaDetalle"]
__FIN__
    escribir "models/factura.py" <<'__FIN__'
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.core.constraints import en_lista, no_negativos, restriccion
from apps.core.fields import dinero
from apps.core.models.documentos import DocumentoImportes
from apps.core.validators import validar_codigo, validar_identificacion_fiscal


class EstadoFactura(models.TextChoices):
    PENDIENTE = "PENDIENTE", "Pendiente"
    PARCIALMENTE_PAGADA = "PARCIALMENTE_PAGADA", "Parcialmente pagada"
    PAGADA = "PAGADA", "Pagada"
    ANULADA = "ANULADA", "Anulada"
    VENCIDA = "VENCIDA", "Vencida"


class Factura(DocumentoImportes):
    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.PROTECT,
        db_column="id_cliente",
        related_name="facturas",
    )
    encargo = models.OneToOneField(
        "encargos.Encargo",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="id_encargo",
        related_name="factura",
    )
    numero_factura = models.CharField(max_length=40, unique=True, validators=[validar_codigo])
    fecha_emision = models.DateTimeField(default=timezone.now)
    fecha_vencimiento = models.DateTimeField(null=True, blank=True)
    nombre_facturacion = models.CharField(max_length=150)
    identificacion_fiscal = models.CharField(
        max_length=30, null=True, blank=True, validators=[validar_identificacion_fiscal]
    )
    direccion_facturacion = models.CharField(max_length=250, null=True, blank=True)
    saldo_pendiente = dinero(default=Decimal("0.00"))
    estado = models.CharField(max_length=25, choices=EstadoFactura.choices, default=EstadoFactura.PENDIENTE)
    observaciones = models.TextField(null=True, blank=True)

    campos_texto_opcional = ("identificacion_fiscal", "direccion_facturacion", "observaciones")

    class Meta:
        db_table = "facturas"
        verbose_name = "factura"
        verbose_name_plural = "facturas"
        constraints = [
            en_lista("ck_facturas_estado", "estado", EstadoFactura.values),
            restriccion(
                "ck_facturas_importes",
                no_negativos("subtotal", "descuento", "impuesto", "total", "saldo_pendiente")
                & Q(saldo_pendiente__lte=F("total")),
            ),
        ]
        indexes = [models.Index(fields=["estado"], name="idx_facturas_estado")]

    def __str__(self):
        return self.numero_factura

    def clean(self):
        super().clean()
        errores = {}
        if self.numero_factura:
            self.numero_factura = self.numero_factura.strip().upper()
        if self.fecha_vencimiento and self.fecha_emision and self.fecha_vencimiento < self.fecha_emision:
            errores["fecha_vencimiento"] = "El vencimiento no puede ser anterior a la emisión."
        if self.saldo_pendiente is not None and self.total is not None and self.saldo_pendiente > self.total:
            errores["saldo_pendiente"] = "El saldo pendiente no puede superar el total."
        if self.estado == EstadoFactura.PAGADA and self.saldo_pendiente:
            errores["estado"] = "Una factura pagada no puede tener saldo pendiente."
        if errores:
            raise ValidationError(errores)
__FIN__
    escribir "models/factura_detalle.py" <<'__FIN__'
from django.db import models
from django.db.models import Q

from apps.core.constraints import no_negativos, restriccion
from apps.core.models.documentos import DetalleImportes


class FacturaDetalle(DetalleImportes):
    factura = models.ForeignKey(
        "facturacion.Factura",
        on_delete=models.PROTECT,
        db_column="id_factura",
        related_name="detalles",
    )
    servicio = models.ForeignKey(
        "catalogo.Servicio",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="id_servicio",
        related_name="detalles_factura",
    )
    descripcion = models.CharField(max_length=250)

    class Meta:
        db_table = "facturas_detalles"
        verbose_name = "detalle de factura"
        verbose_name_plural = "detalles de facturas"
        constraints = [
            restriccion("ck_fact_det_cantidad", Q(cantidad__gt=0)),
            restriccion(
                "ck_fact_det_importes",
                no_negativos("precio_unitario", "descuento", "impuesto", "subtotal"),
            ),
        ]

    def __str__(self):
        return f"{self.factura_id} - {self.descripcion}"
__FIN__
    escribir "admin.py" <<'__FIN__'
from apps.core.admin_utils import registrar
from apps.facturacion.models import Factura, FacturaDetalle

registrar(Factura, list_filter=("estado",), search_fields=("numero_factura", "nombre_facturacion"))
registrar(FacturaDetalle)
__FIN__
    capas_app facturacion Factura FacturaDetalle
}

app_pagos() {
    info "App pagos"
    crear_app pagos "Pagos"
    escribir "models/__init__.py" <<'__FIN__'
from .metodo_pago import MetodoPago
from .pago import EstadoPago, Pago
from .transaccion_pasarela import TransaccionPasarela

__all__ = ["EstadoPago", "MetodoPago", "Pago", "TransaccionPasarela"]
__FIN__
    escribir "models/metodo_pago.py" <<'__FIN__'
from django.db import models

from apps.core.models.base import ModeloValidado


class MetodoPago(ModeloValidado):
    id = models.SmallAutoField(primary_key=True)
    nombre = models.CharField(max_length=40, unique=True)
    descripcion = models.CharField(max_length=150, null=True, blank=True)
    activo = models.BooleanField(default=True)

    campos_texto_opcional = ("descripcion",)

    class Meta:
        db_table = "metodos_pago"
        verbose_name = "método de pago"
        verbose_name_plural = "métodos de pago"

    def __str__(self):
        return self.nombre
__FIN__
    escribir "models/pago.py" <<'__FIN__'
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.constraints import en_lista, restriccion
from apps.core.models.base import ModeloValidado
from apps.facturacion.models import EstadoFactura


class EstadoPago(models.TextChoices):
    PENDIENTE = "PENDIENTE", "Pendiente"
    CONFIRMADO = "CONFIRMADO", "Confirmado"
    RECHAZADO = "RECHAZADO", "Rechazado"
    REEMBOLSADO = "REEMBOLSADO", "Reembolsado"
    CANCELADO = "CANCELADO", "Cancelado"


class Pago(ModeloValidado):
    factura = models.ForeignKey(
        "facturacion.Factura",
        on_delete=models.PROTECT,
        db_column="id_factura",
        related_name="pagos",
    )
    metodo_pago = models.ForeignKey(
        "pagos.MetodoPago",
        on_delete=models.PROTECT,
        db_column="id_metodo_pago",
        related_name="pagos",
    )
    referencia = models.CharField(max_length=120, null=True, blank=True)
    monto = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    fecha_pago = models.DateTimeField(default=timezone.now)
    estado = models.CharField(max_length=20, choices=EstadoPago.choices, default=EstadoPago.PENDIENTE)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="registrado_por",
        related_name="pagos_registrados",
    )
    observaciones = models.TextField(null=True, blank=True)

    campos_texto_opcional = ("referencia", "observaciones")

    class Meta:
        db_table = "pagos"
        verbose_name = "pago"
        verbose_name_plural = "pagos"
        constraints = [
            restriccion("ck_pagos_monto", Q(monto__gt=0)),
            en_lista("ck_pagos_estado", "estado", EstadoPago.values),
        ]
        indexes = [
            models.Index(fields=["estado"], name="idx_pagos_estado"),
            models.Index(fields=["fecha_pago"], name="idx_pagos_fecha"),
        ]

    def __str__(self):
        return f"Pago {self.pk} - {self.monto}"

    def clean(self):
        super().clean()
        if self._state.adding and self.factura_id:
            factura = self.factura
            if factura.estado == EstadoFactura.ANULADA:
                raise ValidationError({"factura": "No se pueden registrar pagos sobre una factura anulada."})
            if self.monto is not None and self.monto > factura.total:
                raise ValidationError({"monto": "El monto no puede superar el total de la factura."})
__FIN__
    escribir "models/transaccion_pasarela.py" <<'__FIN__'
from django.db import models

from apps.core.models.base import ModeloValidado
from apps.core.validators import validar_objeto_json


class TransaccionPasarela(ModeloValidado):
    pago = models.OneToOneField(
        "pagos.Pago",
        on_delete=models.PROTECT,
        db_column="id_pago",
        related_name="transaccion",
    )
    proveedor = models.CharField(max_length=50)
    referencia_externa = models.CharField(max_length=150, unique=True, null=True, blank=True)
    estado_respuesta = models.CharField(max_length=40, null=True, blank=True)
    respuesta = models.JSONField(null=True, blank=True, validators=[validar_objeto_json])
    fecha_respuesta = models.DateTimeField(null=True, blank=True)

    campos_texto_opcional = ("referencia_externa", "estado_respuesta")

    class Meta:
        db_table = "transacciones_pasarela"
        verbose_name = "transacción de pasarela"
        verbose_name_plural = "transacciones de pasarela"

    def __str__(self):
        return f"{self.proveedor} - {self.referencia_externa or self.pk}"
__FIN__
    escribir "admin.py" <<'__FIN__'
from apps.core.admin_utils import registrar
from apps.pagos.models import MetodoPago, Pago, TransaccionPasarela

registrar(MetodoPago)
registrar(Pago, list_filter=("estado", "metodo_pago"))
registrar(TransaccionPasarela)
__FIN__
    capas_app pagos MetodoPago Pago TransaccionPasarela
}

app_crm() {
    info "App crm"
    crear_app crm "CRM"
    escribir "models/__init__.py" <<'__FIN__'
from .interaccion_cliente import InteraccionCliente, TipoInteraccion
from .nota_cliente import NotaCliente
from .resena import Resena
from .solicitud_soporte import EstadoSoporte, PrioridadSoporte, SolicitudSoporte

__all__ = [
    "EstadoSoporte",
    "InteraccionCliente",
    "NotaCliente",
    "PrioridadSoporte",
    "Resena",
    "SolicitudSoporte",
    "TipoInteraccion",
]
__FIN__
    escribir "models/interaccion_cliente.py" <<'__FIN__'
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.constraints import en_lista
from apps.core.models.base import ModeloValidado


class TipoInteraccion(models.TextChoices):
    LLAMADA = "LLAMADA", "Llamada"
    CORREO = "CORREO", "Correo"
    ASESORIA = "ASESORIA", "Asesoría"
    REUNION = "REUNION", "Reunión"
    SEGUIMIENTO = "SEGUIMIENTO", "Seguimiento"
    RECLAMO = "RECLAMO", "Reclamo"


class InteraccionCliente(ModeloValidado):
    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.PROTECT,
        db_column="id_cliente",
        related_name="interacciones",
    )
    usuario_responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column="id_usuario_responsable",
        related_name="interacciones_registradas",
    )
    tipo_interaccion = models.CharField(max_length=40, choices=TipoInteraccion.choices)
    asunto = models.CharField(max_length=150)
    descripcion = models.TextField(null=True, blank=True)
    fecha_interaccion = models.DateTimeField(default=timezone.now)

    campos_texto_opcional = ("descripcion",)

    class Meta:
        db_table = "interacciones_clientes"
        verbose_name = "interacción con cliente"
        verbose_name_plural = "interacciones con clientes"
        constraints = [en_lista("ck_interacciones_tipo", "tipo_interaccion", TipoInteraccion.values)]
        indexes = [models.Index(fields=["cliente", "fecha_interaccion"], name="idx_interacc_cliente_fecha")]

    def __str__(self):
        return f"{self.tipo_interaccion}: {self.asunto}"
__FIN__
    escribir "models/nota_cliente.py" <<'__FIN__'
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models.base import ModeloValidado


class NotaCliente(ModeloValidado):
    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.CASCADE,
        db_column="id_cliente",
        related_name="notas",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column="id_usuario",
        related_name="notas_clientes",
    )
    contenido = models.TextField()
    fecha_creacion = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "notas_clientes"
        verbose_name = "nota de cliente"
        verbose_name_plural = "notas de clientes"
        indexes = [models.Index(fields=["cliente", "fecha_creacion"], name="idx_notas_cliente_fecha")]

    def __str__(self):
        return f"Nota {self.pk} - cliente {self.cliente_id}"
__FIN__
    escribir "models/solicitud_soporte.py" <<'__FIN__'
from django.conf import settings
from django.db import models

from apps.core.constraints import en_lista
from apps.core.models.base import ModeloValidado


class PrioridadSoporte(models.TextChoices):
    BAJA = "BAJA", "Baja"
    MEDIA = "MEDIA", "Media"
    ALTA = "ALTA", "Alta"
    URGENTE = "URGENTE", "Urgente"


class EstadoSoporte(models.TextChoices):
    ABIERTA = "ABIERTA", "Abierta"
    EN_PROCESO = "EN_PROCESO", "En proceso"
    RESUELTA = "RESUELTA", "Resuelta"
    CERRADA = "CERRADA", "Cerrada"


class SolicitudSoporte(ModeloValidado):
    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.PROTECT,
        db_column="id_cliente",
        related_name="solicitudes_soporte",
    )
    usuario_responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="id_usuario_responsable",
        related_name="solicitudes_soporte_a_cargo",
    )
    asunto = models.CharField(max_length=150)
    descripcion = models.TextField()
    prioridad = models.CharField(max_length=20, choices=PrioridadSoporte.choices, default=PrioridadSoporte.MEDIA)
    estado = models.CharField(max_length=20, choices=EstadoSoporte.choices, default=EstadoSoporte.ABIERTA)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "solicitudes_soporte"
        verbose_name = "solicitud de soporte"
        verbose_name_plural = "solicitudes de soporte"
        constraints = [
            en_lista("ck_soporte_prioridad", "prioridad", PrioridadSoporte.values),
            en_lista("ck_soporte_estado", "estado", EstadoSoporte.values),
        ]
        indexes = [models.Index(fields=["estado", "prioridad"], name="idx_soporte_estado_prioridad")]

    def __str__(self):
        return self.asunto
__FIN__
    escribir "models/resena.py" <<'__FIN__'
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.constraints import restriccion
from apps.core.models.base import ModeloValidado


class Resena(ModeloValidado):
    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.PROTECT,
        db_column="id_cliente",
        related_name="resenas",
    )
    servicio = models.ForeignKey(
        "catalogo.Servicio",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="id_servicio",
        related_name="resenas",
    )
    encargo = models.ForeignKey(
        "encargos.Encargo",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="id_encargo",
        related_name="resenas",
    )
    puntuacion = models.SmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comentario = models.TextField(null=True, blank=True)
    fecha_creacion = models.DateTimeField(default=timezone.now)

    campos_texto_opcional = ("comentario",)

    class Meta:
        db_table = "resenas"
        verbose_name = "reseña"
        verbose_name_plural = "reseñas"
        constraints = [
            restriccion("ck_resenas_puntuacion", Q(puntuacion__gte=1, puntuacion__lte=5)),
            restriccion(
                "ck_resenas_referencia",
                Q(servicio__isnull=False) | Q(encargo__isnull=False),
            ),
        ]

    def __str__(self):
        return f"Reseña {self.pk} ({self.puntuacion}/5)"

    def clean(self):
        super().clean()
        if not self.servicio_id and not self.encargo_id:
            raise ValidationError("La reseña debe referirse a un servicio o a un encargo.")
        if self.encargo_id and self.encargo.cliente_id != self.cliente_id:
            raise ValidationError({"encargo": "El encargo pertenece a otro cliente."})
__FIN__
    escribir "admin.py" <<'__FIN__'
from apps.core.admin_utils import registrar
from apps.crm.models import InteraccionCliente, NotaCliente, Resena, SolicitudSoporte

registrar(InteraccionCliente, NotaCliente, Resena)
registrar(SolicitudSoporte, list_filter=("estado", "prioridad"))
__FIN__
    capas_app crm InteraccionCliente NotaCliente SolicitudSoporte Resena
}

app_notificaciones() {
    info "App notificaciones"
    crear_app notificaciones "Notificaciones"
    escribir "models/__init__.py" <<'__FIN__'
from .notificacion import Notificacion

__all__ = ["Notificacion"]
__FIN__
    escribir "models/notificacion.py" <<'__FIN__'
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models.base import ModeloValidado


class Notificacion(ModeloValidado):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column="id_usuario",
        related_name="notificaciones",
    )
    titulo = models.CharField(max_length=120)
    mensaje = models.TextField()
    tipo = models.CharField(max_length=40)
    referencia_id = models.BigIntegerField(null=True, blank=True)
    leida = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "notificaciones"
        verbose_name = "notificación"
        verbose_name_plural = "notificaciones"
        indexes = [
            models.Index(fields=["usuario", "leida", "-fecha_creacion"], name="idx_notif_usuario_leida_fecha")
        ]

    def __str__(self):
        return self.titulo
__FIN__
    escribir "admin.py" <<'__FIN__'
from apps.core.admin_utils import registrar
from apps.notificaciones.models import Notificacion

registrar(Notificacion, list_filter=("leida", "tipo"))
__FIN__
    capas_app notificaciones Notificacion
}

# ============================================================
# PASO 4: PORTAL (vistas por rol), PLANTILLAS Y ESTATICOS
# ============================================================

generar_modulo() {
    local modulo="$1" layout="$2" mixin="$3"
    shift 3
    local spec archivo clase ruta nombre titulo imports="" rutas=""
    ir_a "apps/portal/$modulo"
    vacio_si_falta "__init__.py"
    vacio_si_falta "forms/__init__.py"
    for spec in "$@"; do
        IFS='|' read -r archivo clase ruta nombre titulo <<<"$spec"
        if [[ $mixin == "-" ]]; then
            printf 'from django.views.generic import TemplateView\n\n\nclass %s(TemplateView):\n    template_name = "%s/%s.html"\n' \
                "$clase" "$modulo" "$archivo" | crear_si_falta "views/$archivo.py"
        else
            printf 'from django.views.generic import TemplateView\n\nfrom apps.portal.mixins import %s\n\n\nclass %s(%s, TemplateView):\n    template_name = "%s/%s.html"\n' \
                "$mixin" "$clase" "$mixin" "$modulo" "$archivo" | crear_si_falta "views/$archivo.py"
        fi
        imports+="from .${archivo} import ${clase}"$'\n'
        rutas+="    path(\"${ruta}\", views.${clase}.as_view(), name=\"${nombre}\"),"$'\n'
        ir_a "templates/$modulo"
        printf '{%% extends "layouts/%s.html" %%}\n\n{%% block titulo %%}%s{%% endblock %%}\n\n{%% block contenido %%}\n<h1>%s</h1>\n{%% endblock %%}\n' \
            "$layout" "$titulo" "$titulo" | crear_si_falta "$archivo.html"
        ir_a "apps/portal/$modulo"
    done
    printf '%s' "$imports" | crear_si_falta "views/__init__.py"
    printf 'from django.urls import path\n\nfrom . import views\n\napp_name = "%s"\n\nurlpatterns = [\n%s]\n' \
        "$modulo" "$rutas" | crear_si_falta "urls.py"
}

paso_portal() {
    info "Portal (guest, customer, operator, administrator)"
    ir_a "apps/portal"
    vacio_si_falta "__init__.py"

    crear_si_falta "mixins.py" <<'__FIN__'
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from apps.usuarios.constants import GRUPO_ADMINISTRADOR, GRUPO_CLIENTE, GRUPO_OPERADOR


class RolRequeridoMixin(LoginRequiredMixin, UserPassesTestMixin):
    roles = ()

    def test_func(self):
        usuario = self.request.user
        return usuario.is_authenticated and usuario.tiene_algun_rol(self.roles)


class ClienteRequeridoMixin(RolRequeridoMixin):
    roles = (GRUPO_CLIENTE,)


class OperadorRequeridoMixin(RolRequeridoMixin):
    roles = (GRUPO_OPERADOR, GRUPO_ADMINISTRADOR)


class AdministradorRequeridoMixin(RolRequeridoMixin):
    roles = (GRUPO_ADMINISTRADOR,)
__FIN__

    crear_si_falta "urls.py" <<'__FIN__'
from django.urls import include, path

urlpatterns = [
    path("cliente/", include("apps.portal.customer.urls")),
    path("operador/", include("apps.portal.operator.urls")),
    path("administrador/", include("apps.portal.administrator.urls")),
    path("", include("apps.portal.guest.urls")),
]
__FIN__

    generar_modulo guest guest - \
        "inicio|InicioView||inicio|Inicio" \
        "catalogo|CatalogoView|catalogo/|catalogo|Catálogo" \
        "servicios|ServiciosView|servicios/|servicios|Servicios" \
        "acceso|AccesoView|acceso/|acceso|Acceso"

    generar_modulo customer customer ClienteRequeridoMixin \
        "panel|PanelView||panel|Panel principal" \
        "tienda|TiendaView|tienda/|tienda|Tienda y compras" \
        "cotizar|CotizarView|cotizar/|cotizar|Solicitar cotización" \
        "pedidos|PedidosView|pedidos/|pedidos|Mis solicitudes y pedidos" \
        "cuenta|CuentaView|cuenta/|cuenta|Mi cuenta"

    generar_modulo operator dashboard OperadorRequeridoMixin \
        "panel|PanelView||panel|Panel operativo" \
        "cotizaciones|CotizacionesView|cotizaciones/|cotizaciones|Cotizaciones" \
        "encargos|EncargosView|encargos/|encargos|Encargos" \
        "clientes|ClientesView|clientes/|clientes|Clientes y atención"

    generar_modulo administrator dashboard AdministradorRequeridoMixin \
        "dashboard|DashboardView||dashboard|Dashboard administrativo" \
        "inventario|InventarioView|inventario/|inventario|Productos e inventario" \
        "servicios|ServiciosView|servicios/|servicios|Servicios y categorías" \
        "usuarios|UsuariosView|usuarios/|usuarios|Usuarios y empleados" \
        "ventas|VentasView|ventas/|ventas|Ventas y finanzas" \
        "configuracion|ConfiguracionView|configuracion/|configuracion|Configuración y reportes"
}

paso_plantillas() {
    info "Plantillas y estaticos"
    ir_a "templates/layouts"
    crear_si_falta "base.html" <<'__FIN__'
{% load static %}<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block titulo %}{% endblock %} | {{ negocio.nombre_negocio|default:"3DForge Studio" }}</title>
  <link rel="stylesheet" href="{% static 'css/app.css' %}">
  {% block estilos %}{% endblock %}
</head>
<body>
  {% include "components/mensajes.html" %}
  {% block cuerpo %}{% block contenido %}{% endblock %}{% endblock %}
  <script src="{% static 'js/app.js' %}" defer></script>
  {% block scripts %}{% endblock %}
</body>
</html>
__FIN__
    local layout
    for layout in guest customer dashboard; do
        printf '{%% extends "layouts/base.html" %%}\n\n{%% block cuerpo %%}\n{%% include "components/navbar.html" %%}\n<main>\n  {%% block contenido %%}{%% endblock %%}\n</main>\n{%% include "components/footer.html" %%}\n{%% endblock %%}\n' \
            | crear_si_falta "${layout}.html"
    done

    ir_a "templates/components"
    crear_si_falta "mensajes.html" <<'__FIN__'
{% if messages %}
<ul class="mensajes">
  {% for mensaje in messages %}<li class="{{ mensaje.tags }}">{{ mensaje }}</li>{% endfor %}
</ul>
{% endif %}
__FIN__
    crear_si_falta "navbar.html" <<'__FIN__'
<nav>
  <a href="{% url 'guest:inicio' %}">Inicio</a>
  <a href="{% url 'guest:catalogo' %}">Catálogo</a>
  <a href="{% url 'guest:servicios' %}">Servicios</a>
  {% if user.is_authenticated %}
  <a href="{% url 'customer:panel' %}">Mi panel</a>
  <form method="post" action="{% url 'account_logout' %}">{% csrf_token %}<button type="submit">Salir</button></form>
  {% else %}
  <a href="{% url 'guest:acceso' %}">Acceso</a>
  {% endif %}
</nav>
__FIN__
    crear_si_falta "footer.html" <<'__FIN__'
<footer>
  <p>{{ negocio.nombre_negocio|default:"3DForge Studio" }}</p>
</footer>
__FIN__

    local carpeta
    for carpeta in auth errors; do
        ir_a "templates/$carpeta"
        vacio_si_falta ".gitkeep"
    done
    ir_a "templates"
    local codigo
    for codigo in 403 404 500; do
        printf '<!doctype html>\n<html lang="es">\n<head><meta charset="utf-8"><title>Error %s</title></head>\n<body><h1>Error %s</h1><p><a href="/">Volver al inicio</a></p></body>\n</html>\n' "$codigo" "$codigo" \
            | crear_si_falta "${codigo}.html"
    done

    for carpeta in css js images vendor; do
        ir_a "static/$carpeta"
        vacio_si_falta ".gitkeep"
    done
    ir_a "static/css"
    vacio_si_falta "app.css"
    ir_a "static/js"
    vacio_si_falta "app.js"
    ir_a "media"
    vacio_si_falta ".gitkeep"
}

# ============================================================
# PASO 5: VERIFICACION Y MIGRACIONES
# ============================================================

paso_verificacion() {
    ir_raiz
    local py="python3"
    if [[ -x "$RAIZ/.venv/bin/python" ]]; then
        py="$RAIZ/.venv/bin/python"
    elif [[ -n ${VIRTUAL_ENV:-} && -x "$VIRTUAL_ENV/bin/python" ]]; then
        py="$VIRTUAL_ENV/bin/python"
    fi

    info "Verificando sintaxis de los archivos Python generados"
    if "$py" -m compileall -q apps config >/dev/null; then
        ok "Sintaxis correcta"
    else
        advertir "Hay errores de sintaxis; ejecute: $py -m compileall apps config"
    fi

    if ((INSTALAR)); then
        info "Instalando dependencias"
        "$py" -m pip install -r requirements.txt || advertir "Fallo la instalacion de dependencias"
    fi

    ((MIGRAR)) || return 0

    local faltan
    faltan="$("$py" - <<'__FIN__'
import importlib.util

modulos = ("django", "dj_database_url", "dotenv", "allauth", "axes")
faltan = [m for m in modulos if importlib.util.find_spec(m) is None]
if importlib.util.find_spec("psycopg") is None and importlib.util.find_spec("psycopg2") is None:
    faltan.append("psycopg")
print(" ".join(faltan))
__FIN__
)"
    if [[ -n $faltan ]]; then
        advertir "Faltan paquetes en el entorno ($faltan). Ejecute: pip install -r requirements.txt  y luego: python manage.py makemigrations"
        return 0
    fi
    if [[ ! -f .env ]] || ! grep -q '^DJANGO_SECRET_KEY=.' .env || ! grep -q '^DATABASE_URL=.' .env; then
        advertir ".env sin DJANGO_SECRET_KEY o DATABASE_URL; omito makemigrations."
        return 0
    fi

    info "Generando migraciones (no se ejecuta migrate)"
    if "$py" manage.py makemigrations core usuarios clientes catalogo cotizaciones encargos facturacion pagos crm notificaciones; then
        ok "Migraciones generadas"
        "$py" manage.py check || advertir "manage.py check reporto problemas"
    else
        advertir "makemigrations fallo; revise el error y ejecute: python manage.py makemigrations"
    fi
}

resumen() {
    echo
    echo "============================================================"
    echo " RESUMEN"
    echo "============================================================"
    echo "Raiz:               $RAIZ"
    echo "Archivos creados:   $CREADOS"
    echo "Actualizados:       $ACTUALIZADOS"
    echo "Sin cambios:        $SIN_CAMBIOS"
    echo "Omitidos (ya existen, stubs): $OMITIDOS"
    [[ -n $RESPALDO ]] && echo "Respaldos en:       $RESPALDO"
    if ((${#AVISOS[@]})); then
        echo
        echo "Avisos:"
        printf '  - %s\n' "${AVISOS[@]}"
    fi
    echo
    echo "Siguientes pasos:"
    echo "  1. Revise .env (DJANGO_SECRET_KEY, DATABASE_URL, DJANGO_ENV)."
    echo "  2. python manage.py makemigrations   (si no se ejecuto arriba)"
    echo "  3. python manage.py migrate          (BD vacia: ver nota sobre el SQL ya aplicado)"
    echo "  4. python manage.py createsuperuser"
    echo "============================================================"
}

main() {
    local arg
    for arg in "$@"; do
        case "$arg" in
            -h | --ayuda) ayuda; exit 0 ;;
            --instalar) INSTALAR=1 ;;
            --sin-migraciones) MIGRAR=0 ;;
            -*) fallar "Opcion desconocida: $arg" ;;
            *) RAIZ="$arg" ;;
        esac
    done
    resolver_raiz "$RAIZ"
    info "Raiz del proyecto: $RAIZ"
    ir_raiz

    paso_dependencias
    paso_configuracion
    app_core
    app_usuarios
    app_clientes
    app_catalogo
    app_cotizaciones
    app_encargos
    app_facturacion
    app_pagos
    app_crm
    app_notificaciones
    paso_portal
    paso_plantillas
    paso_verificacion
    resumen
}

main "$@"
