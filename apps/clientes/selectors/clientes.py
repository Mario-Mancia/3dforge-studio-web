from apps.clientes.models import Cliente


def obtener_cliente_de(usuario):
    return Cliente.objects.filter(usuario=usuario).first()


def actividad_reciente(cliente, limite=5):
    return {
        "cotizaciones": list(cliente.cotizaciones.order_by("-fecha_emision")[:limite]),
        "encargos": list(cliente.encargos.order_by("-fecha_solicitud")[:limite]),
    }
