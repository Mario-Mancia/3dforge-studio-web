from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views import View

from apps.usuarios.selectors.usuarios import destino_por_rol


class RedireccionPorRolView(LoginRequiredMixin, View):
    def get(self, request):
        destino = destino_por_rol(request.user)
        if destino is None:
            logout(request)
            messages.error(request, "Su cuenta no tiene un rol habilitado. Contacte al administrador.")
            return redirect("guest:inicio")
        return redirect(destino)
