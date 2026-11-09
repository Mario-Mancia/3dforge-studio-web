from django.views import View
from django.views.generic import ListView

from apps.portal.mixins import OperadorRequeridoMixin
from apps.portal.notificaciones import AccionNotificacionMixin, ListaNotificacionesMixin


class NotificacionesOperadorView(OperadorRequeridoMixin, ListaNotificacionesMixin, ListView):
    template_name = "operator/notificaciones.html"
    ruta_accion = "operator:notificacion_accion"


class NotificacionAccionOperadorView(OperadorRequeridoMixin, AccionNotificacionMixin, View):
    destino = "operator:notificaciones"
