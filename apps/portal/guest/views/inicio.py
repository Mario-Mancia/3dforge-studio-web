from django.views.generic import TemplateView

from apps.catalogo.selectors import catalogo as selectors


class InicioView(TemplateView):
    template_name = "guest/inicio.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["productos"] = selectors.productos_destacados()
        contexto["servicios"] = selectors.servicios_publicos()[:3]
        return contexto
