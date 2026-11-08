from django.views.generic import TemplateView

from apps.portal.mixins import AdministradorRequeridoMixin


class VentasView(AdministradorRequeridoMixin, TemplateView):
    template_name = "administrator/ventas.html"
