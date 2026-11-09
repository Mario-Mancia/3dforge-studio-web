from django.views import View
from django.views.generic import ListView

from apps.portal.mixins import ClienteRequeridoMixin
from apps.portal.notificaciones import AccionNotificacionMixin, ListaNotificacionesMixin


class NotificacionesClienteView(ClienteRequeridoMixin, ListaNotificacionesMixin, ListView):
    template_name = "customer/notificaciones.html"
    ruta_accion = "customer:notificacion_accion"


class NotificacionAccionClienteView(ClienteRequeridoMixin, AccionNotificacionMixin, View):
    destino = "customer:notificaciones"
