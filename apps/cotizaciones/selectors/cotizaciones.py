from django.db.models import Count, Q

from apps.cotizaciones.models import Cotizacion, EstadoCotizacion


def cotizaciones_del_cliente(cliente):
    return Cotizacion.objects.filter(cliente=cliente).order_by("-fecha_emision")


def obtener_del_cliente(cliente, pk):
    return (
        Cotizacion.objects.filter(cliente=cliente, pk=pk)
        .select_related("cliente")
        .prefetch_related("detalles__servicio", "archivos")
        .first()
    )


def bandeja_operador(estado="", busqueda=""):
    consulta = Cotizacion.objects.select_related("cliente", "usuario_responsable").order_by("-fecha_emision")
    if estado in EstadoCotizacion.values:
        consulta = consulta.filter(estado=estado)
    if busqueda:
        consulta = consulta.filter(
            Q(codigo__icontains=busqueda)
            | Q(cliente__correo__icontains=busqueda)
            | Q(cliente__nombres__icontains=busqueda)
            | Q(cliente__apellidos__icontains=busqueda)
            | Q(cliente__nombre_empresa__icontains=busqueda)
        )
    return consulta


def obtener_para_operador(pk):
    return (
        Cotizacion.objects.filter(pk=pk)
        .select_related("cliente", "usuario_responsable")
        .prefetch_related("detalles__servicio", "archivos")
        .first()
    )


def contar_por_estado():
    filas = Cotizacion.objects.values("estado").annotate(total=Count("pk"))
    return {fila["estado"]: fila["total"] for fila in filas}
