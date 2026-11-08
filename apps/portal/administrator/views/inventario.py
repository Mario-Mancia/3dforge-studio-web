from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from apps.catalogo.forms.catalogo import AjusteStockForm, ProductoForm
from apps.catalogo.models import Producto
from apps.catalogo.selectors import catalogo as selectors
from apps.catalogo.services import catalogo as servicio_catalogo
from apps.portal.administrator.mixins import FormularioAdminMixin
from apps.portal.mixins import AdministradorRequeridoMixin


class InventarioView(AdministradorRequeridoMixin, ListView):
    template_name = "administrator/inventario.html"
    context_object_name = "productos"
    paginate_by = 20

    def get_queryset(self):
        return selectors.productos_admin(
            self.request.GET.get("q", "").strip(),
            solo_bajo_stock=bool(self.request.GET.get("bajo")),
        )

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["q"] = self.request.GET.get("q", "").strip()
        contexto["bajo"] = bool(self.request.GET.get("bajo"))
        return contexto


class ProductoCrearView(FormularioAdminMixin, CreateView):
    model = Producto
    form_class = ProductoForm
    titulo = "Nuevo producto"
    mensaje_exito = "Producto creado correctamente."
    success_url = reverse_lazy("administrator:inventario")


class ProductoEditarView(FormularioAdminMixin, UpdateView):
    model = Producto
    form_class = ProductoForm
    titulo = "Editar producto"
    mensaje_exito = "Producto actualizado correctamente."
    success_url = reverse_lazy("administrator:inventario")


class ProductoActivoView(AdministradorRequeridoMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        producto = get_object_or_404(Producto, pk=pk)
        producto.activo = not producto.activo
        producto.save(update_fields=["activo", "actualizado_en"])
        messages.success(request, "Producto activado." if producto.activo else "Producto desactivado.")
        return redirect("administrator:inventario")


class ProductoStockView(AdministradorRequeridoMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        form = AjusteStockForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Ingrese un ajuste de stock válido.")
            return redirect("administrator:inventario")
        try:
            producto = servicio_catalogo.ajustar_stock(pk, form.cleaned_data["delta"])
        except Producto.DoesNotExist:
            raise Http404
        except servicio_catalogo.ErrorInventario as error:
            messages.error(request, str(error))
        else:
            messages.success(request, f"Stock de {producto.nombre}: {producto.stock}.")
        return redirect("administrator:inventario")
