from django.views.generic import TemplateView

from apps.portal.mixins import OperadorRequeridoMixin
from apps.reportes.selectors import reportes as selectors


class PanelView(OperadorRequeridoMixin, TemplateView):
    template_name = "operator/panel.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(selectors.datos_operador())
        contexto["trabajo"] = selectors.trabajo_operador(self.request.user)
        return contexto
