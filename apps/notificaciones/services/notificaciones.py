import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.notificaciones.correo import construir_correo, sitio_url
from apps.notificaciones.models import Notificacion
from apps.notificaciones.selectors.notificaciones import destino
from apps.usuarios.constants import ESTADO_ACTIVO, GRUPO_ADMINISTRADOR, GRUPO_OPERADOR
from apps.usuarios.models import Usuario

registro = logging.getLogger(__name__)
VENTANA_DUPLICADO = 30
NOTA_CLIENTE = "Si tiene alguna duda, puede escribirnos desde la sección Soporte de su cuenta."


def personal_activo():
    return (
        Usuario.objects.filter(is_active=True, estado_id=ESTADO_ACTIVO)
        .filter(groups__name__in=[GRUPO_OPERADOR, GRUPO_ADMINISTRADOR])
        .exclude(empleado__activo=False)
        .distinct()
    )


def _resolver(valor):
    """Los parrafos y detalles pueden ser una funcion: se evalua al confirmar la transaccion, con datos ya actualizados."""
    return valor() if callable(valor) else valor


def _enviar_correo(usuario, asunto, mensaje, ruta=None, parrafos=None, detalles=None, boton=None):
    enlace = {"texto": boton or "Ver los detalles", "url": f"{sitio_url()}{ruta}"} if ruta else None
    for con_imagen in (True, False):
        try:
            correo = construir_correo(
                usuario.correo,
                asunto,
                asunto,
                nombre=usuario.nombres,
                parrafos=_resolver(parrafos) or [mensaje],
                detalles=_resolver(detalles) or (),
                boton=enlace,
                nota="" if usuario.is_staff else NOTA_CLIENTE,
                con_imagen=con_imagen,
            )
            correo.send()
            return
        except Exception:
            registro.exception(
                "No se pudo enviar el correo a %s%s", usuario.correo, " (se reintenta sin el logo)" if con_imagen else ""
            )


def notificar(usuario, titulo, mensaje, tipo, referencia_id=None, correo=False, parrafos=None, detalles=None, boton=None):
    if usuario is None or not usuario.is_active:
        return None
    titulo = titulo[:120]
    limite = timezone.now() - timedelta(seconds=VENTANA_DUPLICADO)
    existente = Notificacion.objects.filter(
        usuario=usuario, tipo=tipo, referencia_id=referencia_id, titulo=titulo, fecha_creacion__gte=limite
    ).first()
    if existente is not None:
        return existente
    notificacion = Notificacion.objects.create(
        usuario=usuario, titulo=titulo, mensaje=mensaje, tipo=tipo, referencia_id=referencia_id
    )
    if correo:
        ruta = destino(notificacion, usuario)
        transaction.on_commit(lambda: _enviar_correo(usuario, titulo, mensaje, ruta, parrafos, detalles, boton))
    return notificacion


def notificar_personal(titulo, mensaje, tipo, referencia_id=None):
    return [notificar(usuario, titulo, mensaje, tipo, referencia_id) for usuario in personal_activo()]


def marcar_leida(usuario, notificacion_id):
    if not str(notificacion_id).isdigit():
        return 0
    return Notificacion.objects.filter(usuario=usuario, pk=int(notificacion_id), leida=False).update(leida=True)


def marcar_todas(usuario):
    return Notificacion.objects.filter(usuario=usuario, leida=False).update(leida=True)
