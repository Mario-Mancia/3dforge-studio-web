import logging

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.cotizaciones.models import Cotizacion
from apps.crm.models import SolicitudSoporte
from apps.crm.services.crm import registrar_evento
from apps.encargos.models import Encargo
from apps.facturacion.models import Factura
from apps.notificaciones.services.notificaciones import notificar, notificar_personal
from apps.pagos.models import EstadoPago, Pago

registro = logging.getLogger(__name__)
PREFIJOS = ("COT-", "ENC-", "FAC-")
CAMPOS_PREVIOS = {
    Encargo: ("estado", "empleado_responsable_id"),
    SolicitudSoporte: ("estado", "usuario_responsable_id"),
}


def _capturar(sender, instance, **kwargs):
    if kwargs.get("raw") or not instance.pk:
        instance._previo = {}
        return
    campos = CAMPOS_PREVIOS.get(sender, ("estado",))
    instance._previo = sender.objects.filter(pk=instance.pk).values(*campos).first() or {}


for _modelo in (Cotizacion, Encargo, Factura, Pago, SolicitudSoporte):
    pre_save.connect(_capturar, sender=_modelo, dispatch_uid=f"eventos.previo.{_modelo.__name__}")


def seguro(funcion):
    def envoltura(sender, instance, **kwargs):
        if kwargs.get("raw"):
            return
        try:
            with transaction.atomic():
                funcion(instance, **kwargs)
        except Exception:
            registro.exception("Fallo el evento de %s", sender.__name__)

    return envoltura


def _creado(instance, created, update_fields, atributo="codigo"):
    codigo = getattr(instance, atributo, "")
    if created:
        return not codigo.startswith("TMP-")
    return bool(update_fields) and atributo in update_fields and codigo.startswith(PREFIJOS)


def _cambio(instance):
    previo = getattr(instance, "_previo", {}).get("estado")
    return previo if previo is not None and previo != instance.estado else None


@receiver(post_save, sender=Cotizacion, dispatch_uid="eventos.cotizacion")
@seguro
def _cotizacion(instance, created=False, update_fields=None, **kwargs):
    codigo, cliente = instance.codigo, instance.cliente
    if _creado(instance, created, update_fields):
        notificar_personal(
            f"Nueva solicitud de cotización {codigo}", f"El cliente {cliente} solicitó una cotización.", "cotizacion", instance.pk
        )
        return
    anterior = _cambio(instance)
    if anterior is None:
        return
    estado = instance.estado
    if estado == "ENVIADA":
        notificar(
            cliente.usuario, f"Cotización {codigo} disponible",
            "Revise la propuesta y acéptela o recházela.", "cotizacion", instance.pk, correo=True,
        )
    elif estado in ("ACEPTADA", "RECHAZADA"):
        titulo = f"Cotización {codigo} {'aceptada' if estado == 'ACEPTADA' else 'rechazada'}"
        if instance.usuario_responsable_id:
            notificar(instance.usuario_responsable, titulo, f"Cliente: {cliente}.", "cotizacion", instance.pk)
        else:
            notificar_personal(titulo, f"Cliente: {cliente}.", "cotizacion", instance.pk)
    elif estado == "VENCIDA":
        notificar(cliente.usuario, f"Cotización {codigo} vencida", "La vigencia terminó.", "cotizacion", instance.pk)
    elif estado == "CANCELADA":
        if anterior in ("BORRADOR", "ENVIADA"):
            notificar(cliente.usuario, f"Cotización {codigo} cancelada", "El equipo canceló la cotización.", "cotizacion", instance.pk)
        else:
            notificar_personal(f"Solicitud {codigo} cancelada", f"Cliente: {cliente}.", "cotizacion", instance.pk)


def _staff_encargo(encargo):
    return encargo.empleado_responsable.usuario if encargo.empleado_responsable_id else None


@receiver(post_save, sender=Encargo, dispatch_uid="eventos.encargo")
@seguro
def _encargo(instance, created=False, update_fields=None, **kwargs):
    codigo, cliente = instance.codigo, instance.cliente
    if _creado(instance, created, update_fields):
        notificar(
            cliente.usuario, f"Pedido {codigo} registrado",
            "Puede seguir su progreso en Mis pedidos.", "encargo", instance.pk, correo=True,
        )
        if instance.cotizacion_id is None:
            notificar_personal(f"Nuevo pedido de tienda {codigo}", f"El cliente {cliente} confirmó una compra.", "encargo", instance.pk)
        registrar_evento(cliente, _staff_encargo(instance), f"Encargo {codigo} creado")
        return
    previo = getattr(instance, "_previo", {})
    nuevo_empleado = instance.empleado_responsable_id
    if nuevo_empleado and nuevo_empleado != previo.get("empleado_responsable_id"):
        notificar(
            instance.empleado_responsable.usuario, f"Se le asignó el encargo {codigo}",
            f"Cliente: {cliente}.", "encargo", instance.pk,
        )
    if _cambio(instance) is None:
        return
    etiqueta = instance.get_estado_display()
    notificar(
        cliente.usuario, f"Pedido {codigo}: {etiqueta}", f"Su pedido cambió de estado a {etiqueta}.",
        "encargo", instance.pk, correo=instance.estado in ("FINALIZADO", "ENTREGADO", "CANCELADO"),
    )
    registrar_evento(cliente, _staff_encargo(instance), f"Encargo {codigo}: {etiqueta}")


@receiver(post_save, sender=Factura, dispatch_uid="eventos.factura")
@seguro
def _factura(instance, created=False, update_fields=None, **kwargs):
    numero, cliente = instance.numero_factura, instance.cliente
    if _creado(instance, created, update_fields, "numero_factura"):
        notificar(
            cliente.usuario, f"Factura {numero} emitida",
            f"Total ${instance.total}. El pago se coordina con el equipo.", "factura", instance.pk, correo=True,
        )
        staff = _staff_encargo(instance.encargo) if instance.encargo_id else None
        registrar_evento(cliente, staff, f"Factura {numero} emitida")
        return
    if _cambio(instance) is None:
        return
    etiqueta = instance.get_estado_display()
    notificar(
        cliente.usuario, f"Factura {numero}: {etiqueta}", f"El estado de su factura es {etiqueta}.",
        "factura", instance.pk, correo=instance.estado in ("PAGADA", "VENCIDA"),
    )


@receiver(post_save, sender=Pago, dispatch_uid="eventos.pago")
@seguro
def _pago(instance, created=False, **kwargs):
    factura = instance.factura
    cliente = factura.cliente
    if created and instance.estado == EstadoPago.CONFIRMADO:
        notificar(
            cliente.usuario, f"Pago #{instance.pk} registrado en la factura {factura.numero_factura}",
            f"Se registró un pago de ${instance.monto}.", "factura", factura.pk, correo=True,
        )
        registrar_evento(cliente, instance.registrado_por, f"Pago de ${instance.monto} en {factura.numero_factura}")
    elif _cambio(instance) is not None and instance.estado == EstadoPago.CANCELADO:
        notificar(
            cliente.usuario, f"Pago #{instance.pk} cancelado en la factura {factura.numero_factura}",
            f"Se canceló un pago de ${instance.monto}.", "factura", factura.pk,
        )


@receiver(post_save, sender=SolicitudSoporte, dispatch_uid="eventos.soporte")
@seguro
def _soporte(instance, created=False, **kwargs):
    cliente = instance.cliente
    if created:
        notificar_personal(f"Nueva solicitud de soporte #{instance.pk}", f"{cliente}: {instance.asunto}", "soporte", instance.pk)
        return
    previo = getattr(instance, "_previo", {})
    responsable = instance.usuario_responsable_id
    if responsable and responsable != previo.get("usuario_responsable_id"):
        notificar(instance.usuario_responsable, f"Se le asignó la solicitud #{instance.pk}", instance.asunto, "soporte", instance.pk)
    if _cambio(instance) is None:
        return
    etiqueta = instance.get_estado_display()
    notificar(
        cliente.usuario, f"Soporte #{instance.pk}: {etiqueta}", f"Su solicitud «{instance.asunto}» está {etiqueta.lower()}.",
        "soporte", instance.pk, correo=instance.estado in ("RESUELTA", "CERRADA"),
    )
