import logging
from datetime import timedelta

from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from apps.notificaciones.models import Notificacion
from apps.usuarios.constants import ESTADO_ACTIVO, GRUPO_ADMINISTRADOR, GRUPO_OPERADOR
from apps.usuarios.models import Usuario

registro = logging.getLogger(__name__)
VENTANA_DUPLICADO = 30


def personal_activo():
    return (
        Usuario.objects.filter(is_active=True, estado_id=ESTADO_ACTIVO)
        .filter(groups__name__in=[GRUPO_OPERADOR, GRUPO_ADMINISTRADOR])
        .exclude(empleado__activo=False)
        .distinct()
    )


def _enviar_correo(usuario, asunto, mensaje):
    try:
        contexto = {"usuario": usuario, "asunto": asunto, "mensaje": mensaje}
        mensaje_correo = EmailMultiAlternatives(
            asunto, render_to_string("correo/notificacion.txt", contexto), to=[usuario.correo]
        )
        mensaje_correo.attach_alternative(render_to_string("correo/notificacion.html", contexto), "text/html")
        mensaje_correo.send()
    except Exception:
        registro.exception("No se pudo enviar el correo a %s", usuario.correo)


def notificar(usuario, titulo, mensaje, tipo, referencia_id=None, correo=False):
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
        transaction.on_commit(lambda: _enviar_correo(usuario, titulo, mensaje))
    return notificacion


def notificar_personal(titulo, mensaje, tipo, referencia_id=None):
    return [notificar(usuario, titulo, mensaje, tipo, referencia_id) for usuario in personal_activo()]


def marcar_leida(usuario, notificacion_id):
    if not str(notificacion_id).isdigit():
        return 0
    return Notificacion.objects.filter(usuario=usuario, pk=int(notificacion_id), leida=False).update(leida=True)


def marcar_todas(usuario):
    return Notificacion.objects.filter(usuario=usuario, leida=False).update(leida=True)
