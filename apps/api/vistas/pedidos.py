from django.http import Http404

from apps.api import serializadores as ser
from apps.api.autenticacion import api
from apps.api.respuestas import ErrorAPI, exito, paginar
from apps.core.archivos import respuesta_descarga
from apps.core.storage import almacenamiento_privado
from apps.encargos.selectors import encargos as selectores
from apps.encargos.services import encargos as servicios
from apps.facturacion.selectors import facturacion as selectores_facturas


def _pedido(cliente, pk):
    encargo = selectores.obtener_del_cliente(cliente, pk)
    if encargo is None:
        raise Http404
    return encargo


@api(("GET",))
def pedidos(request):
    return exito(paginar(request, selectores.encargos_del_cliente(request.cliente), ser.encargo_resumen))


@api(("GET",))
def pedido_detalle(request, pk):
    return exito(ser.encargo_detalle(_pedido(request.cliente, pk)))


@api(("POST",))
def pedido_cancelar(request, pk):
    encargo = _pedido(request.cliente, pk)
    try:
        servicios.cancelar_por_cliente(encargo.pk, request.usuario)
    except servicios.ErrorEncargo as error:
        raise ErrorAPI(str(error), "transicion_invalida", 409)
    return exito(ser.encargo_detalle(_pedido(request.cliente, pk)))


@api(("GET",))
def pedido_archivo(request, pk, archivo_id):
    encargo = _pedido(request.cliente, pk)
    archivo = next((a for d in encargo.detalles.all() for a in d.archivos.all() if a.pk == archivo_id), None)
    if archivo is None:
        raise Http404
    return respuesta_descarga(almacenamiento_privado, archivo.ruta_archivo, archivo.nombre_archivo)


@api(("GET",))
def facturas(request):
    return exito(paginar(request, selectores_facturas.facturas_del_cliente(request.cliente), ser.factura_resumen))


@api(("GET",))
def factura_detalle(request, pk):
    factura = selectores_facturas.obtener_del_cliente(request.cliente, pk)
    if factura is None:
        raise Http404
    return exito(ser.factura_detalle(factura))
