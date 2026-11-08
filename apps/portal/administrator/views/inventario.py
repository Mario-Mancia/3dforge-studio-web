from django.views.generic import TemplateView

from apps.portal.mixins import AdministradorRequeridoMixin


class InventarioView(AdministradorRequeridoMixin, TemplateView):
    template_name = "administrator/inventario.html"
