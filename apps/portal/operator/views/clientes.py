from django.views.generic import TemplateView

from apps.portal.mixins import OperadorRequeridoMixin


class ClientesView(OperadorRequeridoMixin, TemplateView):
    template_name = "operator/clientes.html"
