import uuid
from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.core.files import File
from django.db import transaction
from django.utils import timezone

from apps.catalogo.services.catalogo import reponer_stock
from apps.core.archivos import validar_archivo
from apps.core.storage import almacenamiento_privado
from apps.cotizaciones.models import Cotizacion, EstadoCotizacion
from apps.encargos.models import ArchivoEncargo, Encargo, EncargoDetalle, EstadoEncargo, HistorialEncargo
from apps.usuarios.constants import GRUPO_ADMINISTRADOR, GRUPO_OPERADOR
from apps.usuarios.models import Empleado

E = EstadoEncargo

TRANSICIONES = {
    E.PENDIENTE.value: {E.EN_REVISION.value, E.APROBADO.value, E.CANCELADO.value},
    E.EN_REVISION.value: {E.APROBADO.value, E.EN_ESPERA.value, E.CANCELADO.value},
    E.APROBADO.value: {E.EN_PRODUCCION.value, E.EN_ESPERA.value, E.CANCELADO.value},
    E.EN_PRODUCCION.value: {E.FINALIZADO.value, E.EN_ESPERA.value, E.CANCELADO.value},
    E.EN_ESPERA.value: {E.EN_REVISION.value, E.APROBADO.value, E.EN_PRODUCCION.value, E.CANCELADO.value},
    E.FINALIZADO.value: {E.ENTREGADO.value, E.EN_PRODUCCION.value},
    E.ENTREGADO.value: set(),
    E.CANCELADO.value: set(),
}
TERMINALES = (E.ENTREGADO.value, E.CANCELADO.value)


class ErrorEncargo(Exception):
    pass


class TransicionInvalida(ErrorEncargo):
    pass


def _es_personal(usuario):
    return usuario.tiene_algun_rol((GRUPO_OPERADOR, GRUPO_ADMINISTRADOR))


def _exigir_personal(usuario):
    if not _es_personal(usuario):
        raise PermissionDenied("Solo el personal autorizado puede realizar esta acción.")


def _bloquear(encargo_id):
    return Encargo.objects.select_for_update(of=("self",)).select_related("cliente").get(pk=encargo_id)


def _registrar(encargo, usuario, anterior, nuevo, comentario=None):
    HistorialEncargo.objects.create(
        encargo=encargo,
        usuario=usuario,
        estado_anterior=anterior,
        estado_nuevo=nuevo,
        comentario=comentario,
    )


def _reponer_stock(encargo):
    if encargo.cotizacion_id is not None:
        return
    items = {}
    for detalle in encargo.detalles.filter(producto__isnull=False):
        items[detalle.producto_id] = items.get(detalle.producto_id, 0) + int(detalle.cantidad)
    if items:
        reponer_stock(items)


def _transicionar(encargo, usuario, nuevo, comentario=None):
    nuevo = str(nuevo)
    anterior = encargo.estado
    if nuevo not in TRANSICIONES.get(anterior, set()):
        raise TransicionInvalida(
            f"No se puede pasar de {encargo.get_estado_display()} a {EstadoEncargo(nuevo).label}."
        )
    if nuevo == E.ENTREGADO.value:
        encargo.fecha_entrega_real = timezone.now()
    if nuevo == E.CANCELADO.value:
        _reponer_stock(encargo)
    encargo.estado = nuevo
    encargo.save()
    _registrar(encargo, usuario, anterior, nuevo, comentario)
    return encargo


@transaction.atomic
def crear_desde_cotizacion(cotizacion_id, usuario):
    _exigir_personal(usuario)
    cotizacion = Cotizacion.objects.select_for_update(of=("self",)).select_related("cliente").get(pk=cotizacion_id)
    if cotizacion.estado != EstadoCotizacion.ACEPTADA.value:
        raise ErrorEncargo("Solo se puede crear un encargo desde una cotización aceptada.")
    existente = Encargo.objects.filter(cotizacion=cotizacion).first()
    if existente is not None:
        return existente
    detalles = list(cotizacion.detalles.all())
    if not detalles:
        raise ErrorEncargo("La cotización no tiene líneas.")

    ahora = timezone.now()
    estimada = ahora + timedelta(days=cotizacion.plazo_entrega_dias) if cotizacion.plazo_entrega_dias else None
    encargo = Encargo.objects.create(
        cliente=cotizacion.cliente,
        cotizacion=cotizacion,
        codigo=f"TMP-{uuid.uuid4().hex[:12].upper()}",
        descripcion=cotizacion.solicitud or detalles[0].descripcion,
        subtotal=cotizacion.subtotal,
        descuento=cotizacion.descuento,
        impuesto=cotizacion.impuesto,
        total=cotizacion.total,
        fecha_solicitud=ahora,
        fecha_entrega_estimada=estimada,
        estado=E.PENDIENTE,
    )
    encargo.codigo = f"ENC-{ahora:%Y}-{encargo.pk:06d}"
    encargo.save(update_fields=["codigo"])

    nuevos = [
        EncargoDetalle.objects.create(
            encargo=encargo,
            servicio=d.servicio,
            descripcion=d.descripcion,
            cantidad=d.cantidad,
            precio_unitario=d.precio_unitario,
            descuento=d.descuento,
            impuesto=d.impuesto,
            subtotal=d.subtotal,
            especificaciones=d.especificaciones,
        )
        for d in detalles
    ]

    copiados = []
    try:
        for origen in cotizacion.archivos.all():
            with almacenamiento_privado.open(origen.ruta_archivo, "rb") as contenido:
                ruta = almacenamiento_privado.save(
                    f"encargos/{encargo.pk}/{uuid.uuid4().hex}.{origen.formato.lower()}", File(contenido)
                )
            copiados.append(ruta)
            ArchivoEncargo.objects.create(
                encargo_detalle=nuevos[0],
                nombre_archivo=origen.nombre_archivo,
                ruta_archivo=ruta,
                formato=origen.formato,
                tamano_bytes=origen.tamano_bytes,
                usuario_subida=origen.usuario_subida,
            )
    except Exception:
        for ruta in copiados:
            almacenamiento_privado.delete(ruta)
        raise

    _registrar(encargo, usuario, None, E.PENDIENTE.value, f"Encargo creado desde la cotización {cotizacion.codigo}.")
    return encargo


@transaction.atomic
def cambiar_estado(encargo_id, usuario, nuevo, comentario=None):
    _exigir_personal(usuario)
    return _transicionar(_bloquear(encargo_id), usuario, nuevo, comentario or None)


@transaction.atomic
def cancelar_por_cliente(encargo_id, usuario):
    encargo = _bloquear(encargo_id)
    if encargo.cliente.usuario_id != usuario.pk:
        raise PermissionDenied("Este pedido pertenece a otro cliente.")
    if encargo.estado != E.PENDIENTE.value:
        raise TransicionInvalida("Solo puede cancelar pedidos pendientes. Contacte al equipo para otros casos.")
    return _transicionar(encargo, usuario, E.CANCELADO, "Cancelado por el cliente.")


@transaction.atomic
def asignar_responsable(encargo_id, usuario, empleado_id):
    _exigir_personal(usuario)
    encargo = _bloquear(encargo_id)
    if encargo.estado in TERMINALES:
        raise ErrorEncargo("No se puede asignar responsable a un encargo cerrado.")
    empleado = Empleado.objects.filter(pk=empleado_id, activo=True).first()
    if empleado is None:
        raise ErrorEncargo("El empleado no existe o está inactivo.")
    encargo.empleado_responsable = empleado
    encargo.save()
    return encargo


@transaction.atomic
def subir_archivo(encargo_id, detalle_id, usuario, archivo):
    _exigir_personal(usuario)
    encargo = _bloquear(encargo_id)
    detalle = encargo.detalles.filter(pk=detalle_id).first()
    if detalle is None:
        raise ErrorEncargo("La línea indicada no pertenece al encargo.")
    formato, nombre = validar_archivo(archivo)
    ruta = almacenamiento_privado.save(f"encargos/{encargo.pk}/{uuid.uuid4().hex}.{formato.lower()}", archivo)
    try:
        return ArchivoEncargo.objects.create(
            encargo_detalle=detalle,
            nombre_archivo=nombre,
            ruta_archivo=ruta,
            formato=formato,
            tamano_bytes=archivo.size,
            usuario_subida=usuario,
        )
    except Exception:
        almacenamiento_privado.delete(ruta)
        raise
