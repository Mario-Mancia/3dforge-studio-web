from django.views.generic import TemplateView

from apps.portal.mixins import ClienteRequeridoMixin


class CotizarView(ClienteRequeridoMixin, TemplateView):
    template_name = "customer/cotizar.html"
