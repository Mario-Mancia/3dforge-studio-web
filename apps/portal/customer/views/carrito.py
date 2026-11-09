from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View

from apps.clientes.services.clientes import asegurar_cliente
from apps.encargos.services import compras
from apps.portal.mixins import ClienteRequeridoMixin


class CarritoAgregarView(ClienteRequeridoMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        try:
            compras.Carrito(request.session).agregar(pk, request.POST.get("cantidad", "1"))
        except compras.ErrorCompra as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "Producto agregado al carrito.")
        siguiente = request.POST.get("siguiente", "")
        if siguiente and url_has_allowed_host_and_scheme(siguiente, {request.get_host()}, request.is_secure()):
            return redirect(siguiente)
        return redirect("customer:tienda")


class CarritoView(ClienteRequeridoMixin, View):
    template_name = "customer/carrito.html"

    def get(self, request):
        carrito = compras.Carrito(request.session)
        contexto = {"lineas": carrito.lineas(), "totales": carrito.totales(), "problemas": carrito.hay_problemas()}
        return render(request, self.template_name, contexto)

    def post(self, request):
        carrito = compras.Carrito(request.session)
        accion = request.POST.get("accion", "")
        try:
            if accion == "actualizar":
                carrito.actualizar(request.POST.get("producto", ""), request.POST.get("cantidad", ""))
                messages.success(request, "Carrito actualizado.")
            elif accion == "quitar":
                carrito.quitar(request.POST.get("producto", ""))
                messages.success(request, "Producto eliminado.")
            elif accion == "vaciar":
                carrito.vaciar()
                messages.success(request, "Carrito vacío.")
            else:
                messages.error(request, "Acción no válida.")
        except compras.ErrorCompra as error:
            messages.error(request, str(error))
        return redirect("customer:carrito")


class CheckoutView(ClienteRequeridoMixin, View):
    template_name = "customer/checkout.html"

    def get(self, request):
        try:
            token = compras.iniciar_checkout(request.session)
        except compras.ErrorCompra as error:
            messages.error(request, str(error))
            return redirect("customer:carrito")
        carrito = compras.Carrito(request.session)
        contexto = {"lineas": carrito.lineas(), "totales": carrito.totales(), "token": token}
        return render(request, self.template_name, contexto)

    def post(self, request):
        try:
            encargo = compras.confirmar_compra(
                asegurar_cliente(request.user), request.user, request.session, request.POST.get("token", "")
            )
        except compras.CompraDuplicada as duplicada:
            messages.info(request, "Su compra ya fue procesada.")
            if duplicada.encargo_id:
                return redirect("customer:pedido", pk=duplicada.encargo_id)
            return redirect("customer:pedidos")
        except compras.ErrorCompra as error:
            messages.error(request, str(error))
            return redirect("customer:carrito")
        messages.success(request, f"Compra confirmada: pedido {encargo.codigo}.")
        return redirect("customer:pedido", pk=encargo.pk)
