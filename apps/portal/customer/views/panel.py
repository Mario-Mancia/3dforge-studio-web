from django.views.generic import TemplateView

from apps.clientes.services.clientes import asegurar_cliente
from apps.portal.mixins import ClienteRequeridoMixin
from apps.reportes.selectors.panel_cliente import resumen_cliente


class PanelView(ClienteRequeridoMixin, TemplateView):
    template_name = "customer/panel.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        cliente = asegurar_cliente(self.request.user)
        contexto["cliente"] = cliente
        contexto.update(resumen_cliente(cliente, self.request.user))
        return contexto
