from django.views.generic import TemplateView

from apps.portal.mixins import AdministradorRequeridoMixin


class ServiciosView(AdministradorRequeridoMixin, TemplateView):
    template_name = "administrator/servicios.html"
