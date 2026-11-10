import io
import logging
from email.mime.image import MIMEImage

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


def adjuntar_marca(mensaje, png):
    """Adjunta el logo como imagen incrustada (cid): se ve sin depender de URLs ni de formatos como WebP."""
    try:
        imagen = MIMEImage(png, _subtype="png")
        imagen.add_header("Content-ID", f"<{CID_MARCA}>")
        imagen.add_header("Content-Disposition", "inline", filename="marca.png")
        mensaje.mixed_subtype = "related"
        mensaje.attach(imagen)
    except Exception:
        registro.warning("No se pudo adjuntar el logo al correo", exc_info=True)


def construir_correo(destinatario, asunto, titulo, nombre="", parrafos=(), detalles=(), boton=None, nota=""):
    contexto, png = preparar_marca()
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
    mensaje = EmailMultiAlternatives(asunto, render_to_string("correo/notificacion.txt", contexto), to=[destinatario])
    mensaje.attach_alternative(render_to_string("correo/notificacion.html", contexto), "text/html")
    adjuntar_marca(mensaje, png)
    return mensaje
