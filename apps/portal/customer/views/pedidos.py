from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import ListView

from apps.clientes.services.clientes import asegurar_cliente
from apps.core.archivos import respuesta_descarga
from apps.core.storage import almacenamiento_privado
from apps.encargos.selectors import encargos as selectors
from apps.encargos.services import encargos as servicios
from apps.portal.mixins import ClienteRequeridoMixin


class PedidosView(ClienteRequeridoMixin, ListView):
    template_name = "customer/pedidos.html"
    context_object_name = "encargos"
    paginate_by = 10

    def get_queryset(self):
        return selectors.encargos_del_cliente(asegurar_cliente(self.request.user))


class PedidoDetalleView(ClienteRequeridoMixin, View):
    template_name = "customer/pedido_detalle.html"

    def get(self, request, pk):
        encargo = selectors.obtener_del_cliente(asegurar_cliente(request.user), pk)
        if encargo is None:
            raise Http404
        return render(request, self.template_name, {"encargo": encargo})


class PedidoCancelarView(ClienteRequeridoMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        encargo = selectors.obtener_del_cliente(asegurar_cliente(request.user), pk)
        if encargo is None:
            raise Http404
        try:
            servicios.cancelar_por_cliente(encargo.pk, request.user)
        except servicios.ErrorEncargo as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "Pedido cancelado.")
        return redirect("customer:pedido", pk=pk)


class PedidoArchivoView(ClienteRequeridoMixin, View):
    def get(self, request, pk, archivo_id):
        encargo = selectors.obtener_del_cliente(asegurar_cliente(request.user), pk)
        if encargo is None:
            raise Http404
        archivo = next((a for d in encargo.detalles.all() for a in d.archivos.all() if a.pk == archivo_id), None)
        if archivo is None:
            raise Http404
        return respuesta_descarga(almacenamiento_privado, archivo.ruta_archivo, archivo.nombre_archivo)
