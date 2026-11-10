from django.contrib import messages
from django.shortcuts import redirect, render
from django.views import View

from apps.portal.mixins import OperadorRequeridoMixin
from apps.usuarios.forms.perfil import PerfilPersonalForm
from apps.usuarios.models import Usuario
from apps.usuarios.models.empleado import Empleado

ETIQUETAS_ROL = {"Operator": "Operador", "Administrator": "Administrador", "Customer": "Cliente"}


class CuentaPersonalView(OperadorRequeridoMixin, View):
    """Mi perfil del personal (operador y administrador): datos de contacto y ficha laboral."""

    template_name = "operator/cuenta.html"

    def _contexto(self, usuario, form):
        roles = [ETIQUETAS_ROL.get(nombre, nombre) for nombre in usuario.groups.values_list("name", flat=True)]
        if usuario.is_superuser:
            roles.append("Superusuario")
        return {
            "form": form,
            "perfil": usuario,
            "roles": roles,
            "empleado": Empleado.objects.filter(usuario=usuario).first(),
        }

    def get(self, request):
        usuario = Usuario.objects.get(pk=request.user.pk)
        return render(request, self.template_name, self._contexto(usuario, PerfilPersonalForm(instance=usuario)))

    def post(self, request):
        usuario = Usuario.objects.get(pk=request.user.pk)
        form = PerfilPersonalForm(request.POST, instance=usuario)
        if form.is_valid():
            form.save()
            messages.success(request, "Sus datos se actualizaron correctamente.")
            return redirect(request.resolver_match.view_name)
        return render(request, self.template_name, self._contexto(usuario, form))
