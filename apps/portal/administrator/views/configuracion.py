from django.views.generic import TemplateView

from apps.portal.mixins import AdministradorRequeridoMixin


class ConfiguracionView(AdministradorRequeridoMixin, TemplateView):
    template_name = "administrator/configuracion.html"
