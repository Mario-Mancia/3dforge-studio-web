from django.views.generic import TemplateView

from apps.portal.mixins import AdministradorRequeridoMixin


class UsuariosView(AdministradorRequeridoMixin, TemplateView):
    template_name = "administrator/usuarios.html"
