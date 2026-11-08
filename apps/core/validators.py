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

# >>> fase-0-sku
validar_sku = RegexValidator(
    regex=r"^[A-Za-z0-9][A-Za-z0-9\-_.]{1,49}$",
    message="El SKU solo admite letras, numeros, guion, guion bajo y punto (2 a 50 caracteres).",
    code="sku_invalido",
)
# <<< fase-0-sku
