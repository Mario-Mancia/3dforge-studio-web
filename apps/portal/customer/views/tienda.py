from django.views.generic import ListView

from apps.catalogo.selectors import catalogo as selectors
from apps.encargos.services.compras import Carrito
from apps.portal.mixins import ClienteRequeridoMixin


class TiendaView(ClienteRequeridoMixin, ListView):
    template_name = "customer/tienda.html"
    context_object_name = "productos"
    paginate_by = 12

    def get_queryset(self):
        return selectors.productos_publicos(self.request.GET.get("q", "").strip())

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["q"] = self.request.GET.get("q", "").strip()
        contexto["unidades"] = Carrito(self.request.session).unidades
        return contexto
