from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, ListView

from apps.catalogo.selectors import catalogo as selectors


def _entero(valor):
    return int(valor) if valor and valor.isdigit() else None


class ServiciosView(ListView):
    template_name = "guest/servicios.html"
    context_object_name = "servicios"

    def get_queryset(self):
        return selectors.servicios_publicos(_entero(self.request.GET.get("categoria")))

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["categorias"] = selectors.categorias_publicas()
        contexto["categoria_actual"] = _entero(self.request.GET.get("categoria"))
        return contexto


class ServicioDetalleView(DetailView):
    template_name = "guest/servicio_detalle.html"
    context_object_name = "servicio"

    def get_object(self, queryset=None):
        return get_object_or_404(selectors.servicios_publicos(), pk=self.kwargs["pk"])
