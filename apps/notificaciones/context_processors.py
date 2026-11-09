from apps.notificaciones.models import Notificacion


def no_leidas(request):
    usuario = getattr(request, "user", None)
    if usuario is None or not usuario.is_authenticated:
        return {}
    return {"notificaciones_no_leidas": Notificacion.objects.filter(usuario=usuario, leida=False).count()}
