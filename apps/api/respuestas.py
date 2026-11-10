import json

from django.conf import settings
from django.core.paginator import EmptyPage, Paginator
from django.http import JsonResponse


class ErrorAPI(Exception):
    def __init__(self, mensaje, codigo="error", estado=400, campos=None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo = codigo
        self.estado = estado
        self.campos = campos or {}


def exito(datos=None, estado=200):
    return JsonResponse(
        {"ok": True} if datos is None else datos, status=estado, safe=False, json_dumps_params={"ensure_ascii": False}
    )


def fallo(mensaje, codigo="error", estado=400, campos=None):
    cuerpo = {"error": {"codigo": codigo, "mensaje": mensaje, "campos": campos or {}}}
    return JsonResponse(cuerpo, status=estado, json_dumps_params={"ensure_ascii": False})


def fallo_formulario(formulario):
    campos = {
        ("general" if campo == "__all__" else campo): [str(error) for error in errores]
        for campo, errores in formulario.errors.items()
    }
    primero = next(iter(campos.values()))[0] if campos else "Datos no válidos."
    return fallo(primero, "datos_invalidos", 400, campos)


def leer_json(request):
    if not (request.content_type or "").startswith("application/json"):
        raise ErrorAPI("Se esperaba el tipo application/json.", "tipo_no_soportado", 415)
    if len(request.body) > settings.API_MAX_JSON_BYTES:
        raise ErrorAPI("La petición es demasiado grande.", "demasiado_grande", 413)
    try:
        datos = json.loads(request.body or b"{}")
    except ValueError:
        raise ErrorAPI("El cuerpo no es un JSON válido.", "json_invalido", 400)
    if not isinstance(datos, dict):
        raise ErrorAPI("El cuerpo debe ser un objeto JSON.", "json_invalido", 400)
    return datos


def cadena(datos, clave):
    valor = datos.get(clave)
    return valor.strip() if isinstance(valor, str) else ""


def paginar(request, consulta, serializar, por_pagina=20):
    try:
        numero = max(int(request.GET.get("pagina", 1)), 1)
        tamano = min(max(int(request.GET.get("por_pagina", por_pagina)), 1), 100)
    except (TypeError, ValueError):
        raise ErrorAPI("Los parámetros de paginación no son válidos.", "paginacion_invalida", 400)
    paginador = Paginator(consulta, tamano)
    try:
        pagina = paginador.page(numero)
    except EmptyPage:
        return {"resultados": [], "total": paginador.count, "pagina": numero, "paginas": paginador.num_pages, "hay_mas": False}
    return {
        "resultados": [serializar(objeto) for objeto in pagina.object_list],
        "total": paginador.count,
        "pagina": pagina.number,
        "paginas": paginador.num_pages,
        "hay_mas": pagina.has_next(),
    }
