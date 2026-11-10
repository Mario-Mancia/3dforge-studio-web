from django.core.exceptions import ValidationError
from django.http import Http404

from apps.api import serializadores as ser
from apps.api.autenticacion import api
from apps.api.respuestas import ErrorAPI, exito, fallo_formulario, leer_json, paginar
from apps.core.utiles import mensaje_de
from apps.crm.forms.crm import SolicitudSoporteForm
from apps.crm.selectors import crm as selectores_soporte
from apps.crm.services import crm as servicios_soporte
from apps.notificaciones.models import Notificacion
from apps.notificaciones.selectors import notificaciones as selectores_notificaciones
from apps.notificaciones.services import notificaciones as servicios_notificaciones


@api(("GET",))
def notificaciones(request):
    solo_no_leidas = request.GET.get("no_leidas") in ("1", "true", "True")
    consulta = selectores_notificaciones.de_usuario(request.usuario, solo_no_leidas=solo_no_leidas)
    return exito(paginar(request, consulta, ser.notificacion))


@api(("GET",))
def notificaciones_contador(request):
    return exito({"no_leidas": selectores_notificaciones.contar_no_leidas(request.usuario)})


@api(("POST",))
def notificacion_leer(request, pk):
    if not Notificacion.objects.filter(pk=pk, usuario=request.usuario).exists():
        raise Http404
    servicios_notificaciones.marcar_leida(request.usuario, pk)
    return exito({"no_leidas": selectores_notificaciones.contar_no_leidas(request.usuario)})


@api(("POST",))
def notificaciones_leer_todas(request):
    servicios_notificaciones.marcar_todas(request.usuario)
    return exito({"no_leidas": 0})


@api(("GET", "POST"))
def soporte(request):
    if request.method == "GET":
        return exito(paginar(request, selectores_soporte.solicitudes_del_cliente(request.cliente), ser.soporte))
    formulario = SolicitudSoporteForm(
        {clave: ("" if valor is None else str(valor)) for clave, valor in leer_json(request).items()}
    )
    if not formulario.is_valid():
        return fallo_formulario(formulario)
    try:
        solicitud = servicios_soporte.crear_solicitud(request.cliente, **formulario.cleaned_data)
    except (servicios_soporte.ErrorCRM, ValidationError) as error:
        raise ErrorAPI(mensaje_de(error), "solicitud_invalida", 400)
    return exito(ser.soporte(solicitud), 201)


def _solicitud(cliente, pk):
    solicitud = selectores_soporte.obtener_solicitud_del_cliente(cliente, pk)
    if solicitud is None:
        raise Http404
    return solicitud


@api(("GET",))
def soporte_detalle(request, pk):
    return exito(ser.soporte(_solicitud(request.cliente, pk)))


@api(("POST",))
def soporte_cerrar(request, pk):
    solicitud = _solicitud(request.cliente, pk)
    try:
        servicios_soporte.cerrar_por_cliente(solicitud.pk, request.usuario)
    except servicios_soporte.ErrorCRM as error:
        raise ErrorAPI(str(error), "transicion_invalida", 409)
    return exito(ser.soporte(_solicitud(request.cliente, pk)))
