from django.views.generic import TemplateView

from apps.portal.mixins import ClienteRequeridoMixin


class TiendaView(ClienteRequeridoMixin, TemplateView):
    template_name = "customer/tienda.html"
