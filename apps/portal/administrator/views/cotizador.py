from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, UpdateView

from apps.cotizaciones.forms.automatica import ConfiguracionCotizadorForm, FilamentoForm
from apps.cotizaciones.models import ConfiguracionCotizador, Filamento
from apps.cotizaciones.selectors.automatica import filamentos_admin
from apps.portal.administrator.mixins import FormularioAdminMixin
from apps.portal.mixins import AdministradorRequeridoMixin

URL_COTIZADOR = reverse_lazy("administrator:cotizador")


class CotizadorView(AdministradorRequeridoMixin, View):
    template_name = "administrator/cotizador.html"

    def _render(self, request, form):
        return render(request, self.template_name, {"form": form, "filamentos": filamentos_admin()})

    def get(self, request):
        return self._render(request, ConfiguracionCotizadorForm(instance=ConfiguracionCotizador.obtener()))

    def post(self, request):
        form = ConfiguracionCotizadorForm(request.POST, instance=ConfiguracionCotizador.obtener())
        if form.is_valid():
            form.save()
            messages.success(request, "Los parámetros del cotizador se guardaron correctamente.")
            return redirect("administrator:cotizador")
        return self._render(request, form)


class FilamentoCrearView(FormularioAdminMixin, CreateView):
    model = Filamento
    form_class = FilamentoForm
    titulo = "Nuevo filamento"
    mensaje_exito = "Filamento creado correctamente."
    success_url = URL_COTIZADOR


class FilamentoEditarView(FormularioAdminMixin, UpdateView):
    model = Filamento
    form_class = FilamentoForm
    titulo = "Editar filamento"
    mensaje_exito = "Filamento actualizado correctamente."
    success_url = URL_COTIZADOR


class FilamentoActivoView(AdministradorRequeridoMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        filamento = get_object_or_404(Filamento, pk=pk)
        filamento.activo = not filamento.activo
        filamento.save(update_fields=["activo", "actualizado_en"])
        messages.success(request, "Filamento activado." if filamento.activo else "Filamento desactivado.")
        return redirect("administrator:cotizador")
