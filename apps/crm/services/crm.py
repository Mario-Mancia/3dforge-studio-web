from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from apps.clientes.models import Cliente
from apps.crm.models import EstadoSoporte, InteraccionCliente, NotaCliente, SolicitudSoporte, TipoInteraccion
from apps.usuarios.constants import GRUPO_ADMINISTRADOR, GRUPO_OPERADOR

VENTANA_DUPLICADO = 30
TRANSICIONES_SOPORTE = {
    "ABIERTA": {"EN_PROCESO", "RESUELTA", "CERRADA"},
    "EN_PROCESO": {"ABIERTA", "RESUELTA", "CERRADA"},
    "RESUELTA": {"EN_PROCESO", "CERRADA"},
    "CERRADA": set(),
}


class ErrorCRM(Exception):
    pass


def _exigir_personal(usuario):
    if not usuario.tiene_algun_rol((GRUPO_OPERADOR, GRUPO_ADMINISTRADOR)):
        raise PermissionDenied("Solo el personal autorizado puede realizar esta acción.")


def registrar_evento(cliente, usuario_responsable, asunto, descripcion=None):
    if usuario_responsable is None:
        return None
    asunto = asunto[:150]
    limite = timezone.now() - timedelta(seconds=VENTANA_DUPLICADO)
    if InteraccionCliente.objects.filter(cliente=cliente, asunto=asunto, fecha_interaccion__gte=limite).exists():
        return None
    return InteraccionCliente.objects.create(
        cliente=cliente,
        usuario_responsable=usuario_responsable,
        tipo_interaccion=TipoInteraccion.SEGUIMIENTO,
        asunto=asunto,
        descripcion=descripcion,
    )


@transaction.atomic
def agregar_nota(cliente_id, usuario, contenido):
    _exigir_personal(usuario)
    cliente = Cliente.objects.get(pk=cliente_id)
    return NotaCliente.objects.create(cliente=cliente, usuario=usuario, contenido=contenido)


@transaction.atomic
def registrar_interaccion(cliente_id, usuario, tipo, asunto, descripcion=None):
    _exigir_personal(usuario)
    cliente = Cliente.objects.get(pk=cliente_id)
    return InteraccionCliente.objects.create(
        cliente=cliente, usuario_responsable=usuario, tipo_interaccion=tipo, asunto=asunto[:150], descripcion=descripcion or None
    )


@transaction.atomic
def crear_solicitud(cliente, asunto, descripcion, prioridad="MEDIA"):
    if prioridad not in ("BAJA", "MEDIA", "ALTA"):
        raise ErrorCRM("La prioridad indicada no es válida.")
    return SolicitudSoporte.objects.create(cliente=cliente, asunto=asunto, descripcion=descripcion, prioridad=prioridad)


def _bloquear(solicitud_id):
    return SolicitudSoporte.objects.select_for_update(of=("self",)).select_related("cliente").get(pk=solicitud_id)


@transaction.atomic
def tomar_solicitud(solicitud_id, usuario):
    _exigir_personal(usuario)
    solicitud = _bloquear(solicitud_id)
    if solicitud.estado == EstadoSoporte.CERRADA:
        raise ErrorCRM("La solicitud está cerrada.")
    solicitud.usuario_responsable = usuario
    if solicitud.estado == EstadoSoporte.ABIERTA:
        solicitud.estado = EstadoSoporte.EN_PROCESO
    solicitud.save()
    return solicitud


@transaction.atomic
def cambiar_estado_solicitud(solicitud_id, usuario, nuevo):
    _exigir_personal(usuario)
    solicitud = _bloquear(solicitud_id)
    nuevo = str(nuevo)
    if nuevo not in TRANSICIONES_SOPORTE.get(solicitud.estado, set()):
        raise ErrorCRM(f"No se puede pasar de {solicitud.get_estado_display()} a {EstadoSoporte(nuevo).label}.")
    if solicitud.usuario_responsable_id is None:
        solicitud.usuario_responsable = usuario
    solicitud.estado = nuevo
    solicitud.save()
    return solicitud


@transaction.atomic
def cerrar_por_cliente(solicitud_id, usuario):
    solicitud = _bloquear(solicitud_id)
    if solicitud.cliente.usuario_id != usuario.pk:
        raise PermissionDenied("Esta solicitud pertenece a otro cliente.")
    if solicitud.estado == EstadoSoporte.CERRADA:
        raise ErrorCRM("La solicitud ya está cerrada.")
    solicitud.estado = EstadoSoporte.CERRADA
    solicitud.save()
    return solicitud
