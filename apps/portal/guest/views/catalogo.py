from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, ListView

from apps.catalogo.selectors import catalogo as selectors


class CatalogoView(ListView):
    template_name = "guest/catalogo.html"
    context_object_name = "productos"
    paginate_by = 12

    def get_queryset(self):
        return selectors.productos_publicos(self.request.GET.get("q", "").strip())

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["q"] = self.request.GET.get("q", "").strip()
        return contexto


class ProductoDetalleView(DetailView):
    template_name = "guest/producto_detalle.html"
    context_object_name = "producto"

    def get_object(self, queryset=None):
        return get_object_or_404(selectors.productos_publicos(), pk=self.kwargs["pk"])
