from django.views.generic import TemplateView

from apps.portal.mixins import AdministradorRequeridoMixin
from apps.reportes.selectors import reportes as selectors


class DashboardView(AdministradorRequeridoMixin, TemplateView):
    template_name = "administrator/dashboard.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        datos = selectors.datos_admin(self.request.GET.get("rango", "6m"))
        contexto.update(datos)
        contexto["rangos"] = list(selectors.RANGOS.items())
        return contexto
