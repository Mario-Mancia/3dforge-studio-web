import logging
from datetime import date, datetime
from decimal import Decimal

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

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

ESTADOS_PEDIDO = {
    "PENDIENTE": "Su pedido está pendiente de revisión. En breve nuestro equipo lo atenderá.",
    "EN_REVISION": "Estamos revisando los detalles de su pedido para confirmar que todo esté en orden.",
    "APROBADO": "Su pedido fue aprobado y quedó en nuestra cola de producción.",
    "EN_PRODUCCION": "Su pedido ya está en producción. Pronto tendrá novedades.",
    "EN_ESPERA": "Su pedido está en espera por el momento. Si necesitamos algo de usted, nos comunicaremos.",
    "FINALIZADO": "Su pedido está terminado. Coordinaremos con usted la entrega o el retiro.",
    "ENTREGADO": "Su pedido fue entregado. ¡Gracias por confiar en nosotros!",
    "CANCELADO": "Su pedido fue cancelado. Si no esperaba este cambio, contáctenos desde la sección Soporte.",
}
ESTADOS_FACTURA = {
    "PAGADA": "Su factura quedó pagada en su totalidad. ¡Gracias por su pago!",
    "VENCIDA": "Su factura venció y aún tiene saldo pendiente. Comuníquese con nuestro equipo para regularizarla.",
    "PARCIALMENTE_PAGADA": "Registramos un pago parcial en su factura; aún queda un saldo por cubrir.",
    "ANULADA": "Su factura fue anulada y ya no requiere pago.",
    "PENDIENTE": "Su factura está pendiente de pago.",
}
ESTADOS_SOPORTE = {
    "EN_PROCESO": "Nuestro equipo ya está trabajando en su solicitud.",
    "RESUELTA": "Marcamos su solicitud como resuelta. Si el problema continúa, cree una nueva solicitud mencionando este número.",
    "CERRADA": "Su solicitud fue cerrada. Si necesita más ayuda, puede abrir una nueva en cualquier momento.",
    "ABIERTA": "Su solicitud está abierta y será atendida pronto.",
}


def _dinero(valor):
    try:
        return f"${Decimal(valor):,.2f}"
    except Exception:
        return "-"


def _fecha(valor):
    if not valor:
        return "-"
    if isinstance(valor, datetime):
        return timezone.localtime(valor).strftime("%d/%m/%Y")
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")
    return str(valor)


def _cantidad(valor):
    try:
        return f"{Decimal(valor).normalize():f}"
    except Exception:
        return str(valor)


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


# ---- Cotizaciones ------------------------------------------------------------------------------


def _detalles_cotizacion(cotizacion):
    filas = [("Cotización", cotizacion.codigo)]
    for linea in cotizacion.detalles.all()[:5]:
        filas.append(
            (linea.descripcion, f"{_cantidad(linea.cantidad)} × {_dinero(linea.precio_unitario)} = {_dinero(linea.subtotal)}")
        )
    filas += [("Subtotal", _dinero(cotizacion.subtotal)), ("Impuesto", _dinero(cotizacion.impuesto)), ("Total", _dinero(cotizacion.total))]
    if cotizacion.plazo_entrega_dias:
        filas.append(("Plazo de entrega", f"{cotizacion.plazo_entrega_dias} días"))
    filas.append(("Válida hasta", _fecha(cotizacion.fecha_vencimiento)))
    return filas


@receiver(post_save, sender=Cotizacion, dispatch_uid="eventos.cotizacion")
@seguro
def _cotizacion(instance, created=False, update_fields=None, **kwargs):
    codigo, cliente = instance.codigo, instance.cliente
    total = _dinero(instance.total)
    if _creado(instance, created, update_fields):
        automatica = " (cotización automática 3D)" if (instance.solicitud or "").startswith("Cotización automática") else ""
        notificar_personal(
            f"Nueva solicitud de cotización {codigo}",
            f"El cliente {cliente} solicitó una cotización{automatica}. Total preliminar: {total}. "
            "Revísela, ajuste los importes si hace falta y envíe la propuesta.",
            "cotizacion", instance.pk,
        )
        return
    anterior = _cambio(instance)
    if anterior is None:
        return
    estado = instance.estado
    if estado == "ENVIADA":
        parrafos = [
            "Nuestro equipo revisó su solicitud y preparó una propuesta con el precio y el plazo de entrega.",
            "Para continuar, ingrese a su cuenta y acepte o rechace la propuesta. Si la deja vencer, tendrá que solicitar una nueva cotización.",
        ]
        if instance.observaciones:
            parrafos.insert(1, f"Notas del equipo: {instance.observaciones}")
        notificar(
            cliente.usuario, f"Cotización {codigo} disponible",
            f"Su cotización por {total} está lista y es válida hasta el {_fecha(instance.fecha_vencimiento)}. "
            "Revise el detalle y acéptela o recházela antes de que venza.",
            "cotizacion", instance.pk, correo=True,
            parrafos=parrafos, detalles=lambda: _detalles_cotizacion(Cotizacion.objects.get(pk=instance.pk)),
            boton="Ver mi cotización",
        )
    elif estado in ("ACEPTADA", "RECHAZADA"):
        aceptada = estado == "ACEPTADA"
        titulo = f"Cotización {codigo} {'aceptada' if aceptada else 'rechazada'}"
        mensaje = (
            f"El cliente {cliente} aceptó la cotización por {total}. Ya puede crear el pedido desde la cotización."
            if aceptada
            else f"El cliente {cliente} rechazó la cotización por {total}."
        )
        if instance.usuario_responsable_id:
            notificar(instance.usuario_responsable, titulo, mensaje, "cotizacion", instance.pk)
        else:
            notificar_personal(titulo, mensaje, "cotizacion", instance.pk)
    elif estado == "VENCIDA":
        notificar(
            cliente.usuario, f"Cotización {codigo} vencida",
            f"La vigencia de su cotización por {total} terminó. Si todavía necesita el trabajo, solicite una nueva cotización.",
            "cotizacion", instance.pk,
        )
    elif estado == "CANCELADA":
        if anterior in ("BORRADOR", "ENVIADA"):
            notificar(
                cliente.usuario, f"Cotización {codigo} cancelada",
                "El equipo canceló esta cotización. Si tiene dudas, escríbanos desde la sección Soporte.",
                "cotizacion", instance.pk,
            )
        else:
            notificar_personal(
                f"Solicitud {codigo} cancelada", f"El cliente {cliente} canceló su solicitud antes de la revisión.",
                "cotizacion", instance.pk,
            )


# ---- Pedidos -----------------------------------------------------------------------------------


def _staff_encargo(encargo):
    return encargo.empleado_responsable.usuario if encargo.empleado_responsable_id else None


def _detalles_pedido(encargo):
    filas = [("Pedido", encargo.codigo), ("Estado", encargo.get_estado_display()), ("Total", _dinero(encargo.total))]
    if encargo.fecha_entrega_estimada:
        filas.append(("Entrega estimada", _fecha(encargo.fecha_entrega_estimada)))
    if encargo.fecha_entrega_real:
        filas.append(("Entregado el", _fecha(encargo.fecha_entrega_real)))
    return filas


@receiver(post_save, sender=Encargo, dispatch_uid="eventos.encargo")
@seguro
def _encargo(instance, created=False, update_fields=None, **kwargs):
    codigo, cliente = instance.codigo, instance.cliente
    total = _dinero(instance.total)
    if _creado(instance, created, update_fields):
        tienda = instance.cotizacion_id is None
        origen = "su compra en la tienda" if tienda else "la cotización que usted aceptó"
        notificar(
            cliente.usuario, f"Pedido {codigo} registrado",
            f"Recibimos su pedido por {total}, generado a partir de {origen}. "
            "Le avisaremos cada vez que cambie de estado y también puede seguirlo en Mis pedidos.",
            "encargo", instance.pk, correo=True,
            parrafos=[
                f"Gracias. Registramos su pedido a partir de {origen}.",
                "Nuestro equipo lo revisará y lo pondrá en producción. Le avisaremos cada vez que cambie de estado; "
                "también puede seguir el avance en cualquier momento desde Mis pedidos.",
            ],
            detalles=lambda: [("Pedido", codigo), ("Origen", "Compra en la tienda" if tienda else "Cotización aceptada"), ("Total", total), ("Estado", "Pendiente")],
            boton="Ver mi pedido",
        )
        if tienda:
            notificar_personal(
                f"Nuevo pedido de tienda {codigo}",
                f"El cliente {cliente} confirmó una compra por {total}. Revise el inventario y avance el pedido.",
                "encargo", instance.pk,
            )
        registrar_evento(cliente, _staff_encargo(instance), f"Encargo {codigo} creado")
        return
    previo = getattr(instance, "_previo", {})
    nuevo_empleado = instance.empleado_responsable_id
    if nuevo_empleado and nuevo_empleado != previo.get("empleado_responsable_id"):
        notificar(
            instance.empleado_responsable.usuario, f"Se le asignó el encargo {codigo}",
            f"Cliente: {cliente}. Pedido por {total}; revíselo y mantenga su estado actualizado.", "encargo", instance.pk,
        )
    if _cambio(instance) is None:
        return
    etiqueta = instance.get_estado_display()
    explicacion = ESTADOS_PEDIDO.get(instance.estado, f"Su pedido cambió de estado a {etiqueta}.")
    notificar(
        cliente.usuario, f"Pedido {codigo}: {etiqueta}", explicacion, "encargo", instance.pk,
        correo=instance.estado in ("FINALIZADO", "ENTREGADO", "CANCELADO"),
        parrafos=[explicacion, "Puede ver el detalle y el historial completo de su pedido en su cuenta."],
        detalles=lambda: _detalles_pedido(Encargo.objects.get(pk=instance.pk)),
        boton="Ver mi pedido",
    )
    registrar_evento(cliente, _staff_encargo(instance), f"Encargo {codigo}: {etiqueta}")


# ---- Facturas y pagos --------------------------------------------------------------------------


def _detalles_factura(factura):
    return [
        ("Factura", factura.numero_factura),
        ("Fecha de emisión", _fecha(factura.fecha_emision)),
        ("Vencimiento", _fecha(factura.fecha_vencimiento)),
        ("Subtotal", _dinero(factura.subtotal)),
        ("Impuesto", _dinero(factura.impuesto)),
        ("Total", _dinero(factura.total)),
        ("Saldo pendiente", _dinero(factura.saldo_pendiente)),
        ("Estado", factura.get_estado_display()),
    ]


@receiver(post_save, sender=Factura, dispatch_uid="eventos.factura")
@seguro
def _factura(instance, created=False, update_fields=None, **kwargs):
    numero, cliente = instance.numero_factura, instance.cliente
    if _creado(instance, created, update_fields, "numero_factura"):
        notificar(
            cliente.usuario, f"Factura {numero} emitida",
            f"Emitimos la factura {numero} por {_dinero(instance.total)}, con vencimiento el {_fecha(instance.fecha_vencimiento)}. "
            "El pago es en efectivo y se coordina con nuestro equipo.",
            "factura", instance.pk, correo=True,
            parrafos=[
                "Emitimos la factura correspondiente a su pedido. Encontrará el detalle completo en su cuenta.",
                "El pago es en efectivo y se coordina directamente con nuestro equipo. Cuando registremos su pago, "
                "recibirá una confirmación con el saldo actualizado.",
            ],
            detalles=lambda: _detalles_factura(Factura.objects.get(pk=instance.pk)),
            boton="Ver mi factura",
        )
        staff = _staff_encargo(instance.encargo) if instance.encargo_id else None
        registrar_evento(cliente, staff, f"Factura {numero} emitida")
        return
    if _cambio(instance) is None:
        return
    etiqueta = instance.get_estado_display()
    explicacion = ESTADOS_FACTURA.get(instance.estado, f"El estado de su factura es {etiqueta}.")
    notificar(
        cliente.usuario, f"Factura {numero}: {etiqueta}", explicacion, "factura", instance.pk,
        correo=instance.estado in ("PAGADA", "VENCIDA"),
        parrafos=[explicacion],
        detalles=lambda: _detalles_factura(Factura.objects.get(pk=instance.pk)),
        boton="Ver mi factura",
    )


def _detalles_pago(pago_id):
    def construir():
        pago = Pago.objects.select_related("factura", "metodo_pago").get(pk=pago_id)
        filas = [
            ("Factura", pago.factura.numero_factura),
            ("Monto pagado", _dinero(pago.monto)),
            ("Método de pago", pago.metodo_pago.nombre),
            ("Fecha del pago", _fecha(pago.fecha_pago)),
        ]
        if pago.referencia:
            filas.append(("Referencia", pago.referencia))
        filas.append(("Saldo pendiente", _dinero(pago.factura.saldo_pendiente)))
        return filas

    return construir


def _parrafos_pago(pago_id):
    def construir():
        pago = Pago.objects.select_related("factura").get(pk=pago_id)
        saldo = pago.factura.saldo_pendiente
        cierre = (
            "Con este pago su factura quedó saldada. ¡Gracias!"
            if saldo is not None and Decimal(saldo) <= 0
            else f"El saldo pendiente de la factura es {_dinero(saldo)}."
        )
        return [f"Registramos su pago de {_dinero(pago.monto)} en la factura {pago.factura.numero_factura}.", cierre]

    return construir


@receiver(post_save, sender=Pago, dispatch_uid="eventos.pago")
@seguro
def _pago(instance, created=False, **kwargs):
    factura = instance.factura
    cliente = factura.cliente
    if created and instance.estado == EstadoPago.CONFIRMADO:
        notificar(
            cliente.usuario, f"Pago #{instance.pk} registrado en la factura {factura.numero_factura}",
            f"Registramos su pago de {_dinero(instance.monto)} en la factura {factura.numero_factura}. "
            "Puede ver el saldo actualizado en Mis facturas.",
            "factura", factura.pk, correo=True,
            parrafos=_parrafos_pago(instance.pk), detalles=_detalles_pago(instance.pk), boton="Ver mi factura",
        )
        registrar_evento(cliente, instance.registrado_por, f"Pago de ${instance.monto} en {factura.numero_factura}")
    elif _cambio(instance) is not None and instance.estado == EstadoPago.CANCELADO:
        notificar(
            cliente.usuario, f"Pago #{instance.pk} cancelado en la factura {factura.numero_factura}",
            f"Se canceló el pago de {_dinero(instance.monto)} registrado en la factura {factura.numero_factura}. "
            "Si tiene dudas, comuníquese con nuestro equipo.",
            "factura", factura.pk,
        )


# ---- Soporte -----------------------------------------------------------------------------------


@receiver(post_save, sender=SolicitudSoporte, dispatch_uid="eventos.soporte")
@seguro
def _soporte(instance, created=False, **kwargs):
    cliente = instance.cliente
    if created:
        notificar_personal(
            f"Nueva solicitud de soporte #{instance.pk}",
            f"{cliente} ({instance.get_prioridad_display().lower()}): {instance.asunto}. Respóndala lo antes posible.",
            "soporte", instance.pk,
        )
        return
    previo = getattr(instance, "_previo", {})
    responsable = instance.usuario_responsable_id
    if responsable and responsable != previo.get("usuario_responsable_id"):
        notificar(
            instance.usuario_responsable, f"Se le asignó la solicitud #{instance.pk}",
            f"{cliente}: {instance.asunto}.", "soporte", instance.pk,
        )
    if _cambio(instance) is None:
        return
    etiqueta = instance.get_estado_display()
    explicacion = ESTADOS_SOPORTE.get(instance.estado, f"Su solicitud «{instance.asunto}» está {etiqueta.lower()}.")
    notificar(
        cliente.usuario, f"Soporte #{instance.pk}: {etiqueta}",
        f"Su solicitud «{instance.asunto}» está {etiqueta.lower()}. {explicacion}", "soporte", instance.pk,
        correo=instance.estado in ("RESUELTA", "CERRADA"),
        parrafos=[f"Actualizamos su solicitud «{instance.asunto}».", explicacion],
        detalles=[
            ("Solicitud", f"#{instance.pk}"),
            ("Asunto", instance.asunto),
            ("Estado", etiqueta),
            ("Prioridad", instance.get_prioridad_display()),
        ],
        boton="Ver mi solicitud",
    )
