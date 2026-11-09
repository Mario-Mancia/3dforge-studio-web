from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone

from apps.facturacion.models import EstadoFactura, Factura
from apps.pagos.models import EstadoPago, Pago

MAX_FILAS_CSV = 50000


def limites(desde, hasta):
    inicio = timezone.make_aware(datetime.combine(desde, time.min))
    fin = timezone.make_aware(datetime.combine(hasta + timedelta(days=1), time.min))
    return inicio, fin


def facturas_en_rango(desde, hasta):
    inicio, fin = limites(desde, hasta)
    return (
        Factura.objects.filter(fecha_emision__gte=inicio, fecha_emision__lt=fin)
        .select_related("cliente")
        .order_by("-fecha_emision", "-pk")
    )


def pagos_en_rango(desde, hasta):
    inicio, fin = limites(desde, hasta)
    return (
        Pago.objects.filter(fecha_pago__gte=inicio, fecha_pago__lt=fin)
        .select_related("factura", "factura__cliente", "metodo_pago", "registrado_por")
        .order_by("-fecha_pago", "-pk")
    )


def _cero(valor):
    return valor or Decimal("0.00")


def resumen_ventas(desde, hasta):
    facturas = facturas_en_rango(desde, hasta)
    validas = facturas.exclude(estado=EstadoFactura.ANULADA)
    pagos = pagos_en_rango(desde, hasta).filter(estado=EstadoPago.CONFIRMADO)
    facturado = _cero(validas.aggregate(t=Sum("total"))["t"])
    cantidad = validas.count()
    por_metodo = (
        pagos.values("metodo_pago__nombre").annotate(total=Sum("monto"), pagos=Count("pk")).order_by("-total")
    )
    return {
        "facturado": facturado,
        "cobrado": _cero(pagos.aggregate(t=Sum("monto"))["t"]),
        "saldo_facturas": _cero(validas.aggregate(t=Sum("saldo_pendiente"))["t"]),
        "cantidad_facturas": cantidad,
        "cantidad_anuladas": facturas.filter(estado=EstadoFactura.ANULADA).count(),
        "cantidad_pagos": pagos.count(),
        "ticket_promedio": (facturado / cantidad).quantize(Decimal("0.01")) if cantidad else Decimal("0.00"),
        "por_metodo": [
            {"metodo": fila["metodo_pago__nombre"], "total": fila["total"], "pagos": fila["pagos"]} for fila in por_metodo
        ],
    }


def _celda(valor):
    texto = "" if valor is None else str(valor)
    return "'" + texto if texto[:1] in ("=", "+", "-", "@", "\t", "\r") else texto


def _fecha(valor):
    return timezone.localtime(valor).strftime("%Y-%m-%d %H:%M") if valor else ""


def filas_exportacion(tipo, desde, hasta):
    if tipo == "facturas":
        encabezados = [
            "Numero", "Fecha emision", "Cliente", "Identificacion fiscal", "Estado",
            "Subtotal", "Descuento", "Impuesto", "Total", "Saldo pendiente",
        ]
        filas = (
            [
                _celda(f.numero_factura), _fecha(f.fecha_emision), _celda(f.nombre_facturacion),
                _celda(f.identificacion_fiscal), f.get_estado_display(),
                f.subtotal, f.descuento, f.impuesto, f.total, f.saldo_pendiente,
            ]
            for f in facturas_en_rango(desde, hasta)[:MAX_FILAS_CSV]
        )
    else:
        encabezados = ["ID", "Fecha pago", "Factura", "Cliente", "Metodo", "Referencia", "Monto", "Estado", "Registro"]
        filas = (
            [
                p.pk, _fecha(p.fecha_pago), _celda(p.factura.numero_factura), _celda(p.factura.nombre_facturacion),
                _celda(p.metodo_pago.nombre), _celda(p.referencia), p.monto, p.get_estado_display(),
                _celda(p.registrado_por.correo if p.registrado_por else ""),
            ]
            for p in pagos_en_rango(desde, hasta)[:MAX_FILAS_CSV]
        )
    return encabezados, filas
