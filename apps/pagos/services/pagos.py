from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from apps.core.calculos import redondear
from apps.facturacion.models import EstadoFactura, Factura
from apps.facturacion.services.facturacion import (
    ESTADOS_COBRABLES,
    ErrorFacturacion,
    bloquear_factura,
    estado_segun_saldo,
    exigir_personal,
)
from apps.pagos.models import EstadoPago, Pago
from apps.pagos.selectors.pagos import metodos_activos

VENTANA_DUPLICADO = 15


class ErrorPago(ErrorFacturacion):
    pass


@transaction.atomic
def registrar_pago(factura_id, usuario, metodo_id, monto, referencia=None, observaciones=None):
    exigir_personal(usuario)
    factura = bloquear_factura(factura_id)
    if factura.estado not in ESTADOS_COBRABLES:
        raise ErrorPago("La factura no admite pagos en su estado actual.")
    try:
        monto = redondear(Decimal(str(monto)))
    except (InvalidOperation, ValueError):
        raise ErrorPago("El monto indicado no es válido.")
    if monto <= 0:
        raise ErrorPago("El monto debe ser mayor que cero.")
    if monto > factura.saldo_pendiente:
        raise ErrorPago(f"El monto supera el saldo pendiente (${factura.saldo_pendiente}).")
    metodo = metodos_activos().filter(pk=metodo_id).first()
    if metodo is None:
        raise ErrorPago("El método de pago no está disponible.")
    limite = timezone.now() - timedelta(seconds=VENTANA_DUPLICADO)
    if Pago.objects.filter(
        factura=factura, metodo_pago=metodo, monto=monto, registrado_por=usuario,
        estado=EstadoPago.CONFIRMADO, fecha_pago__gte=limite,
    ).exists():
        raise ErrorPago("Se registró un pago idéntico hace unos segundos. Verifique que no esté duplicado.")

    pago = Pago.objects.create(
        factura=factura,
        metodo_pago=metodo,
        referencia=referencia or None,
        monto=monto,
        estado=EstadoPago.CONFIRMADO,
        registrado_por=usuario,
        observaciones=observaciones or None,
    )
    factura.saldo_pendiente = redondear(factura.saldo_pendiente - monto)
    factura.estado = estado_segun_saldo(factura)
    factura.save()
    return pago


@transaction.atomic
def anular_pago(pago_id, usuario, motivo):
    exigir_personal(usuario)
    factura_id = Pago.objects.values_list("factura_id", flat=True).get(pk=pago_id)
    factura = bloquear_factura(factura_id)
    pago = Pago.objects.select_for_update().get(pk=pago_id)
    if pago.estado != EstadoPago.CONFIRMADO.value:
        raise ErrorPago("Solo se pueden cancelar pagos confirmados.")
    if factura.estado == EstadoFactura.ANULADA.value:
        raise ErrorPago("La factura está anulada.")
    nota = f"Cancelado: {motivo}"
    pago.observaciones = f"{pago.observaciones}\n{nota}" if pago.observaciones else nota
    pago.estado = EstadoPago.CANCELADO
    pago.save()
    factura.saldo_pendiente = redondear(factura.saldo_pendiente + pago.monto)
    factura.estado = estado_segun_saldo(factura)
    factura.save()
    return pago
