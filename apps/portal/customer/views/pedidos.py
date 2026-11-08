from django.views.generic import TemplateView

from apps.portal.mixins import ClienteRequeridoMixin


class PedidosView(ClienteRequeridoMixin, TemplateView):
    template_name = "customer/pedidos.html"
