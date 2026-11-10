from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404

from apps.api import serializadores as ser
from apps.api.autenticacion import api
from apps.api.respuestas import ErrorAPI, exito, fallo_formulario, leer_json, paginar
from apps.core.archivos import respuesta_descarga
from apps.core.storage import almacenamiento_privado
from apps.core.utiles import mensaje_de
from apps.cotizaciones.forms.cotizaciones import SolicitudCotizacionForm
from apps.cotizaciones.selectors import cotizaciones as selectores
from apps.cotizaciones.services import cotizaciones as servicios
from apps.encargos.models import Encargo

ACCIONES = {"aceptar": "aceptar_cotizacion", "rechazar": "rechazar_cotizacion", "cancelar": "cancelar_cotizacion"}
CAMPOS_ESPECIFICACIONES = ("material", "color", "dimensiones")


def _detalle(cliente, pk):
    cotizacion = selectores.obtener_del_cliente(cliente, pk)
    if cotizacion is None:
        raise Http404
    encargo = Encargo.objects.filter(cotizacion=cotizacion).first()
    return ser.cotizacion_detalle(cotizacion, encargo)


def _datos_json(datos):
    plano = {clave: ("" if valor is None else str(valor)) for clave, valor in datos.items() if not isinstance(valor, (dict, list))}
    especificaciones = datos.get("especificaciones")
    if isinstance(especificaciones, dict):
        for clave in CAMPOS_ESPECIFICACIONES:
            if especificaciones.get(clave) is not None:
                plano[clave] = str(especificaciones[clave])
    return plano


@api(("GET", "POST"))
def cotizaciones(request):
    if request.method == "GET":
        return exito(paginar(request, selectores.cotizaciones_del_cliente(request.cliente), ser.cotizacion_resumen))
    if (request.content_type or "").startswith("application/json"):
        formulario = SolicitudCotizacionForm(_datos_json(leer_json(request)))
    else:
        formulario = SolicitudCotizacionForm(request.POST, request.FILES)
    if not formulario.is_valid():
        return fallo_formulario(formulario)
    try:
        cotizacion = servicios.solicitar_cotizacion(
            cliente=request.cliente,
            usuario=request.usuario,
            servicio=formulario.cleaned_data["servicio"],
            cantidad=formulario.cleaned_data["cantidad"],
            descripcion=formulario.cleaned_data["descripcion"],
            solicitud=formulario.cleaned_data["solicitud"],
            especificaciones=formulario.especificaciones(),
            archivos=formulario.cleaned_data["archivos"],
        )
    except (servicios.ErrorCotizacion, ValidationError) as error:
        raise ErrorAPI(mensaje_de(error), "cotizacion_invalida", 400)
    return exito(_detalle(request.cliente, cotizacion.pk), 201)


@api(("GET",))
def cotizacion_detalle(request, pk):
    return exito(_detalle(request.cliente, pk))


@api(("POST",))
def cotizacion_accion(request, pk, accion):
    if accion not in ACCIONES:
        raise Http404
    cotizacion = selectores.obtener_del_cliente(request.cliente, pk)
    if cotizacion is None:
        raise Http404
    try:
        getattr(servicios, ACCIONES[accion])(cotizacion.pk, request.usuario)
    except servicios.CotizacionVencida:
        raise ErrorAPI("La cotización ya venció.", "cotizacion_vencida", 409)
    except servicios.ErrorCotizacion as error:
        raise ErrorAPI(str(error), "transicion_invalida", 409)
    return exito(_detalle(request.cliente, pk))


@api(("GET",))
def cotizacion_archivo(request, pk, archivo_id):
    cotizacion = selectores.obtener_del_cliente(request.cliente, pk)
    if cotizacion is None:
        raise Http404
    archivo = get_object_or_404(cotizacion.archivos.all(), pk=archivo_id)
    return respuesta_descarga(almacenamiento_privado, archivo.ruta_archivo, archivo.nombre_archivo)
