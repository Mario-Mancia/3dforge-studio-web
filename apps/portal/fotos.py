from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.views import View

from apps.core.utiles import mensaje_de
from apps.portal.mixins import ClienteRequeridoMixin, OperadorRequeridoMixin
from apps.usuarios.forms.foto import FotoPerfilForm
from apps.usuarios.models import Usuario
from apps.usuarios.services.fotos import guardar_foto, quitar_foto


class FotoPerfilBase(View):
    """Sube o quita la foto de perfil del usuario autenticado y vuelve a su pagina de perfil."""

    http_method_names = ["post"]

    def destino(self, request):
        return request.resolver_match.view_name.removesuffix("_foto")

    def post(self, request):
        formulario = FotoPerfilForm(request.POST, request.FILES)
        if not formulario.is_valid():
            errores = [error for lista in formulario.errors.values() for error in lista]
            messages.error(request, " ".join(errores) or "No se pudo procesar la imagen.")
            return redirect(self.destino(request))
        usuario = Usuario.objects.get(pk=request.user.pk)
        try:
            if formulario.cleaned_data["quitar"]:
                quitar_foto(usuario)
                messages.success(request, "Su foto de perfil se eliminó.")
            elif formulario.cleaned_data["foto"]:
                guardar_foto(usuario, formulario.cleaned_data["foto"])
                messages.success(request, "Su foto de perfil se actualizó.")
            else:
                messages.error(request, "Seleccione una imagen.")
        except ValidationError as error:
            messages.error(request, mensaje_de(error))
        return redirect(self.destino(request))


class FotoPerfilClienteView(ClienteRequeridoMixin, FotoPerfilBase):
    pass


class FotoPerfilPersonalView(OperadorRequeridoMixin, FotoPerfilBase):
    pass
