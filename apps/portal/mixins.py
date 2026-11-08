from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from apps.usuarios.constants import GRUPO_ADMINISTRADOR, GRUPO_CLIENTE, GRUPO_OPERADOR


class RolRequeridoMixin(LoginRequiredMixin, UserPassesTestMixin):
    roles = ()

    def test_func(self):
        usuario = self.request.user
        return usuario.is_authenticated and usuario.tiene_algun_rol(self.roles)


class ClienteRequeridoMixin(RolRequeridoMixin):
    roles = (GRUPO_CLIENTE,)


class OperadorRequeridoMixin(RolRequeridoMixin):
    roles = (GRUPO_OPERADOR, GRUPO_ADMINISTRADOR)


class AdministradorRequeridoMixin(RolRequeridoMixin):
    roles = (GRUPO_ADMINISTRADOR,)
