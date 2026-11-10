from django.shortcuts import get_object_or_404

from apps.api import serializadores as ser
from apps.api.autenticacion import api
from apps.api.respuestas import ErrorAPI, exito, paginar
from apps.catalogo.selectors import catalogo as selectores


@api(("GET",), requiere_sesion=False)
def categorias(request):
    return exito({"resultados": [ser.categoria(c) for c in selectores.categorias_publicas()]})


@api(("GET",), requiere_sesion=False)
def productos(request):
    consulta = selectores.productos_publicos(request.GET.get("q", "").strip()[:100])
    return exito(paginar(request, consulta, lambda p: ser.producto(p, request)))


@api(("GET",), requiere_sesion=False)
def producto_detalle(request, pk):
    return exito(ser.producto(get_object_or_404(selectores.productos_publicos(), pk=pk), request))


@api(("GET",), requiere_sesion=False)
def servicios(request):
    categoria = request.GET.get("categoria", "")
    if categoria and not categoria.isdigit():
        raise ErrorAPI("La categoría indicada no es válida.", "datos_invalidos", 400)
    consulta = selectores.servicios_publicos(int(categoria) if categoria else None)
    return exito({"resultados": [ser.servicio(s) for s in consulta]})


@api(("GET",), requiere_sesion=False)
def servicio_detalle(request, pk):
    return exito(ser.servicio(get_object_or_404(selectores.servicios_publicos(), pk=pk)))
