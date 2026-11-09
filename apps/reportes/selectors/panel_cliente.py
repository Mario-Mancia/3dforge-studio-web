from decimal import Decimal

from django.db.models import Sum

from apps.cotizaciones.models import Cotizacion
from apps.crm.models import SolicitudSoporte
from apps.encargos.models import Encargo
from apps.facturacion.models import Factura
from apps.notificaciones.selectors import notificaciones as notificaciones

ESTADOS_CERRADOS = ("ENTREGADO", "CANCELADO")
ESTADOS_COBRABLES = ("PENDIENTE", "PARCIALMENTE_PAGADA", "VENCIDA")


def resumen_cliente(cliente, usuario):
    por_responder = Cotizacion.objects.filter(cliente=cliente, estado="ENVIADA")
    en_revision = Cotizacion.objects.filter(cliente=cliente, estado__in=["SOLICITADA", "BORRADOR"])
    pedidos = Encargo.objects.filter(cliente=cliente).exclude(estado__in=ESTADOS_CERRADOS)
    facturas = Factura.objects.filter(cliente=cliente, estado__in=ESTADOS_COBRABLES, saldo_pendiente__gt=0)
    soporte = SolicitudSoporte.objects.filter(cliente=cliente, estado__in=["ABIERTA", "EN_PROCESO"])
    return {
        "kpis": {
            "por_responder": por_responder.count(),
            "en_revision": en_revision.count(),
            "pedidos_en_curso": pedidos.count(),
            "saldo_pendiente": facturas.aggregate(t=Sum("saldo_pendiente"))["t"] or Decimal("0.00"),
            "soporte_abierto": soporte.count(),
        },
        "cotizaciones": list(por_responder.order_by("fecha_vencimiento")[:5]),
        "pedidos": list(pedidos.order_by("fecha_entrega_estimada", "-fecha_solicitud")[:5]),
        "facturas": list(facturas.order_by("fecha_vencimiento")[:5]),
        "soporte": list(soporte.order_by("-creado_en")[:5]),
        "notificaciones": [(n, notificaciones.destino(n, usuario)) for n in notificaciones.de_usuario(usuario)[:5]],
    }
