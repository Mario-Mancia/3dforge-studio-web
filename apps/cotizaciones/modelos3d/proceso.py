"""Analiza una malla 3D con trimesh.

Este modulo NO usa Django: se ejecuta en un proceso aparte (python -m ...) con tiempo limite,
de modo que un archivo corrupto o enorme no pueda colgar ni tumbar el servidor web.
"""
import json
import math
import sys

EXTENSIONES = ("stl", "obj", "3mf")


def _proporcion_voladizo(malla, area):
    """Fraccion del area con normales hacia abajo (>45 grados), sin contar la cara apoyada en la cama."""
    if area <= 0:
        return 0.0
    normales = malla.face_normals
    areas = malla.area_faces
    z_minimo = float(malla.bounds[0][2])
    apoyada = malla.triangles[:, :, 2].max(axis=1) <= z_minimo + 0.05
    voladizo = (normales[:, 2] < -0.7071) & ~apoyada
    return float(areas[voladizo].sum() / area)


def analizar(ruta, extension, limite_triangulos):
    extension = str(extension).lower().lstrip(".")
    if extension not in EXTENSIONES:
        raise ValueError("Formato no compatible. Use STL, OBJ o 3MF.")
    try:
        import trimesh
    except ImportError:
        raise ValueError("El cotizador 3D no está disponible: falta instalar la librería trimesh.")

    malla = trimesh.load(ruta, file_type=extension, force="mesh")
    if not hasattr(malla, "faces") or len(malla.faces) == 0:
        raise ValueError("El archivo no contiene geometría 3D.")
    caras = int(len(malla.faces))
    if caras > limite_triangulos:
        raise ValueError(
            f"El modelo tiene {caras:,} triángulos y el máximo permitido es {limite_triangulos:,}. "
            "Simplifique la malla o solicite una cotización manual."
        )

    hermetica = bool(malla.is_watertight)
    reparada = False
    if not hermetica:
        try:
            malla.fill_holes()
            hermetica = bool(malla.is_watertight)
            reparada = hermetica
        except Exception:
            pass

    volumen = abs(float(malla.volume)) if hermetica else 0.0
    area = float(malla.area)
    extents = [float(valor) for valor in malla.extents]
    resultado = {
        "volumen_mm3": volumen,
        "area_mm2": area,
        "extents_mm": extents,
        "triangulos": caras,
        "hermetica": hermetica,
        "reparada": reparada,
        "voladizo_ratio": _proporcion_voladizo(malla, area),
    }
    numeros = [volumen, area, resultado["voladizo_ratio"], *extents]
    if not all(math.isfinite(numero) for numero in numeros) or min(extents) < 0 or max(extents) <= 0:
        raise ValueError("La geometría del archivo no es válida.")
    return resultado


def analizar_seguro(ruta, extension, limite_triangulos):
    try:
        return analizar(ruta, extension, int(limite_triangulos))
    except ValueError as error:
        return {"error": str(error)}
    except MemoryError:
        return {"error": "El modelo es demasiado grande para analizarlo."}
    except Exception:
        return {"error": "No se pudo leer el modelo. Verifique que el archivo no esté dañado (para 3MF se requiere lxml)."}


def main(argumentos):
    if len(argumentos) != 4:
        print(json.dumps({"error": "Uso: proceso.py <archivo> <extension> <limite>"}))
        return 2
    print(json.dumps(analizar_seguro(argumentos[1], argumentos[2], argumentos[3]), ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
