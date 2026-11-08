from allauth.account.signals import user_signed_up
from django.test import TestCase

from apps.clientes.models import Cliente
from apps.usuarios.constants import GRUPO_CLIENTE, GRUPO_OPERADOR
from apps.usuarios.models import Usuario
from apps.usuarios.tests.utiles import crear_usuario


class RegistroPublicoTests(TestCase):
    def test_registro_crea_cliente_con_rol_customer(self):
        usuario = crear_usuario("nuevo@example.com")
        user_signed_up.send(sender=Usuario, request=None, user=usuario)
        self.assertTrue(usuario.groups.filter(name=GRUPO_CLIENTE).exists())
        self.assertTrue(Cliente.objects.filter(usuario=usuario).exists())

    def test_registro_nunca_asigna_roles_de_empleado(self):
        usuario = crear_usuario("seguro@example.com")
        user_signed_up.send(sender=Usuario, request=None, user=usuario)
        self.assertFalse(usuario.groups.filter(name=GRUPO_OPERADOR).exists())
        self.assertFalse(usuario.is_staff)

    def test_personal_no_se_convierte_en_cliente(self):
        usuario = crear_usuario("staff@example.com", is_staff=True)
        user_signed_up.send(sender=Usuario, request=None, user=usuario)
        self.assertFalse(Cliente.objects.filter(usuario=usuario).exists())
