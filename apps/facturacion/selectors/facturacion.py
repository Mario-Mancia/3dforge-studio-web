from django.db.models import Prefetch, Q

from apps.facturacion.models import EstadoFactura, Factura
from apps.pagos.models import Pago


def _con_detalle(consulta):
    pagos = Pago.objects.select_related("metodo_pago", "registrado_por").order_by("fecha_pago", "pk")
    return consulta.select_related("cliente", "encargo").prefetch_related("detalles", Prefetch("pagos", queryset=pagos))


def facturas_del_cliente(cliente):
    return Factura.objects.filter(cliente=cliente).order_by("-fecha_emision")


def obtener_del_cliente(cliente, pk):
    return _con_detalle(Factura.objects.filter(cliente=cliente, pk=pk)).first()


def bandeja(estado="", busqueda=""):
    consulta = Factura.objects.select_related("cliente").order_by("-fecha_emision")
    if estado in EstadoFactura.values:
        consulta = consulta.filter(estado=estado)
    if busqueda:
        consulta = consulta.filter(
            Q(numero_factura__icontains=busqueda)
            | Q(nombre_facturacion__icontains=busqueda)
            | Q(cliente__correo__icontains=busqueda)
        )
    return consulta


def obtener_para_operador(pk):
    return _con_detalle(Factura.objects.filter(pk=pk)).first()
