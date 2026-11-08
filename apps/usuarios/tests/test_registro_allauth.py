from allauth.account.models import EmailAddress
from allauth.account.signals import email_confirmed
from axes.utils import reset
from django.conf import settings
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from apps.clientes.models import Cliente
from apps.usuarios.constants import ESTADO_ACTIVO, ESTADO_PENDIENTE, GRUPO_CLIENTE, GRUPO_OPERADOR
from apps.usuarios.models import Usuario
from apps.usuarios.tests.utiles import crear_usuario

DATOS = {
    "nombres": "Luis",
    "apellidos": "Pérez",
    "email": "luis@example.com",
    "telefono": "",
    "password1": "Clave-Segura-123",
    "password2": "Clave-Segura-123",
}


class RegistroAllauthTests(TestCase):
    def test_registro_crea_usuario_pendiente_con_rol_cliente_y_perfil(self):
        respuesta = self.client.post(reverse("account_signup"), DATOS)
        self.assertEqual(respuesta.status_code, 302)
        usuario = Usuario.objects.get(correo="luis@example.com")
        self.assertEqual(usuario.estado_id, ESTADO_PENDIENTE)
        self.assertTrue(usuario.groups.filter(name=GRUPO_CLIENTE).exists())
        self.assertFalse(usuario.groups.filter(name=GRUPO_OPERADOR).exists())
        self.assertFalse(usuario.is_staff)
        self.assertEqual(Cliente.objects.filter(usuario=usuario).count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_confirmar_el_correo_activa_la_cuenta(self):
        self.client.post(reverse("account_signup"), DATOS)
        usuario = Usuario.objects.get(correo="luis@example.com")
        direccion = EmailAddress.objects.get(user=usuario)
        email_confirmed.send(sender=EmailAddress, request=None, email_address=direccion)
        usuario.refresh_from_db()
        self.assertEqual(usuario.estado_id, ESTADO_ACTIVO)

    def test_correo_repetido_no_crea_otra_cuenta(self):
        self.client.post(reverse("account_signup"), DATOS)
        self.client.post(reverse("account_signup"), DATOS)
        self.assertEqual(Usuario.objects.filter(correo="luis@example.com").count(), 1)
        self.assertEqual(Cliente.objects.count(), 1)


class BloqueoAxesTests(TestCase):
    def test_bloqueo_por_intentos_fallidos_y_recuperacion(self):
        crear_usuario("axes@example.com", GRUPO_CLIENTE)
        datos = {"login": "axes@example.com", "password": "incorrecta"}
        for _ in range(settings.AXES_FAILURE_LIMIT + 1):
            respuesta = self.client.post(reverse("account_login"), datos)
        self.assertIn(respuesta.status_code, (403, 429))
        reset(username="axes@example.com")
        respuesta = self.client.post(reverse("account_login"), datos)
        self.assertNotIn(respuesta.status_code, (403, 429))
