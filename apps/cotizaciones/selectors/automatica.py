from apps.cotizaciones.models import Filamento


def filamentos_activos():
    return Filamento.objects.filter(activo=True).order_by("material", "color")


def filamentos_admin():
    return Filamento.objects.order_by("material", "color")
