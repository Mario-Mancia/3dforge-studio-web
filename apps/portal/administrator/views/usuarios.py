from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import ListView

from apps.core.utiles import mensaje_de
from apps.portal.mixins import AdministradorRequeridoMixin
from apps.usuarios.constants import GRUPOS
from apps.usuarios.forms.usuarios import EmpleadoCrearForm, UsuarioEditarForm
from apps.usuarios.models import EstadoUsuario, Usuario
from apps.usuarios.selectors import usuarios as selectors
from apps.usuarios.services import usuarios as servicios


class UsuariosView(AdministradorRequeridoMixin, ListView):
    template_name = "administrator/usuarios.html"
    context_object_name = "usuarios"
    paginate_by = 20

    def get_queryset(self):
        return selectors.usuarios_para_panel(
            self.request.GET.get("q", "").strip(),
            self.request.GET.get("rol", ""),
            self.request.GET.get("estado", ""),
        )

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["q"] = self.request.GET.get("q", "").strip()
        contexto["rol"] = self.request.GET.get("rol", "")
        contexto["estado"] = self.request.GET.get("estado", "")
        contexto["roles"] = GRUPOS
        contexto["estados"] = EstadoUsuario.objects.all()
        return contexto


class UsuarioCrearView(AdministradorRequeridoMixin, View):
    template_name = "administrator/formulario.html"

    def _responder(self, request, form):
        contexto = {"form": form, "titulo": "Nuevo empleado", "volver": "/administrador/usuarios/"}
        return render(request, self.template_name, contexto)

    def get(self, request):
        return self._responder(request, EmpleadoCrearForm())

    def post(self, request):
        form = EmpleadoCrearForm(request.POST)
        if form.is_valid():
            try:
                usuario = servicios.crear_empleado(**form.datos_servicio())
            except (servicios.ErrorUsuarios, ValidationError) as error:
                form.add_error(None, mensaje_de(error))
            else:
                messages.success(request, f"Empleado {usuario.correo} creado.")
                return redirect("administrator:usuarios")
        return self._responder(request, form)


class UsuarioEditarView(AdministradorRequeridoMixin, View):
    template_name = "administrator/formulario.html"

    def _responder(self, request, form, usuario):
        contexto = {"form": form, "titulo": f"Editar usuario: {usuario.correo}", "volver": "/administrador/usuarios/"}
        return render(request, self.template_name, contexto)

    def get(self, request, pk):
        usuario = get_object_or_404(Usuario, pk=pk)
        return self._responder(request, UsuarioEditarForm(usuario=usuario), usuario)

    def post(self, request, pk):
        usuario = get_object_or_404(Usuario, pk=pk)
        form = UsuarioEditarForm(request.POST, usuario=usuario)
        if form.is_valid():
            try:
                servicios.actualizar_usuario(usuario.pk, request.user, form.cleaned_data)
            except (servicios.ErrorUsuarios, ValidationError) as error:
                form.add_error(None, mensaje_de(error))
            else:
                messages.success(request, "Usuario actualizado.")
                return redirect("administrator:usuarios")
        return self._responder(request, form, usuario)
