from django.http import Http404
from django.shortcuts import render
from django.views import View
from django.views.generic import ListView

from apps.clientes.services.clientes import asegurar_cliente
from apps.facturacion.selectors import facturacion as selectors
from apps.portal.mixins import ClienteRequeridoMixin


class FacturasClienteView(ClienteRequeridoMixin, ListView):
    template_name = "customer/facturas.html"
    context_object_name = "facturas"
    paginate_by = 10

    def get_queryset(self):
        return selectors.facturas_del_cliente(asegurar_cliente(self.request.user))


class FacturaClienteView(ClienteRequeridoMixin, View):
    template_name = "customer/factura_detalle.html"

    def get(self, request, pk):
        factura = selectors.obtener_del_cliente(asegurar_cliente(request.user), pk)
        if factura is None:
            raise Http404
        return render(request, self.template_name, {"factura": factura})
