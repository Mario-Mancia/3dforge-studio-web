from django.urls import reverse

from apps.notificaciones.models import Notificacion

RUTAS = {
    "cotizacion": ("customer:cotizacion", "operator:cotizacion"),
    "encargo": ("customer:pedido", "operator:encargo"),
    "factura": ("customer:factura", "operator:factura"),
    "soporte": ("customer:soporte_detalle", "operator:soporte_detalle"),
}


def de_usuario(usuario, solo_no_leidas=False):
    consulta = Notificacion.objects.filter(usuario=usuario).order_by("-fecha_creacion", "-pk")
    return consulta.filter(leida=False) if solo_no_leidas else consulta


def contar_no_leidas(usuario):
    return Notificacion.objects.filter(usuario=usuario, leida=False).count()


def destino(notificacion, usuario):
    rutas = RUTAS.get(notificacion.tipo)
    if not rutas or not notificacion.referencia_id:
        return None
    return reverse(rutas[1] if usuario.is_staff else rutas[0], args=[notificacion.referencia_id])
