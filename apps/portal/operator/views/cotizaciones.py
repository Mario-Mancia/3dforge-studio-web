from django.views.generic import TemplateView

from apps.portal.mixins import OperadorRequeridoMixin


class CotizacionesView(OperadorRequeridoMixin, TemplateView):
    template_name = "operator/cotizaciones.html"
