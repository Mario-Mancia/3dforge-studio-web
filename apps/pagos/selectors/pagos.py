from apps.pagos.models import MetodoPago


def metodos_activos():
    return MetodoPago.objects.filter(activo=True).exclude(nombre__icontains="pasarela").order_by("nombre")
