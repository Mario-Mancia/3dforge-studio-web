import uuid
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from apps.encargos.models import Encargo, EstadoEncargo
from apps.facturacion.models import EstadoFactura, Factura, FacturaDetalle
from apps.pagos.models import EstadoPago
from apps.usuarios.constants import GRUPO_ADMINISTRADOR, GRUPO_OPERADOR

E = EstadoFactura
ESTADOS_FACTURABLES = (
    EstadoEncargo.APROBADO.value,
    EstadoEncargo.EN_PRODUCCION.value,
    EstadoEncargo.EN_ESPERA.value,
    EstadoEncargo.FINALIZADO.value,
    EstadoEncargo.ENTREGADO.value,
)
ESTADOS_COBRABLES = (E.PENDIENTE.value, E.PARCIALMENTE_PAGADA.value, E.VENCIDA.value)


class ErrorFacturacion(Exception):
    pass


def exigir_personal(usuario):
    if not usuario.tiene_algun_rol((GRUPO_OPERADOR, GRUPO_ADMINISTRADOR)):
        raise PermissionDenied("Solo el personal autorizado puede realizar esta acción.")


def bloquear_factura(factura_id):
    return Factura.objects.select_for_update(of=("self",)).get(pk=factura_id)


def estado_segun_saldo(factura, ahora=None):
    if factura.saldo_pendiente <= 0:
        return E.PAGADA.value
    vencida = factura.fecha_vencimiento and factura.fecha_vencimiento < (ahora or timezone.now())
    if vencida:
        return E.VENCIDA.value
    if factura.saldo_pendiente < factura.total:
        return E.PARCIALMENTE_PAGADA.value
    return E.PENDIENTE.value


@transaction.atomic
def crear_desde_encargo(encargo_id, usuario):
    exigir_personal(usuario)
    encargo = Encargo.objects.select_for_update(of=("self",)).select_related("cliente").get(pk=encargo_id)
    existente = Factura.objects.filter(encargo=encargo).first()
    if existente is not None:
        return existente
    if encargo.estado not in ESTADOS_FACTURABLES:
        raise ErrorFacturacion("Solo se factura un encargo aprobado o en curso.")
    if encargo.total <= 0:
        raise ErrorFacturacion("No se puede facturar un encargo con total cero.")
    detalles = list(encargo.detalles.all())
    if not detalles:
        raise ErrorFacturacion("El encargo no tiene líneas.")

    cliente = encargo.cliente
    ahora = timezone.now()
    vigencia = getattr(settings, "FACTURA_VENCIMIENTO_DIAS", 30)
    factura = Factura.objects.create(
        cliente=cliente,
        encargo=encargo,
        numero_factura=f"TMP-{uuid.uuid4().hex[:12].upper()}",
        fecha_emision=ahora,
        fecha_vencimiento=ahora + timedelta(days=vigencia),
        nombre_facturacion=cliente.nombre_visible[:150],
        identificacion_fiscal=cliente.identificacion_fiscal,
        direccion_facturacion=cliente.direccion,
        subtotal=encargo.subtotal,
        descuento=encargo.descuento,
        impuesto=encargo.impuesto,
        total=encargo.total,
        saldo_pendiente=encargo.total,
        estado=E.PENDIENTE,
    )
    factura.numero_factura = f"FAC-{ahora:%Y}-{factura.pk:06d}"
    factura.save(update_fields=["numero_factura"])
    for d in detalles:
        FacturaDetalle.objects.create(
            factura=factura,
            servicio_id=d.servicio_id,
            producto_id=d.producto_id,
            descripcion=d.descripcion[:250],
            cantidad=d.cantidad,
            precio_unitario=d.precio_unitario,
            descuento=d.descuento,
            impuesto=d.impuesto,
            subtotal=d.subtotal,
        )
    return factura


@transaction.atomic
def anular_factura(factura_id, usuario, motivo):
    exigir_personal(usuario)
    factura = bloquear_factura(factura_id)
    if factura.estado == E.ANULADA.value:
        raise ErrorFacturacion("La factura ya está anulada.")
    if factura.pagos.filter(estado=EstadoPago.CONFIRMADO).exists():
        raise ErrorFacturacion("Cancele primero los pagos confirmados de la factura.")
    nota = f"Anulada: {motivo}"
    if factura.encargo_id:
        nota += f" (encargo {factura.encargo.codigo})"
    factura.observaciones = f"{factura.observaciones}\n{nota}" if factura.observaciones else nota
    factura.encargo = None
    factura.saldo_pendiente = Decimal("0.00")
    factura.estado = E.ANULADA
    factura.save()
    return factura


def marcar_vencidas():
    ahora = timezone.now()
    ids = list(
        Factura.objects.filter(
            estado__in=[E.PENDIENTE, E.PARCIALMENTE_PAGADA], saldo_pendiente__gt=0, fecha_vencimiento__lt=ahora
        ).values_list("pk", flat=True)
    )
    total = 0
    for pk in ids:
        with transaction.atomic():
            factura = bloquear_factura(pk)
            if factura.estado in (E.PENDIENTE.value, E.PARCIALMENTE_PAGADA.value) and estado_segun_saldo(factura, ahora) == E.VENCIDA.value:
                factura.estado = E.VENCIDA
                factura.save()
                total += 1
    return total
