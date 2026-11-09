from django.db.models import Q

from apps.clientes.models import Cliente
from apps.crm.models import EstadoSoporte, SolicitudSoporte


def clientes_para_operador(busqueda=""):
    consulta = Cliente.objects.order_by("-creado_en")
    if busqueda:
        consulta = consulta.filter(
            Q(correo__icontains=busqueda)
            | Q(nombres__icontains=busqueda)
            | Q(apellidos__icontains=busqueda)
            | Q(nombre_empresa__icontains=busqueda)
        )
    return consulta


def datos_cliente(pk):
    cliente = Cliente.objects.filter(pk=pk).first()
    if cliente is None:
        return None
    return {
        "cliente": cliente,
        "interacciones": cliente.interacciones.select_related("usuario_responsable").order_by("-fecha_interaccion")[:15],
        "notas": cliente.notas.select_related("usuario").order_by("-fecha_creacion")[:15],
        "cotizaciones": cliente.cotizaciones.order_by("-fecha_emision")[:5],
        "encargos": cliente.encargos.order_by("-fecha_solicitud")[:5],
        "facturas": cliente.facturas.order_by("-fecha_emision")[:5],
        "solicitudes": cliente.solicitudes_soporte.order_by("-creado_en")[:5],
    }


def solicitudes_del_cliente(cliente):
    return SolicitudSoporte.objects.filter(cliente=cliente).order_by("-creado_en")


def obtener_solicitud_del_cliente(cliente, pk):
    return SolicitudSoporte.objects.filter(cliente=cliente, pk=pk).select_related("usuario_responsable").first()


def bandeja_soporte(estado="", busqueda=""):
    consulta = SolicitudSoporte.objects.select_related("cliente", "usuario_responsable").order_by("-creado_en")
    if estado in EstadoSoporte.values:
        consulta = consulta.filter(estado=estado)
    if busqueda:
        consulta = consulta.filter(Q(asunto__icontains=busqueda) | Q(cliente__correo__icontains=busqueda))
    return consulta


def obtener_solicitud(pk):
    return SolicitudSoporte.objects.filter(pk=pk).select_related("cliente", "usuario_responsable").first()
