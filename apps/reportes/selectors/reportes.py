from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.core.cache import cache
from django.db.models import Count, F, Q, Sum, Value
from django.db.models.functions import Coalesce, TruncDay, TruncMonth, TruncWeek
from django.utils import timezone

from apps.catalogo.models import Producto
from apps.clientes.models import Cliente
from apps.cotizaciones.models import Cotizacion
from apps.crm.models import SolicitudSoporte
from apps.encargos.models import Encargo, EstadoEncargo
from apps.facturacion.models import EstadoFactura, Factura, FacturaDetalle
from apps.pagos.models import EstadoPago, Pago

RANGOS = {"30d": "Últimos 30 días", "6m": "Últimos 6 meses", "12m": "Últimos 12 meses"}
CACHE_SEGUNDOS = 60
ESTADOS_COBRO = (
    EstadoFactura.PENDIENTE.value,
    EstadoFactura.PARCIALMENTE_PAGADA.value,
    EstadoFactura.VENCIDA.value,
)
ESTADOS_CERRADOS = (EstadoEncargo.ENTREGADO.value, EstadoEncargo.CANCELADO.value)


def rango_valido(valor):
    return valor if valor in RANGOS else "6m"


def _cero(valor):
    return valor or Decimal("0.00")


def _inicio_dia(fecha):
    return timezone.make_aware(datetime.combine(fecha, time.min))


def _sumar_meses(fecha, meses):
    indice = fecha.year * 12 + fecha.month - 1 + meses
    return date(indice // 12, indice % 12 + 1, 1)


def periodo(rango, ahora=None):
    rango = rango_valido(rango)
    hoy = timezone.localtime(ahora or timezone.now()).date()
    if rango == "30d":
        pasos = [hoy - timedelta(days=29 - i) for i in range(30)]
        return {"rango": rango, "pasos": pasos, "trunc": TruncDay, "formato": "%d/%m", "inicio": _inicio_dia(pasos[0])}
    meses = 6 if rango == "6m" else 12
    primero = _sumar_meses(hoy.replace(day=1), -(meses - 1))
    pasos = [_sumar_meses(primero, i) for i in range(meses)]
    return {"rango": rango, "pasos": pasos, "trunc": TruncMonth, "formato": "%m/%Y", "inicio": _inicio_dia(pasos[0])}


def periodo_semanal(semanas=8, ahora=None):
    hoy = timezone.localtime(ahora or timezone.now()).date()
    lunes = hoy - timedelta(days=hoy.weekday())
    pasos = [lunes - timedelta(weeks=semanas - 1 - i) for i in range(semanas)]
    return {"pasos": pasos, "trunc": TruncWeek, "formato": "%d/%m", "inicio": _inicio_dia(pasos[0])}


def _serie(consulta, campo, agregado, per):
    filas = (
        consulta.filter(**{f"{campo}__gte": per["inicio"]})
        .annotate(bucket=per["trunc"](campo))
        .values("bucket")
        .annotate(valor=agregado)
        .order_by("bucket")
    )
    datos = {}
    for fila in filas:
        clave = fila["bucket"]
        clave = timezone.localtime(clave).date() if isinstance(clave, datetime) else clave
        datos[clave] = float(fila["valor"] or 0)
    return [datos.get(paso, 0.0) for paso in per["pasos"]]


def _grafico(etiquetas, series, dinero=False):
    return {"etiquetas": etiquetas, "series": [{"nombre": n, "valores": v} for n, v in series], "dinero": dinero}


def _facturas_vencidas(ahora):
    return Factura.objects.filter(
        Q(estado=EstadoFactura.VENCIDA)
        | Q(
            estado__in=[EstadoFactura.PENDIENTE, EstadoFactura.PARCIALMENTE_PAGADA],
            saldo_pendiente__gt=0,
            fecha_vencimiento__lt=ahora,
        )
    )


def _encargos_por_estado():
    conteos = dict(Encargo.objects.values_list("estado").annotate(total=Count("pk")))
    etiquetas = [etiqueta for _, etiqueta in EstadoEncargo.choices]
    return _grafico(etiquetas, [("Encargos", [conteos.get(valor, 0) for valor, _ in EstadoEncargo.choices])])


def kpis_admin(ahora=None):
    ahora = ahora or timezone.now()
    inicio_mes = _inicio_dia(timezone.localtime(ahora).date().replace(day=1))
    facturas = Factura.objects.exclude(estado=EstadoFactura.ANULADA)
    return {
        "ventas_mes": _cero(facturas.filter(fecha_emision__gte=inicio_mes).aggregate(t=Sum("total"))["t"]),
        "cobrado_mes": _cero(
            Pago.objects.filter(estado=EstadoPago.CONFIRMADO, fecha_pago__gte=inicio_mes).aggregate(t=Sum("monto"))["t"]
        ),
        "por_cobrar": _cero(
            Factura.objects.filter(estado__in=ESTADOS_COBRO).aggregate(t=Sum("saldo_pendiente"))["t"]
        ),
        "facturas_vencidas": _facturas_vencidas(ahora).count(),
        "productos_bajo_stock": Producto.objects.filter(activo=True, stock__lte=F("stock_minimo")).count(),
        "clientes_nuevos": Cliente.objects.filter(creado_en__gte=inicio_mes).count(),
    }


def conversion_cotizaciones(per):
    cotizaciones = Cotizacion.objects.filter(fecha_emision__gte=per["inicio"])
    cerradas = cotizaciones.filter(estado__in=["ACEPTADA", "RECHAZADA", "VENCIDA"]).count()
    if not cerradas:
        return None
    return round(cotizaciones.filter(estado="ACEPTADA").count() * 100 / cerradas, 1)


def graficos_admin(per):
    etiquetas = [paso.strftime(per["formato"]) for paso in per["pasos"]]
    ventas = _serie(Factura.objects.exclude(estado=EstadoFactura.ANULADA), "fecha_emision", Sum("total"), per)
    cobros = _serie(Pago.objects.filter(estado=EstadoPago.CONFIRMADO), "fecha_pago", Sum("monto"), per)
    lineas = FacturaDetalle.objects.exclude(factura__estado=EstadoFactura.ANULADA).filter(
        factura__fecha_emision__gte=per["inicio"]
    )
    por_tipo = lineas.aggregate(
        servicios=Sum("subtotal", filter=Q(servicio__isnull=False)),
        productos=Sum("subtotal", filter=Q(producto__isnull=False)),
        otros=Sum("subtotal", filter=Q(servicio__isnull=True, producto__isnull=True)),
    )
    top = (
        lineas.annotate(nombre=Coalesce("producto__nombre", "servicio__nombre", Value("Sin catálogo")))
        .values("nombre")
        .annotate(total=Sum("subtotal"))
        .order_by("-total")[:5]
    )
    return {
        "ventas_cobros": _grafico(etiquetas, [("Ventas", ventas), ("Cobros", cobros)], dinero=True),
        "ingresos_tipo": _grafico(
            ["Servicios", "Productos", "Otros"],
            [("Ingresos", [float(_cero(por_tipo[c])) for c in ("servicios", "productos", "otros")])],
            dinero=True,
        ),
        "top_ventas": _grafico(
            [fila["nombre"] for fila in top], [("Ingresos", [float(fila["total"] or 0) for fila in top])], dinero=True
        ),
        "encargos_estado": _encargos_por_estado(),
    }


def _calcular_admin(rango):
    per = periodo(rango)
    ahora = timezone.now()
    return {
        "rango": per["rango"],
        "kpis": kpis_admin(ahora),
        "conversion": conversion_cotizaciones(per),
        "graficos": graficos_admin(per),
        "stock_bajo": [
            {"pk": p.pk, "sku": p.sku, "nombre": p.nombre, "stock": p.stock, "minimo": p.stock_minimo}
            for p in Producto.objects.filter(activo=True, stock__lte=F("stock_minimo")).order_by("stock", "nombre")[:8]
        ],
        "vencidas": [
            {"pk": f.pk, "numero": f.numero_factura, "cliente": f.nombre_facturacion, "saldo": f.saldo_pendiente, "vence": f.fecha_vencimiento}
            for f in _facturas_vencidas(ahora).order_by("fecha_vencimiento")[:8]
        ],
    }


def datos_admin(rango="6m"):
    rango = rango_valido(rango)
    return cache.get_or_set(f"reportes:admin:{rango}", lambda: _calcular_admin(rango), CACHE_SEGUNDOS)


def _calcular_operador():
    ahora = timezone.now()
    per = periodo_semanal()
    etiquetas = [paso.strftime(per["formato"]) for paso in per["pasos"]]
    return {
        "kpis": {
            "cotizaciones_por_atender": Cotizacion.objects.filter(estado__in=["SOLICITADA", "BORRADOR"]).count(),
            "encargos_activos": Encargo.objects.exclude(estado__in=ESTADOS_CERRADOS).count(),
            "facturas_vencidas": _facturas_vencidas(ahora).count(),
            "soporte_abierto": SolicitudSoporte.objects.filter(estado__in=["ABIERTA", "EN_PROCESO"]).count(),
        },
        "graficos": {
            "encargos_estado": _encargos_por_estado(),
            "carga_semanal": _grafico(
                etiquetas,
                [
                    ("Encargos nuevos", _serie(Encargo.objects.all(), "fecha_solicitud", Count("pk"), per)),
                    ("Cotizaciones nuevas", _serie(Cotizacion.objects.all(), "fecha_emision", Count("pk"), per)),
                ],
            ),
        },
    }


def datos_operador():
    return cache.get_or_set("reportes:operador", _calcular_operador, CACHE_SEGUNDOS)


def trabajo_operador(usuario):
    sin_cerrar = Encargo.objects.exclude(estado__in=ESTADOS_CERRADOS)
    propios = sin_cerrar.filter(empleado_responsable__usuario=usuario)
    mio_o_libre = Q(usuario_responsable__isnull=True) | Q(usuario_responsable=usuario)
    return {
        "mis_encargos_total": propios.count(),
        "mis_encargos": list(
            propios.select_related("cliente").order_by("fecha_entrega_estimada", "fecha_solicitud")[:8]
        ),
        "cotizaciones": list(
            Cotizacion.objects.filter(estado__in=["SOLICITADA", "BORRADOR"])
            .filter(mio_o_libre)
            .select_related("cliente")
            .order_by("fecha_emision")[:8]
        ),
        "soporte": list(
            SolicitudSoporte.objects.filter(estado__in=["ABIERTA", "EN_PROCESO"])
            .filter(mio_o_libre)
            .select_related("cliente")
            .order_by("creado_en")[:8]
        ),
    }
