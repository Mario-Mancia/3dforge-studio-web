from django.contrib import messages
from django.shortcuts import redirect, render
from django.views import View

from apps.clientes.forms.clientes import PerfilClienteForm
from apps.clientes.selectors import clientes as selectors
from apps.clientes.services import clientes as servicios
from apps.portal.mixins import ClienteRequeridoMixin


class CuentaView(ClienteRequeridoMixin, View):
    template_name = "customer/cuenta.html"

    def _contexto(self, form, cliente):
        return {"form": form, "cliente": cliente, "actividad": selectors.actividad_reciente(cliente)}

    def get(self, request):
        cliente = servicios.asegurar_cliente(request.user)
        return render(request, self.template_name, self._contexto(PerfilClienteForm(instance=cliente), cliente))

    def post(self, request):
        cliente = servicios.asegurar_cliente(request.user)
        form = PerfilClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            servicios.guardar_perfil(form)
            messages.success(request, "Sus datos se actualizaron correctamente.")
            return redirect("customer:cuenta")
        return render(request, self.template_name, self._contexto(form, cliente))
