from django.db.models import Count, Prefetch, Q

from apps.encargos.models import Encargo, EstadoEncargo, HistorialEncargo
from apps.usuarios.models import Empleado


def _con_detalle(consulta):
    historial = HistorialEncargo.objects.select_related("usuario").order_by("fecha_cambio", "pk")
    return consulta.select_related("cliente", "empleado_responsable__usuario").prefetch_related(
        "detalles__servicio", "detalles__producto", "detalles__archivos", Prefetch("historial", queryset=historial)
    )


def encargos_del_cliente(cliente):
    return Encargo.objects.filter(cliente=cliente).order_by("-fecha_solicitud")


def obtener_del_cliente(cliente, pk):
    return _con_detalle(Encargo.objects.filter(cliente=cliente, pk=pk)).first()


def bandeja_operador(estado="", busqueda=""):
    consulta = Encargo.objects.select_related("cliente", "empleado_responsable__usuario").order_by("-fecha_solicitud")
    if estado in EstadoEncargo.values:
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
    return _con_detalle(Encargo.objects.filter(pk=pk)).first()


def empleados_activos():
    return Empleado.objects.filter(activo=True).select_related("usuario").order_by("codigo_empleado")


def contar_por_estado():
    filas = Encargo.objects.values("estado").annotate(total=Count("pk"))
    return {fila["estado"]: fila["total"] for fila in filas}
