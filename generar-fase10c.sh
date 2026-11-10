#!/usr/bin/env bash
set -Eeuo pipefail

readonly RAIZ_POR_DEFECTO="/home/mmancia/Projects/Web/3dforge-studio/3dforge-studio-web"

RAIZ=""
DIR_ACTUAL=""
RESPALDO=""
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


ayuda() {
    cat <<'__FIN__'
Uso: generar-fase10c.sh [opciones] [RAIZ_DEL_PROYECTO]

  -h, --ayuda    muestra esta ayuda

Fase 10C: correcciones de las pruebas exhaustivas.
  - Correos: corrige el error "EmailMessage no longer supports the undocumented `mixed_subtype`
    attribute" (Django 6.1 usa la API moderna de correo). El logo se incrusta con multipart/related y,
    si el envio con imagen fallara, se reintenta sin ella. Afecta a los avisos y a los correos de
    confirmacion de cuenta y de restablecer contrasena.
  - Login: la pagina que vuelve tras un error de credenciales (/cuenta/login/) ahora carga el script
    de acceso (boton para ver la contrasena y validacion del registro).
  - Base de datos: en desarrollo las conexiones ya no son persistentes (CONN_MAX_AGE=0). Con runserver
    cada peticion usa un hilo nuevo y las conexiones persistentes agotaban el pool de Supabase
    (EMAXCONNSESSION). Opciones nuevas en .env: DB_POOLER_TRANSACCION y DB_POOL_MAX.
No genera migraciones ni agrega dependencias. Archivos que usted edito: version nueva en <archivo>.propuesta.
__FIN__
}

PROPUESTAS=()

declare -A HASHES_STUB=(
    [apps/notificaciones/correo.py]=7a9c369470d005ed06a99bc94381723794169b77f5402d7e9cf3f52927e4ebc4
    [templates/correo/base.html]=a1d3c82d12b98caee54e4f15992aff8f2c2c8ea4554e3c1b6478cdc6ec9a7205
    [apps/notificaciones/services/notificaciones.py]=9f6586fb129dc556d804ef8994e7daadba8395a1e5ffc2c5568f3893da91292d
    [apps/notificaciones/tests/test_correos.py]=6bfb5103f7c9de281f92c264f58e8a26906cebdf1656b279766448518399135d
    [templates/layouts/base.html]=839b4537b0947455cbeec8575ace3091790c939398c93a2a6221b67ba28fb0d0
)

escribir_stub() {
    local rel destino tmp actual
    rel="$(rel_actual "$1")"
    validar_ruta "$rel"
    destino="$RAIZ/$rel"
    tmp="$(mktemp)"
    cat >"$tmp"
    if [[ ! -e $destino ]]; then
        mkdir -p -- "$(dirname -- "$destino")"
        mv -- "$tmp" "$destino"
        chmod 0644 -- "$destino"
        CREADOS=$((CREADOS + 1))
        return 0
    fi
    if cmp -s -- "$tmp" "$destino"; then
        rm -f -- "$tmp"
        SIN_CAMBIOS=$((SIN_CAMBIOS + 1))
        return 0
    fi
    actual="$(sha256sum -- "$destino" | cut -d' ' -f1)"
    if [[ ${HASHES_STUB[$rel]:-} == "$actual" ]]; then
        respaldar "$rel"
        rm -f -- "$destino"
        mv -- "$tmp" "$destino"
        chmod 0644 -- "$destino"
        ACTUALIZADOS=$((ACTUALIZADOS + 1))
    else
        mv -- "$tmp" "$destino.propuesta"
        PROPUESTAS+=("$rel")
        OMITIDOS=$((OMITIDOS + 1))
    fi
}

inyectar_bloque() {
    local archivo="$1" nombre="$2" ini fin contenido actual nuevo
    ini="# >>> ${nombre}"
    fin="# <<< ${nombre}"
    contenido="$(cat)"
    actual="$(leer "$archivo")" || fallar "No existe $(rel_actual "$archivo")"
    if [[ $actual == *"$ini"* ]]; then
        nuevo="${actual%%"$ini"*}${ini}"$'\n'"${contenido}"$'\n'"${fin}${actual#*"$fin"}"
    else
        nuevo="${actual}"$'\n\n'"${ini}"$'\n'"${contenido}"$'\n'"${fin}"
    fi
    printf '%s\n' "$nuevo" | escribir "$archivo"
}


elegir_python() {
    if [[ -x "$RAIZ/.venv/bin/python" ]]; then
        printf '%s' "$RAIZ/.venv/bin/python"
    elif [[ -x "$RAIZ/.venv/Scripts/python.exe" ]]; then
        printf '%s' "$RAIZ/.venv/Scripts/python.exe"
    elif [[ -n ${VIRTUAL_ENV:-} && -x "$VIRTUAL_ENV/bin/python" ]]; then
        printf '%s' "$VIRTUAL_ENV/bin/python"
    else
        printf '%s' "python3"
    fi
}

verificar_base() {
    [[ -f "$RAIZ/apps/notificaciones/correo.py" && -f "$RAIZ/config/settings/development.py" && -f "$RAIZ/templates/layouts/base.html" ]] \
        || fallar "Faltan archivos de la fase 10B. Ejecute primero generar-fase10b.sh."
}

paso_base_de_datos() {
    info "Base de datos: conexiones no persistentes en desarrollo"
    ir_a "config/settings"
    inyectar_bloque "development.py" "fase-10c" <<'__FIN__'
# runserver atiende cada peticion en un hilo nuevo: con conexiones persistentes cada hilo deja una conexion
# abierta hasta 10 minutos y se agota el pool de Supabase (EMAXCONNSESSION: max clients reached in session mode).
# En desarrollo cada conexion se cierra al terminar la peticion.
DATABASES["default"]["CONN_MAX_AGE"] = 0
DATABASES["default"]["CONN_HEALTH_CHECKS"] = False
__FIN__
    inyectar_bloque "base.py" "fase-10c" <<'__FIN__'
# Opciones para limitar las conexiones a Supabase (ver la seccion T de TASKLIST_USUARIO.txt):
#   DB_POOLER_TRANSACCION=True  -> usar con el pooler en modo transaccion (puerto 6543)
#   DB_POOL_MAX=4               -> pool de conexiones por proceso (requiere: pip install "psycopg[pool]")
if os.getenv("DB_POOLER_TRANSACCION", "False") == "True":
    DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True
    DATABASES["default"].setdefault("OPTIONS", {})["prepare_threshold"] = None
_pool_max = (os.getenv("DB_POOL_MAX") or "").strip()
if _pool_max.isdigit() and int(_pool_max) > 0:
    DATABASES["default"].setdefault("OPTIONS", {})["pool"] = {"min_size": 1, "max_size": int(_pool_max), "timeout": 15}
    DATABASES["default"]["CONN_MAX_AGE"] = 0
    DATABASES["default"]["CONN_HEALTH_CHECKS"] = False
__FIN__
    ir_raiz
    asegurar_claves ".env.example" DB_POOLER_TRANSACCION DB_POOL_MAX
}

paso_correos() {
    info "Correos: imagen incrustada compatible con Django 6.1 y reintento sin imagen"
    ir_a "apps/notificaciones"
    escribir_stub "correo.py" <<'__FIN__'
import email.policy
import io
import logging

from django.conf import settings
from django.core.files.storage import default_storage
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from PIL import Image, ImageDraw, ImageOps

from apps.core.models import ConfiguracionNegocio

registro = logging.getLogger(__name__)

COLOR_MARCA = "#167C80"
CID_MARCA = "marca-logo"
NOMBRE_DEFECTO = "3DForge Studio"
ALTO_IMAGEN = 96


def sitio_url():
    """Direccion publica del sitio (para los enlaces de los correos). Se define con SITIO_URL en .env."""
    return (getattr(settings, "SITIO_URL", "") or "http://localhost:8000").rstrip("/")


def _configuracion():
    try:
        return ConfiguracionNegocio.objects.first()
    except Exception:
        return None


def _a_png(imagen):
    salida = io.BytesIO()
    imagen.save(salida, format="PNG", optimize=True)
    return salida.getvalue()


def icono_cubo(tamano=ALTO_IMAGEN):
    """Icono por defecto (cubo blanco) para el encabezado cuando no hay logo configurado."""
    imagen = Image.new("RGBA", (tamano, tamano), (255, 255, 255, 0))
    dibujo = ImageDraw.Draw(imagen)
    centro = tamano / 2
    radio = tamano * 0.44
    dx = radio * 0.866
    vertices = [
        (centro, centro - radio),
        (centro + dx, centro - radio / 2),
        (centro + dx, centro + radio / 2),
        (centro, centro + radio),
        (centro - dx, centro + radio / 2),
        (centro - dx, centro - radio / 2),
    ]
    blanco = (255, 255, 255, 255)
    grosor = max(3, tamano // 24)
    dibujo.line(vertices + [vertices[0]], fill=blanco, width=grosor, joint="curve")
    for extremo in (vertices[5], vertices[1], vertices[3]):
        dibujo.line([(centro, centro), extremo], fill=blanco, width=grosor)
    return imagen


def _logo_png(configuracion):
    if configuracion is None or not configuracion.logo:
        return None
    try:
        with default_storage.open(configuracion.logo, "rb") as archivo:
            with Image.open(archivo) as original:
                original.load()
                imagen = ImageOps.exif_transpose(original).convert("RGBA")
        imagen = ImageOps.contain(imagen, (ALTO_IMAGEN * 3, ALTO_IMAGEN), Image.Resampling.LANCZOS)
        return _a_png(imagen)
    except Exception:
        registro.warning("No se pudo leer el logo para los correos", exc_info=True)
        return None


def preparar_marca():
    """Devuelve (contexto de plantilla, bytes PNG del logo o del icono por defecto)."""
    configuracion = _configuracion()
    png = _logo_png(configuracion)
    es_logo = png is not None
    if png is None:
        png = _a_png(icono_cubo())
    contexto = {
        "marca": {
            "nombre": (configuracion.nombre_negocio if configuracion else "") or NOMBRE_DEFECTO,
            "color": COLOR_MARCA,
            "es_logo": es_logo,
            "correo": getattr(configuracion, "correo", None),
            "telefono": getattr(configuracion, "telefono", None),
            "direccion": getattr(configuracion, "direccion", None),
            "web": getattr(configuracion, "sitio_web", None),
        },
        "cid_marca": CID_MARCA,
        "sitio_url": sitio_url(),
    }
    return contexto, png


class CorreoConMarca(EmailMultiAlternatives):
    """Correo multiparte cuyo HTML incluye el logo como imagen incrustada (multipart/related).

    Django 6 usa la API moderna de correo: ya no existe mixed_subtype. Se arma la parte "related"
    sobre el HTML al generar el mensaje.
    """

    imagen_png = None

    def message(self, *, policy=email.policy.default):
        mensaje = super().message(policy=policy)
        if self.imagen_png:
            try:
                html = mensaje.get_body(preferencelist=("html",))
                if html is not None:
                    html.add_related(
                        self.imagen_png, "image", "png", cid=f"<{CID_MARCA}>", filename="marca.png", disposition="inline"
                    )
            except Exception:
                registro.warning("No se pudo incrustar el logo en el correo", exc_info=True)
        return mensaje


def adjuntar_marca(mensaje, png):
    """Convierte un correo multiparte existente (p. ej. el de allauth) para incrustar el logo."""
    try:
        if isinstance(mensaje, EmailMultiAlternatives):
            mensaje.__class__ = CorreoConMarca
            mensaje.imagen_png = png
    except Exception:
        registro.warning("No se pudo preparar el logo del correo", exc_info=True)


def construir_correo(destinatario, asunto, titulo, nombre="", parrafos=(), detalles=(), boton=None, nota="", con_imagen=True):
    contexto, png = preparar_marca()
    if not con_imagen:
        contexto["cid_marca"] = ""
    contexto.update(
        {
            "asunto": asunto,
            "titulo": titulo,
            "nombre": nombre,
            "parrafos": [parrafo for parrafo in parrafos if parrafo],
            "detalles": [{"etiqueta": etiqueta, "valor": valor} for etiqueta, valor in detalles],
            "boton": boton,
            "nota": nota,
        }
    )
    mensaje = CorreoConMarca(asunto, render_to_string("correo/notificacion.txt", contexto), to=[destinatario])
    mensaje.attach_alternative(render_to_string("correo/notificacion.html", contexto), "text/html")
    if con_imagen:
        mensaje.imagen_png = png
    return mensaje
__FIN__
    ir_a "apps/notificaciones/services"
    escribir_stub "notificaciones.py" <<'__FIN__'
import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.notificaciones.correo import construir_correo, sitio_url
from apps.notificaciones.models import Notificacion
from apps.notificaciones.selectors.notificaciones import destino
from apps.usuarios.constants import ESTADO_ACTIVO, GRUPO_ADMINISTRADOR, GRUPO_OPERADOR
from apps.usuarios.models import Usuario

registro = logging.getLogger(__name__)
VENTANA_DUPLICADO = 30
NOTA_CLIENTE = "Si tiene alguna duda, puede escribirnos desde la sección Soporte de su cuenta."


def personal_activo():
    return (
        Usuario.objects.filter(is_active=True, estado_id=ESTADO_ACTIVO)
        .filter(groups__name__in=[GRUPO_OPERADOR, GRUPO_ADMINISTRADOR])
        .exclude(empleado__activo=False)
        .distinct()
    )


def _resolver(valor):
    """Los parrafos y detalles pueden ser una funcion: se evalua al confirmar la transaccion, con datos ya actualizados."""
    return valor() if callable(valor) else valor


def _enviar_correo(usuario, asunto, mensaje, ruta=None, parrafos=None, detalles=None, boton=None):
    enlace = {"texto": boton or "Ver los detalles", "url": f"{sitio_url()}{ruta}"} if ruta else None
    for con_imagen in (True, False):
        try:
            correo = construir_correo(
                usuario.correo,
                asunto,
                asunto,
                nombre=usuario.nombres,
                parrafos=_resolver(parrafos) or [mensaje],
                detalles=_resolver(detalles) or (),
                boton=enlace,
                nota="" if usuario.is_staff else NOTA_CLIENTE,
                con_imagen=con_imagen,
            )
            correo.send()
            return
        except Exception:
            registro.exception(
                "No se pudo enviar el correo a %s%s", usuario.correo, " (se reintenta sin el logo)" if con_imagen else ""
            )


def notificar(usuario, titulo, mensaje, tipo, referencia_id=None, correo=False, parrafos=None, detalles=None, boton=None):
    if usuario is None or not usuario.is_active:
        return None
    titulo = titulo[:120]
    limite = timezone.now() - timedelta(seconds=VENTANA_DUPLICADO)
    existente = Notificacion.objects.filter(
        usuario=usuario, tipo=tipo, referencia_id=referencia_id, titulo=titulo, fecha_creacion__gte=limite
    ).first()
    if existente is not None:
        return existente
    notificacion = Notificacion.objects.create(
        usuario=usuario, titulo=titulo, mensaje=mensaje, tipo=tipo, referencia_id=referencia_id
    )
    if correo:
        ruta = destino(notificacion, usuario)
        transaction.on_commit(lambda: _enviar_correo(usuario, titulo, mensaje, ruta, parrafos, detalles, boton))
    return notificacion


def notificar_personal(titulo, mensaje, tipo, referencia_id=None):
    return [notificar(usuario, titulo, mensaje, tipo, referencia_id) for usuario in personal_activo()]


def marcar_leida(usuario, notificacion_id):
    if not str(notificacion_id).isdigit():
        return 0
    return Notificacion.objects.filter(usuario=usuario, pk=int(notificacion_id), leida=False).update(leida=True)


def marcar_todas(usuario):
    return Notificacion.objects.filter(usuario=usuario, leida=False).update(leida=True)
__FIN__
    ir_a "templates/correo"
    escribir_stub "base.html" <<'__FIN__'
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% if asunto %}{{ asunto }}{% else %}{{ marca.nombre }}{% endif %}</title>
</head>
<body style="margin:0;padding:0;background:#eef3f3;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#eef3f3;">
    <tr><td align="center" style="padding:24px 12px;">
      <table role="presentation" width="600" cellspacing="0" cellpadding="0" style="width:100%;max-width:600px;background:#ffffff;border-radius:12px;overflow:hidden;font-family:Roboto,'Segoe UI',Arial,sans-serif;color:#1c2b2d;">
        <tr><td style="background:{{ marca.color }};padding:18px 24px;">
          <table role="presentation" cellspacing="0" cellpadding="0"><tr>
            {% if cid_marca %}<td valign="middle" style="padding-right:12px;">{% if marca.es_logo %}<span style="display:inline-block;background:#ffffff;border-radius:8px;padding:5px 8px;"><img src="cid:{{ cid_marca }}" alt="" height="36" style="display:block;height:36px;width:auto;border:0;"></span>{% else %}<img src="cid:{{ cid_marca }}" alt="" width="36" height="36" style="display:block;width:36px;height:36px;border:0;">{% endif %}</td>{% endif %}
            <td valign="middle" style="font-size:20px;font-weight:600;color:#ffffff;line-height:1.2;">{{ marca.nombre }}</td>
          </tr></table>
        </td></tr>
        <tr><td style="padding:28px 24px 12px 24px;">
{% block contenido %}{% endblock %}
        </td></tr>
        <tr><td style="padding:16px 24px 24px 24px;border-top:1px solid #e3eaeb;font-size:12px;line-height:1.6;color:#6b7c7e;">
          <strong style="color:#3b4d4f;">{{ marca.nombre }}</strong>{% if marca.telefono %} · {{ marca.telefono }}{% endif %}{% if marca.correo %} · {{ marca.correo }}{% endif %}{% if marca.direccion %}<br>{{ marca.direccion }}{% endif %}{% if marca.web %}<br>{{ marca.web }}{% endif %}<br>
          Este mensaje se envió de forma automática; por favor no responda a este correo.
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
__FIN__
    ir_a "apps/notificaciones/tests"
    escribir_stub "test_correos.py" <<'__FIN__'
import io
import shutil
import tempfile
from decimal import Decimal

from unittest.mock import patch

from django.core import mail
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from apps.catalogo.models import Producto
from apps.core.models import ConfiguracionNegocio
from apps.cotizaciones.services import cotizaciones as servicios_cot
from apps.cotizaciones.tests.utiles import AlmacenTemporalMixin, crear_cliente, crear_personal, crear_servicio
from apps.encargos.services import compras, encargos
from apps.facturacion.models import Factura
from apps.notificaciones import correo as modulo_correo
from apps.notificaciones.correo import CID_MARCA, COLOR_MARCA, construir_correo, icono_cubo
from apps.notificaciones.services.notificaciones import notificar
from apps.pagos.models import EstadoPago, MetodoPago, Pago
from apps.usuarios.constants import GRUPO_ADMINISTRADOR, GRUPO_OPERADOR
from apps.usuarios.tests.utiles import crear_usuario, iniciar_sesion

SITIO = "https://taller.test"


def html_de(correo):
    return correo.alternatives[0][0]


def logo_adjunto(correo):
    """Bytes del logo incrustado (Content-ID) en el mensaje ya armado, o None."""
    for parte in correo.message().walk():
        if parte.get("Content-ID") == f"<{CID_MARCA}>":
            return parte.get_payload(decode=True)
    return None


def tiene_parte_related(correo):
    return any(parte.get_content_type() == "multipart/related" for parte in correo.message().walk())


class MarcaEnCorreosTests(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        ConfiguracionNegocio.objects.all().delete()
        self._media = tempfile.mkdtemp()
        contexto = override_settings(MEDIA_ROOT=self._media)
        contexto.enable()
        self.addCleanup(contexto.disable)
        self.addCleanup(shutil.rmtree, self._media, ignore_errors=True)

    def correo(self):
        return construir_correo(
            "ana@example.com", "Asunto de prueba", "Titulo de prueba", nombre="Ana",
            parrafos=["Primer párrafo.", "Segundo párrafo."], detalles=[("Total", "$10.00")],
            boton={"texto": "Ver mi cotización", "url": f"{SITIO}/cliente/cotizaciones/1/"},
        )

    def test_encabezado_con_el_color_el_nombre_y_el_icono_por_defecto(self):
        correo = self.correo()
        html = html_de(correo)
        for texto in (COLOR_MARCA, "3DForge Studio", f"cid:{CID_MARCA}", "Titulo de prueba", "Hola Ana", "Primer párrafo.", "Total", "$10.00", "Ver mi cotización"):
            self.assertIn(texto, html)
        self.assertNotIn("background:#ffffff;border-radius:8px;padding:5px 8px", html)
        self.assertTrue(tiene_parte_related(correo))
        icono = Image.open(io.BytesIO(logo_adjunto(correo)))
        self.assertEqual(icono.size, (96, 96))
        self.assertIsNotNone(icono.getchannel("A").getbbox())
        self.assertIn("Ver mi cotización: " + f"{SITIO}/cliente/cotizaciones/1/", correo.body)
        self.assertIn("Total: $10.00", correo.body)
        self.assertNotIn("&amp;", correo.body)

    def test_con_logo_configurado_se_usa_el_logo_y_el_nombre_del_negocio(self):
        buffer = io.BytesIO()
        Image.new("RGB", (300, 100), (20, 120, 200)).save(buffer, format="WEBP")
        ruta = default_storage.save("negocio/logo.webp", ContentFile(buffer.getvalue()))
        ConfiguracionNegocio.objects.all().delete()
        ConfiguracionNegocio.objects.create(
            nombre_negocio="Taller Prueba", correo="info@taller.test", telefono="+503 2200-0000", logo=ruta
        )
        cache.clear()
        correo = self.correo()
        html = html_de(correo)
        self.assertIn("Taller Prueba", html)
        self.assertIn("background:#ffffff;border-radius:8px;padding:5px 8px", html)
        self.assertIn("info@taller.test", html)
        logo = Image.open(io.BytesIO(logo_adjunto(correo)))
        self.assertEqual(logo.format, "PNG")
        self.assertEqual(logo.size[1], 96)
        self.assertGreater(logo.size[0], logo.size[1])

    def test_si_el_logo_esta_roto_se_vuelve_al_icono(self):
        ConfiguracionNegocio.objects.all().delete()
        ConfiguracionNegocio.objects.create(nombre_negocio="Taller Prueba", logo="negocio/no-existe.png")
        correo = self.correo()
        self.assertEqual(Image.open(io.BytesIO(logo_adjunto(correo))).size, (96, 96))
        self.assertNotIn("padding:5px 8px", html_de(correo))

    def test_sin_imagen_el_correo_no_referencia_el_logo(self):
        correo = construir_correo("ana@example.com", "Asunto", "Titulo", con_imagen=False)
        self.assertNotIn("cid:", html_de(correo))
        self.assertIsNone(logo_adjunto(correo))

    def test_el_mensaje_se_arma_con_la_api_moderna_de_django(self):
        correo = self.correo()
        mensaje = correo.message()
        tipos = [parte.get_content_type() for parte in mensaje.walk()]
        for esperado in ("multipart/alternative", "text/plain", "multipart/related", "text/html", "image/png"):
            self.assertIn(esperado, tipos)
        self.assertFalse(hasattr(correo, "mixed_subtype"))
        imagenes = [parte for parte in mensaje.walk() if parte.get_content_type() == "image/png"]
        self.assertEqual(len(imagenes), 1)
        self.assertEqual(imagenes[0].get_content_disposition(), "inline")
        self.assertEqual(imagenes[0]["Content-ID"], f"<{CID_MARCA}>")

    def test_el_icono_por_defecto_es_blanco_sobre_transparente(self):
        icono = icono_cubo(96)
        self.assertEqual(icono.mode, "RGBA")
        self.assertEqual(icono.getpixel((0, 0))[3], 0)


@override_settings(SITIO_URL=SITIO)
class CorreosDeEventosTests(AlmacenTemporalMixin, TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.usuario, self.cliente = crear_cliente("ana@example.com")
        self.operador = crear_personal("operador@example.com")

    def test_cotizacion_enviada_detalla_importes_y_enlaza_a_la_cotizacion(self):
        servicio = crear_servicio()
        cotizacion = servicios_cot.solicitar_cotizacion(
            self.cliente, self.usuario, servicio, Decimal("2"), "Pieza especial", "Necesito una pieza especial."
        )
        lineas = [{"id": d.pk, "cantidad": Decimal("2"), "precio_unitario": Decimal("15.00"), "descuento": Decimal("0")} for d in cotizacion.detalles.all()]
        servicios_cot.revisar_cotizacion(cotizacion.pk, self.operador, lineas, observaciones="Entrega en 5 días", plazo_entrega_dias=5)
        with self.captureOnCommitCallbacks(execute=True):
            servicios_cot.enviar_cotizacion(cotizacion.pk, self.operador)
        cliente = [c for c in mail.outbox if c.to == ["ana@example.com"]]
        self.assertEqual(len(cliente), 1)
        correo = cliente[0]
        self.assertEqual(correo.subject, f"Cotización {cotizacion.codigo} disponible")
        html = html_de(correo)
        for texto in ("Ver mi cotización", f"{SITIO}{reverse('customer:cotizacion', args=[cotizacion.pk])}", "Pieza especial", "2 × $15.00 = $30.00", "$33.90", "Plazo de entrega", "5 días", "Válida hasta", "Entrega en 5 días", COLOR_MARCA, "Soporte"):
            self.assertIn(texto, html)
        self.assertIn("Total: $33.90", correo.body)
        self.assertIn(f"{SITIO}{reverse('customer:cotizacion', args=[cotizacion.pk])}", correo.body)
        self.assertTrue(tiene_parte_related(correo))
        self.assertIsNotNone(logo_adjunto(correo))

    def test_pedido_cancelado_explica_que_paso(self):
        producto = Producto.objects.create(sku="MAIL-001", nombre="Producto correo", precio=Decimal("10.00"), stock=5, stock_minimo=1)
        with self.captureOnCommitCallbacks(execute=True):
            pedido = compras.confirmar_compra_api(self.cliente, self.usuario, [{"producto_id": producto.pk, "cantidad": 1}], "token-correo-0001")
        registrado = [c for c in mail.outbox if c.subject.startswith("Pedido") and "registrado" in c.subject]
        self.assertEqual(len(registrado), 1)
        self.assertIn("Compra en la tienda", html_de(registrado[0]))
        self.assertIn(f"{SITIO}{reverse('customer:pedido', args=[pedido.pk])}", html_de(registrado[0]))
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            encargos.cancelar_por_cliente(pedido.pk, self.usuario)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Su pedido fue cancelado", html_de(mail.outbox[0]))
        self.assertIn("Cancelado", html_de(mail.outbox[0]))

    def test_pago_registrado_informa_monto_metodo_y_saldo(self):
        factura = Factura.objects.create(
            cliente=self.cliente, numero_factura="FAC-MAIL-1", nombre_facturacion="Ana",
            subtotal=Decimal("50.00"), total=Decimal("50.00"), saldo_pendiente=Decimal("50.00"),
        )
        metodo, _ = MetodoPago.objects.get_or_create(nombre="Efectivo")
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            Pago.objects.create(factura=factura, metodo_pago=metodo, monto=Decimal("20.00"), estado=EstadoPago.CONFIRMADO)
        pagos = [c for c in mail.outbox if c.subject.startswith("Pago #")]
        self.assertEqual(len(pagos), 1)
        html = html_de(pagos[0])
        for texto in ("Monto pagado", "$20.00", "Efectivo", "Saldo pendiente", "FAC-MAIL-1", "Ver mi factura"):
            self.assertIn(texto, html)


@override_settings(SITIO_URL=SITIO)
class ReintentoSinImagenTests(TestCase):
    def test_si_falla_el_envio_con_logo_se_reintenta_sin_el(self):
        usuario, _ = crear_cliente("ana@example.com")
        original = modulo_correo.construir_correo
        llamadas = []

        def con_fallo(*args, **kwargs):
            llamadas.append(kwargs.get("con_imagen", True))
            if kwargs.get("con_imagen", True):
                raise RuntimeError("fallo simulado")
            return original(*args, **kwargs)

        with patch("apps.notificaciones.services.notificaciones.construir_correo", side_effect=con_fallo):
            with self.captureOnCommitCallbacks(execute=True):
                notificar(usuario, "Aviso con correo", "Mensaje", "cotizacion", 1, correo=True)
        self.assertEqual(llamadas, [True, False])
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn("cid:", html_de(mail.outbox[0]))


class LoginConScriptTests(TestCase):
    def test_el_login_con_error_carga_el_script_de_acceso(self):
        crear_cliente("ana@example.com")
        respuesta = self.client.post(reverse("account_login"), {"login": "ana@example.com", "password": "clave-mala-1"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "js/vistas/guest/acceso.js")
        self.assertContains(respuesta, "toggle-password")

    def test_el_script_de_acceso_no_se_carga_dos_veces(self):
        contenido = self.client.get(reverse("guest:acceso")).content.decode()
        self.assertEqual(contenido.count("js/vistas/guest/acceso.js"), 1)


@override_settings(SITIO_URL=SITIO)
class CorreosDeCuentaTests(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def test_el_correo_de_confirmacion_lleva_la_marca_y_el_enlace(self):
        import json

        datos = {"nombres": "Luis", "apellidos": "Pérez", "correo": "luis.correo@example.com", "password": "Clave-Segura-123"}
        self.client.post(reverse("api:registro"), json.dumps(datos), content_type="application/json")
        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        html = html_de(correo)
        prefijo = reverse("account_confirm_email", args=["CLAVEX"]).split("CLAVEX")[0]
        for texto in ("Confirmar mi correo", prefijo, "Hola Luis", COLOR_MARCA, f"cid:{CID_MARCA}"):
            self.assertIn(texto, html)
        self.assertIn(prefijo, correo.body)
        self.assertIn("Hola Luis", correo.body)
        self.assertTrue(tiene_parte_related(correo))
        self.assertIsNotNone(logo_adjunto(correo))

    def test_el_correo_de_restablecer_contrasena_lleva_la_marca_y_el_enlace(self):
        import json

        crear_cliente("ana@example.com")
        self.client.post(reverse("api:recuperar"), json.dumps({"correo": "ana@example.com"}), content_type="application/json")
        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        html = html_de(correo)
        prefijo = reverse("account_reset_password_from_key", kwargs={"uidb36": "UIDX", "key": "KEYX"}).split("UIDX")[0]
        for texto in ("Elegir una contraseña nueva", prefijo, COLOR_MARCA):
            self.assertIn(texto, html)
        self.assertIn(prefijo, correo.body)


class BarraAdministradorTests(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        iniciar_sesion(self.client, crear_usuario("admin@example.com", GRUPO_ADMINISTRADOR, is_staff=True))

    def test_los_catalogos_y_la_gestion_viven_en_menus_desplegables(self):
        html = self.client.get(reverse("administrator:configuracion")).content.decode()
        self.assertIn("Catálogos", html)
        self.assertIn("Gestión", html)
        self.assertGreaterEqual(html.count('data-bs-toggle="dropdown"'), 3)
        inicio_catalogos = html.index("Catálogos")
        for nombre in ("administrator:inventario", "administrator:servicios", "administrator:cotizador"):
            self.assertIn(f'href="{reverse(nombre)}"', html[inicio_catalogos:])
        for nombre in ("administrator:usuarios", "administrator:configuracion", "administrator:ventas", "operator:panel", "administrator:dashboard"):
            self.assertIn(f'href="{reverse(nombre)}"', html)

    def test_el_grupo_se_marca_activo_en_sus_paginas(self):
        self.assertIn("dropdown-toggle active", self.client.get(reverse("administrator:inventario")).content.decode())
        self.assertIn("dropdown-toggle active", self.client.get(reverse("administrator:cotizador")).content.decode())
        self.assertIn("dropdown-toggle active", self.client.get(reverse("administrator:usuarios")).content.decode())

    def test_el_operador_no_ve_los_menus_de_administracion(self):
        self.client.logout()
        iniciar_sesion(self.client, crear_usuario("op@example.com", GRUPO_OPERADOR, is_staff=True))
        html = self.client.get(reverse("operator:clientes")).content.decode()
        self.assertNotIn("Catálogos", html)
        self.assertNotIn(f'href="{reverse("administrator:inventario")}"', html)
__FIN__
}

paso_login() {
    info "Login: el script de acceso tambien en las paginas de allauth"
    ir_a "templates/layouts"
    escribir_stub "base.html" <<'__FIN__'
{% load static %}<!doctype html>
<html lang="es" data-bs-theme="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <script>
    (function () {
      try {
        var tema = localStorage.getItem("tema");
        if (!tema) { tema = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"; }
        document.documentElement.setAttribute("data-bs-theme", tema);
      } catch (error) {
        document.documentElement.setAttribute("data-bs-theme", "light");
      }
    })();
  </script>
  <title>{% block titulo %}{% endblock %} | {{ negocio.nombre_negocio|default:"3DForge Studio" }}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,0,0&display=block" rel="stylesheet">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <link href="{% static 'css/app.css' %}" rel="stylesheet">
  <link href="{% static 'css/componentes.css' %}" rel="stylesheet">
  <link href="{% static 'css/perfil.css' %}" rel="stylesheet">
  {% block estilos %}{% endblock %}
</head>
<body>
  <a class="visually-hidden-focusable saltar-contenido" href="#contenido-principal">Saltar al contenido</a>
  {% block cuerpo %}{% block contenido %}{% endblock %}{% endblock %}
  {% include "components/mensajes.html" %}
  <script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
  <script src="{% static 'js/components/tema.js' %}"></script>
  <script src="{% static 'js/components/toasts.js' %}"></script>
  <script src="{% static 'js/components/formularios.js' %}"></script>
  <script src="{% static 'js/components/ui.js' %}"></script>
  <script src="{% static 'js/components/foto.js' %}"></script>
  {% if request.resolver_match.namespace %}
  {% with ruta="js/vistas/"|add:request.resolver_match.namespace|add:"/"|add:request.resolver_match.url_name|add:".js" %}
  <script src="{% static ruta %}"></script>
  {% endwith %}
  {% endif %}
  {% if request.resolver_match.url_name == "account_login" or request.resolver_match.url_name == "account_signup" %}
  <script src="{% static 'js/vistas/guest/acceso.js' %}"></script>
  {% endif %}
  {% block scripts %}{% endblock %}
</body>
</html>
__FIN__
}

paso_tasklist() {
    ir_raiz
    [[ -f TASKLIST_USUARIO.txt ]] || return 0
    inyectar_bloque "TASKLIST_USUARIO.txt" "fase-10c" <<'__FIN__'

=== T. CORRECCIONES DE LAS PRUEBAS EXHAUSTIVAS (generar-fase10c.sh) ===
[ ] T1. Detenga TODO lo que use la base de datos (runserver, pruebas de PyCharm, consolas de Python, el servidor de su companero si
        comparte la misma base) y espere 1 o 2 minutos para que Supabase libere las conexiones que quedaron abiertas.
        Si sigue el error EMAXCONNSESSION, vea quien las ocupa en el editor SQL de Supabase:
          select usename, application_name, state, count(*) from pg_stat_activity group by 1,2,3 order by 4 desc;
        El limite de 15 es el "Pool size" del proyecto (configuracion de la base de datos / conexion por pooler): puede subirlo.
        Si prefiere no depender de ese limite, use el pooler en modo transaccion: DATABASE_URL con el puerto 6543 y en .env
        DB_POOLER_TRANSACCION=True. Opcional: DB_POOL_MAX=4 (instalar antes: pip install "psycopg[pool]").
[ ] T2. Reinicie el servidor y ejecute: python manage.py test  (envieme el resumen).
[ ] T3. Correos: "Olvide mi contrasena" con un correo registrado, una cotizacion enviada y un pedido cancelado. Deben llegar con el
        encabezado de la marca, el logo (o el cubo) y el boton. Si algun envio falla veria en la consola "se reintenta sin el logo".
[ ] T4. Login: equivocarse de contrasena y en la pagina que vuelve probar el ojo (mostrar/ocultar). Despues entrar con las
        credenciales correctas. Atencion: tras 5 intentos fallidos con el mismo correo, django-axes bloquea 30 minutos (pagina
        "Acceso bloqueado") y allauth limita los intentos seguidos; si probo muchas veces, desbloquee con:
          python manage.py axes_reset      (y reinicie el servidor para limpiar el limite de allauth, que vive en memoria).
        Si con las credenciales correctas el error sigue, envieme el TEXTO exacto del mensaje y las lineas del servidor.
[ ] T5. Google (el error que vio era de la base de datos, no de OAuth). Compruebe, con la base ya estable:
          - .env: GOOGLE_CLIENT_ID y GOOGLE_CLIENT_SECRET (reinicie PyCharm/servidor: el .env se lee al arrancar).
          - Google Cloud Console > Credenciales > ID de cliente OAuth tipo "Aplicacion web" > URI de redireccionamiento autorizados:
              http://127.0.0.1:8000/cuenta/google/login/callback/
              http://localhost:8000/cuenta/google/login/callback/
            (127.0.0.1 y localhost cuentan como direcciones distintas: use en el navegador la misma que registro).
          - Pantalla de consentimiento en modo "Prueba": solo entran las cuentas agregadas como usuarios de prueba.
          - Google no acepta IPs ni HTTP fuera de localhost: su companera NO podra usar "Ingresar con Google" contra
            http://100.78.139.27:8000. Pruebelo desde su PC (localhost) o con un dominio HTTPS publico.
[ ] T6. Pendiente de la fase 10 de produccion: pool de conexiones, servir /media/, HTTPS y variables de entorno.
__FIN__
}

paso_pruebas_y_cierre() { :; }

paso_verificacion() {
    ir_raiz
    local py
    py="$(elegir_python)"
    info "Verificando sintaxis"
    if "$py" -m compileall -q apps config >/dev/null; then
        ok "Sintaxis correcta"
    else
        advertir "Errores de sintaxis: $py -m compileall apps config"
        return 0
    fi
    [[ -f .env ]] || return 0
    if "$py" -c "import django" >/dev/null 2>&1; then
        "$py" manage.py check >/dev/null 2>&1 && ok "manage.py check sin problemas" \
            || advertir "manage.py check reporto problemas; ejecutelo para ver el detalle."
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
    echo "Omitidos/propuestas: $OMITIDOS"
    [[ -n $RESPALDO ]] && echo "Respaldos en:       $RESPALDO"
    if ((${#PROPUESTAS[@]})); then
        echo
        echo "Archivos que usted ya habia editado (version nueva en <archivo>.propuesta):"
        printf '  - %s\n' "${PROPUESTAS[@]}"
    fi
    if ((${#AVISOS[@]})); then
        echo
        echo "Avisos:"
        printf '  - %s\n' "${AVISOS[@]}"
    fi
    echo
    echo "Siguiente: detenga los procesos que usan la base, espere 1-2 minutos, reinicie el servidor y ejecute python manage.py test (seccion T de la tasklist)."
    echo "============================================================"
}

main() {
    local arg
    for arg in "$@"; do
        case "$arg" in
            -h | --ayuda) ayuda; exit 0 ;;
            -*) fallar "Opcion desconocida: $arg" ;;
            *) RAIZ="$arg" ;;
        esac
    done
    resolver_raiz "$RAIZ"
    verificar_base
    info "Raiz del proyecto: $RAIZ"
    ir_raiz

    paso_base_de_datos
    paso_correos
    paso_login
    paso_tasklist
    paso_verificacion
    resumen
}

main "$@"
