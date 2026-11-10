import uuid
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from apps.core.archivos import validar_archivo
from apps.core.calculos import calcular_linea, totales_documento
from apps.core.storage import almacenamiento_privado
from apps.cotizaciones.models import ArchivoCotizacion, Cotizacion, CotizacionDetalle, EstadoCotizacion
from apps.crm.models import InteraccionCliente, TipoInteraccion
from apps.usuarios.constants import GRUPO_ADMINISTRADOR, GRUPO_OPERADOR

E = EstadoCotizacion

TRANSICIONES = {
    E.SOLICITADA.value: {E.BORRADOR.value, E.CANCELADA.value},
    E.BORRADOR.value: {E.ENVIADA.value, E.CANCELADA.value},
    E.ENVIADA.value: {E.ACEPTADA.value, E.RECHAZADA.value, E.VENCIDA.value, E.CANCELADA.value},
    E.ACEPTADA.value: set(),
    E.RECHAZADA.value: set(),
    E.VENCIDA.value: set(),
    E.CANCELADA.value: set(),
}
EDITABLES = (E.SOLICITADA.value, E.BORRADOR.value)


class ErrorCotizacion(Exception):
    pass


class TransicionInvalida(ErrorCotizacion):
    pass


class CotizacionVencida(ErrorCotizacion):
    pass


class CotizacionIncompleta(ErrorCotizacion):
    pass


def _es_personal(usuario):
    return usuario.tiene_algun_rol((GRUPO_OPERADOR, GRUPO_ADMINISTRADOR))


def _exigir_personal(usuario):
    if not _es_personal(usuario):
        raise PermissionDenied("Solo el personal autorizado puede realizar esta acción.")


def _exigir_propietario(cotizacion, usuario):
    if cotizacion.cliente.usuario_id != usuario.pk:
        raise PermissionDenied("Esta cotización pertenece a otro cliente.")


def _bloquear(cotizacion_id):
    return (
        Cotizacion.objects.select_for_update(of=("self",))
        .select_related("cliente")
        .get(pk=cotizacion_id)
    )


def _cambiar_estado(cotizacion, nuevo):
    nuevo = str(nuevo)
    if nuevo not in TRANSICIONES.get(cotizacion.estado, set()):
        raise TransicionInvalida(
            f"No se puede pasar de {cotizacion.get_estado_display()} a {EstadoCotizacion(nuevo).label}."
        )
    cotizacion.estado = nuevo


def _registrar(cotizacion, asunto, usuario=None):
    responsable = usuario if usuario is not None and _es_personal(usuario) else cotizacion.usuario_responsable
    if responsable is None:
        return
    InteraccionCliente.objects.create(
        cliente=cotizacion.cliente,
        usuario_responsable=responsable,
        tipo_interaccion=TipoInteraccion.SEGUIMIENTO,
        asunto=asunto[:150],
        descripcion=f"Cotización {cotizacion.codigo}",
    )


def _vigente(cotizacion):
    return not (cotizacion.fecha_vencimiento and cotizacion.fecha_vencimiento < timezone.now())


@transaction.atomic
def solicitar_cotizacion(
    cliente,
    usuario,
    servicio,
    cantidad,
    descripcion,
    solicitud,
    especificaciones=None,
    archivos=(),
    precio_unitario=None,
    verificar_servicio=True,
):
    if verificar_servicio and (not servicio.activo or not servicio.categoria.activo):
        raise ErrorCotizacion("El servicio seleccionado no está disponible.")
    maximo = getattr(settings, "COTIZACION_MAX_ARCHIVOS", 5)
    if len(archivos) > maximo:
        raise ErrorCotizacion(f"Puede adjuntar hasta {maximo} archivos.")
    validados = [(archivo, *validar_archivo(archivo)) for archivo in archivos]

    precio = servicio.precio_base if precio_unitario is None else precio_unitario
    linea = calcular_linea(cantidad, precio, Decimal("0"))
    cotizacion = Cotizacion.objects.create(
        cliente=cliente,
        codigo=f"TMP-{uuid.uuid4().hex[:12].upper()}",
        estado=E.SOLICITADA,
        solicitud=solicitud,
        **totales_documento([linea]),
    )
    cotizacion.codigo = f"COT-{timezone.now():%Y}-{cotizacion.pk:06d}"
    cotizacion.save(update_fields=["codigo", "actualizado_en"])
    CotizacionDetalle.objects.create(
        cotizacion=cotizacion,
        servicio=servicio,
        descripcion=descripcion[:250],
        cantidad=cantidad,
        precio_unitario=precio,
        descuento=linea["descuento"],
        impuesto=linea["impuesto"],
        subtotal=linea["subtotal"],
        especificaciones=especificaciones or None,
    )

    guardados = []
    try:
        for archivo, formato, nombre in validados:
            ruta = almacenamiento_privado.save(
                f"cotizaciones/{cotizacion.pk}/{uuid.uuid4().hex}.{formato.lower()}", archivo
            )
            guardados.append(ruta)
            ArchivoCotizacion.objects.create(
                cotizacion=cotizacion,
                nombre_archivo=nombre,
                ruta_archivo=ruta,
                formato=formato,
                tamano_bytes=archivo.size,
                usuario_subida=usuario,
            )
    except Exception:
        for ruta in guardados:
            almacenamiento_privado.delete(ruta)
        raise
    return cotizacion


@transaction.atomic
def revisar_cotizacion(cotizacion_id, usuario, lineas, observaciones=None, plazo_entrega_dias=None):
    _exigir_personal(usuario)
    cotizacion = _bloquear(cotizacion_id)
    if cotizacion.estado not in EDITABLES:
        raise TransicionInvalida("Solo se pueden editar cotizaciones solicitadas o en borrador.")
    detalles = {d.pk: d for d in cotizacion.detalles.select_for_update()}
    ids = [datos["id"] for datos in lineas]
    if not ids or len(ids) != len(set(ids)) or set(ids) != set(detalles):
        raise ErrorCotizacion("Debe indicar todas las líneas de la cotización, sin repetir.")

    calculadas = []
    for datos in lineas:
        detalle = detalles[datos["id"]]
        calculo = calcular_linea(datos["cantidad"], datos["precio_unitario"], datos.get("descuento") or Decimal("0"))
        detalle.cantidad = datos["cantidad"]
        detalle.precio_unitario = datos["precio_unitario"]
        detalle.descuento = calculo["descuento"]
        detalle.impuesto = calculo["impuesto"]
        detalle.subtotal = calculo["subtotal"]
        detalle.save()
        calculadas.append(calculo)

    for campo, valor in totales_documento(calculadas).items():
        setattr(cotizacion, campo, valor)
    cotizacion.observaciones = observaciones
    cotizacion.plazo_entrega_dias = plazo_entrega_dias
    cotizacion.usuario_responsable = usuario
    if cotizacion.estado == E.SOLICITADA.value:
        _cambiar_estado(cotizacion, E.BORRADOR)
    cotizacion.save()
    _registrar(cotizacion, "Cotización revisada", usuario)
    return cotizacion


@transaction.atomic
def enviar_cotizacion(cotizacion_id, usuario):
    _exigir_personal(usuario)
    cotizacion = _bloquear(cotizacion_id)
    if cotizacion.total <= 0 or not cotizacion.detalles.exists():
        raise CotizacionIncompleta("La cotización debe tener importes definidos antes de enviarse.")
    _cambiar_estado(cotizacion, E.ENVIADA)
    cotizacion.usuario_responsable = cotizacion.usuario_responsable or usuario
    vigencia = getattr(settings, "COTIZACION_VIGENCIA_DIAS", 15)
    cotizacion.fecha_vencimiento = timezone.now() + timedelta(days=vigencia)
    cotizacion.save()
    _registrar(cotizacion, "Cotización enviada al cliente", usuario)
    return cotizacion


@transaction.atomic
def _responder(cotizacion_id, usuario, nuevo, asunto):
    cotizacion = _bloquear(cotizacion_id)
    _exigir_propietario(cotizacion, usuario)
    if cotizacion.estado == E.ENVIADA.value and not _vigente(cotizacion):
        raise CotizacionVencida("La cotización ya venció.")
    _cambiar_estado(cotizacion, nuevo)
    cotizacion.save()
    _registrar(cotizacion, asunto)
    return cotizacion


def aceptar_cotizacion(cotizacion_id, usuario):
    try:
        return _responder(cotizacion_id, usuario, E.ACEPTADA, "Cotización aceptada por el cliente")
    except CotizacionVencida:
        marcar_vencida(cotizacion_id)
        raise


def rechazar_cotizacion(cotizacion_id, usuario):
    try:
        return _responder(cotizacion_id, usuario, E.RECHAZADA, "Cotización rechazada por el cliente")
    except CotizacionVencida:
        marcar_vencida(cotizacion_id)
        raise


@transaction.atomic
def cancelar_cotizacion(cotizacion_id, usuario):
    cotizacion = _bloquear(cotizacion_id)
    if not _es_personal(usuario):
        _exigir_propietario(cotizacion, usuario)
        if cotizacion.estado != E.SOLICITADA.value:
            raise TransicionInvalida("Solo puede cancelar solicitudes que aún no fueron revisadas.")
    _cambiar_estado(cotizacion, E.CANCELADA)
    cotizacion.save()
    _registrar(cotizacion, "Cotización cancelada", usuario)
    return cotizacion


@transaction.atomic
def marcar_vencida(cotizacion_id):
    cotizacion = _bloquear(cotizacion_id)
    if cotizacion.estado == E.ENVIADA.value and not _vigente(cotizacion):
        _cambiar_estado(cotizacion, E.VENCIDA)
        cotizacion.save()
        _registrar(cotizacion, "Cotización vencida")
        return True
    return False


def vencer_cotizaciones_vencidas():
    ids = list(
        Cotizacion.objects.filter(estado=E.ENVIADA, fecha_vencimiento__lt=timezone.now()).values_list("pk", flat=True)
    )
    return sum(1 for pk in ids if marcar_vencida(pk))
