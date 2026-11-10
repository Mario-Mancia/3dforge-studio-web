import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from django.conf import settings

from apps.cotizaciones.modelos3d.errores import ErrorAnalisis

EXTENSIONES_3D = ("stl", "obj", "3mf")


def _ejecutar_aislado(ruta, extension, limite):
    entorno = {**os.environ, "PYTHONPATH": str(settings.BASE_DIR), "PYTHONIOENCODING": "utf-8"}
    comando = [sys.executable, "-m", "apps.cotizaciones.modelos3d.proceso", ruta, extension, str(limite)]
    try:
        proceso = subprocess.run(
            comando,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=getattr(settings, "COTIZADOR_TIMEOUT_SEGUNDOS", 30),
            cwd=str(settings.BASE_DIR),
            env=entorno,
        )
    except subprocess.TimeoutExpired:
        raise ErrorAnalisis("El análisis del modelo tardó demasiado. Pruebe con un archivo más liviano.")
    except OSError:
        raise ErrorAnalisis("No se pudo iniciar el análisis del modelo.")
    lineas = [linea for linea in proceso.stdout.strip().splitlines() if linea.strip().startswith("{")]
    if not lineas:
        raise ErrorAnalisis("No se pudo analizar el modelo. Intente con otro archivo.")
    try:
        return json.loads(lineas[-1])
    except ValueError:
        raise ErrorAnalisis("No se pudo analizar el modelo. Intente con otro archivo.")


def _ejecutar_directo(ruta, extension, limite):
    from apps.cotizaciones.modelos3d import proceso

    return proceso.analizar_seguro(ruta, extension, limite)


def analizar_archivo(archivo, limite_triangulos, aislado=None):
    """Analiza un archivo subido (STL, OBJ o 3MF) y devuelve volumen, area, dimensiones y calidad de la malla."""
    extension = Path(archivo.name or "").suffix.lower().lstrip(".")
    if extension not in EXTENSIONES_3D:
        raise ErrorAnalisis("Formato no compatible con la cotización automática. Use STL, OBJ o 3MF.")
    if aislado is None:
        aislado = getattr(settings, "COTIZADOR_AISLADO", True)
    with tempfile.TemporaryDirectory(prefix="modelo3d_") as carpeta:
        ruta = os.path.join(carpeta, f"modelo.{extension}")
        archivo.seek(0)
        with open(ruta, "wb") as destino:
            for bloque in archivo.chunks():
                destino.write(bloque)
        archivo.seek(0)
        ejecutar = _ejecutar_aislado if aislado else _ejecutar_directo
        resultado = ejecutar(ruta, extension, int(limite_triangulos))
    if "error" in resultado:
        raise ErrorAnalisis(resultado["error"])
    return resultado


def _numero(valor, minimo, maximo):
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        raise ErrorAnalisis("El análisis enviado no es válido.")
    if not math.isfinite(numero) or not minimo <= numero <= maximo:
        raise ErrorAnalisis("El análisis enviado no es válido.")
    return numero


def analisis_desde_json(texto):
    """Reconstruye (y valida) un analisis previo que el navegador reenvia para recalcular opciones sin subir el archivo."""
    try:
        datos = json.loads(texto or "")
    except (TypeError, ValueError):
        raise ErrorAnalisis("El análisis enviado no es válido.")
    if not isinstance(datos, dict):
        raise ErrorAnalisis("El análisis enviado no es válido.")
    extents = datos.get("extents_mm")
    if not isinstance(extents, list) or len(extents) != 3:
        raise ErrorAnalisis("El análisis enviado no es válido.")
    return {
        "volumen_mm3": _numero(datos.get("volumen_mm3"), 0, 1e12),
        "area_mm2": _numero(datos.get("area_mm2"), 0, 1e11),
        "extents_mm": [_numero(valor, 0, 1e5) for valor in extents],
        "triangulos": int(_numero(datos.get("triangulos"), 0, 1e8)),
        "hermetica": bool(datos.get("hermetica")),
        "reparada": bool(datos.get("reparada")),
        "voladizo_ratio": _numero(datos.get("voladizo_ratio"), 0, 1),
    }
