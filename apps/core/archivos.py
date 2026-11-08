import os
import re
import struct

from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404

from apps.core.constants import FORMATOS_ARCHIVO, MAX_ARCHIVO_BYTES

EXTENSIONES = {
    "stl": "STL",
    "obj": "OBJ",
    "3mf": "3MF",
    "step": "STEP",
    "stp": "STEP",
    "png": "PNG",
    "jpg": "JPG",
    "jpeg": "JPG",
    "pdf": "PDF",
}

TEXTO_PLANO = re.compile(rb"[\x09\x0a\x0d\x20-\x7e\x80-\xff]*")


def nombre_seguro(nombre):
    base = os.path.basename(str(nombre).replace("\\", "/"))
    base = re.sub(r"[^\w.\- ]", "_", base, flags=re.UNICODE).strip(" .")
    return base[:150]


def _leer_cabecera(archivo, tamano=1024):
    archivo.seek(0)
    datos = archivo.read(tamano)
    archivo.seek(0)
    return datos


def _stl_valido(archivo, cabecera):
    if cabecera.startswith(b"solid") and b"\x00" not in cabecera:
        return True
    if archivo.size < 84:
        return False
    archivo.seek(80)
    triangulos = struct.unpack("<I", archivo.read(4))[0]
    archivo.seek(0)
    return archivo.size == 84 + 50 * triangulos


def _contenido_coincide(formato, archivo, cabecera):
    if formato == "STL":
        return _stl_valido(archivo, cabecera)
    if formato == "OBJ":
        return bool(TEXTO_PLANO.fullmatch(cabecera))
    if formato == "3MF":
        return cabecera.startswith(b"PK\x03\x04")
    if formato == "STEP":
        return cabecera.lstrip().startswith(b"ISO-10303-21")
    if formato == "PNG":
        return cabecera.startswith(b"\x89PNG\r\n\x1a\n")
    if formato == "JPG":
        return cabecera.startswith(b"\xff\xd8\xff")
    if formato == "PDF":
        return cabecera.startswith(b"%PDF-")
    return False


def validar_archivo(archivo):
    nombre = nombre_seguro(archivo.name)
    if not nombre or "." not in nombre:
        raise ValidationError("El archivo debe tener una extensión.", code="archivo_sin_extension")
    formato = EXTENSIONES.get(nombre.rsplit(".", 1)[-1].lower())
    if formato is None:
        raise ValidationError(
            f"Formato no permitido. Formatos válidos: {', '.join(FORMATOS_ARCHIVO)}.", code="formato_no_permitido"
        )
    if archivo.size <= 0:
        raise ValidationError("El archivo está vacío.", code="archivo_vacio")
    maximo = getattr(settings, "MAX_ARCHIVO_BYTES", MAX_ARCHIVO_BYTES)
    if archivo.size > maximo:
        raise ValidationError("El archivo supera el tamaño máximo permitido.", code="archivo_grande")
    if not _contenido_coincide(formato, archivo, _leer_cabecera(archivo)):
        raise ValidationError("El contenido del archivo no corresponde a su formato.", code="contenido_invalido")
    return formato, nombre


def respuesta_descarga(almacenamiento, ruta, nombre):
    if not ruta or not almacenamiento.exists(ruta):
        raise Http404
    respuesta = FileResponse(almacenamiento.open(ruta, "rb"), as_attachment=True, filename=nombre)
    respuesta["X-Content-Type-Options"] = "nosniff"
    return respuesta
