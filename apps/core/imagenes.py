import io
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image, ImageOps

from apps.core.constants import FORMATOS_IMAGEN, MAX_IMAGEN_BYTES

FORMATOS_PILLOW = {"JPEG", "PNG", "WEBP"}
MAX_PIXELES = 25_000_000


def validar_imagen_subida(archivo):
    """Valida extension, tamano y contenido de una imagen subida (JPG, PNG o WEBP)."""
    nombre = archivo.name or ""
    extension = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
    if extension not in FORMATOS_IMAGEN:
        raise ValidationError("Formato no permitido. Use JPG, PNG o WEBP.")
    if archivo.size > getattr(settings, "IMAGEN_MAX_BYTES", MAX_IMAGEN_BYTES):
        raise ValidationError("La imagen supera el tamaño máximo permitido.")
    imagen = getattr(archivo, "image", None)
    if imagen is None or imagen.format not in FORMATOS_PILLOW:
        raise ValidationError("El archivo no es una imagen válida.")
    return archivo


def normalizar_imagen(archivo, lado=None, maximo=None):
    """Reencoda la imagen (quita metadatos como el GPS) y la ajusta.

    lado: recorte cuadrado de lado x lado. maximo: cabe dentro de maximo x maximo sin recortar.
    Devuelve (ContentFile, extension).
    """
    archivo.seek(0)
    try:
        with Image.open(archivo) as original:
            if original.width * original.height > MAX_PIXELES:
                raise ValidationError("La imagen tiene demasiados píxeles.")
            imagen = ImageOps.exif_transpose(original)
            transparente = "A" in imagen.getbands() or imagen.mode == "P"
            imagen = imagen.convert("RGBA" if transparente else "RGB")
            if lado:
                imagen = ImageOps.fit(imagen, (lado, lado), Image.Resampling.LANCZOS)
            elif maximo:
                imagen = ImageOps.contain(imagen, (maximo, maximo), Image.Resampling.LANCZOS)
            salida = io.BytesIO()
            try:
                imagen.save(salida, format="WEBP", quality=85)
                extension = "webp"
            except (OSError, KeyError, ValueError):
                salida = io.BytesIO()
                imagen.save(salida, format="PNG", optimize=True)
                extension = "png"
    except (OSError, SyntaxError, Image.DecompressionBombError) as error:
        raise ValidationError("El archivo no es una imagen válida.") from error
    return ContentFile(salida.getvalue()), extension


def guardar_imagen_publica(carpeta, contenido, extension):
    return default_storage.save(f"{carpeta}/{uuid.uuid4().hex}.{extension}", contenido)


def eliminar_imagen(ruta):
    if ruta and default_storage.exists(ruta):
        default_storage.delete(ruta)
