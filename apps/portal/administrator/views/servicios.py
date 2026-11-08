from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from apps.catalogo.forms.catalogo import CategoriaForm, ServicioForm
from apps.catalogo.models import CategoriaServicio, Servicio
from apps.portal.administrator.mixins import FormularioAdminMixin
from apps.portal.mixins import AdministradorRequeridoMixin

URL_SERVICIOS = reverse_lazy("administrator:servicios")


class ServiciosView(AdministradorRequeridoMixin, ListView):
    template_name = "administrator/servicios.html"
    context_object_name = "servicios"
    model = Servicio
    queryset = Servicio.objects.select_related("categoria").order_by("categoria__nombre", "nombre")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["categorias"] = CategoriaServicio.objects.order_by("nombre")
        return contexto


class ServicioCrearView(FormularioAdminMixin, CreateView):
    model = Servicio
    form_class = ServicioForm
    titulo = "Nuevo servicio"
    mensaje_exito = "Servicio creado correctamente."
    success_url = URL_SERVICIOS


class ServicioEditarView(FormularioAdminMixin, UpdateView):
    model = Servicio
    form_class = ServicioForm
    titulo = "Editar servicio"
    mensaje_exito = "Servicio actualizado correctamente."
    success_url = URL_SERVICIOS


class ServicioActivoView(AdministradorRequeridoMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        servicio = get_object_or_404(Servicio, pk=pk)
        servicio.activo = not servicio.activo
        servicio.save(update_fields=["activo", "actualizado_en"])
        messages.success(request, "Servicio activado." if servicio.activo else "Servicio desactivado.")
        return redirect("administrator:servicios")


class CategoriaCrearView(FormularioAdminMixin, CreateView):
    model = CategoriaServicio
    form_class = CategoriaForm
    titulo = "Nueva categoría"
    mensaje_exito = "Categoría creada correctamente."
    success_url = URL_SERVICIOS


class CategoriaEditarView(FormularioAdminMixin, UpdateView):
    model = CategoriaServicio
    form_class = CategoriaForm
    titulo = "Editar categoría"
    mensaje_exito = "Categoría actualizada correctamente."
    success_url = URL_SERVICIOS
