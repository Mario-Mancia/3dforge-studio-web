from django.test import TestCase
from django.urls import reverse

from apps.clientes.models import Cliente
from apps.clientes.services.clientes import asegurar_cliente
from apps.usuarios.constants import GRUPO_CLIENTE
from apps.usuarios.tests.utiles import crear_usuario, iniciar_sesion

DATOS = {
    "tipo_cliente": "PERSONA",
    "nombres": "Ana",
    "apellidos": "Nueva",
    "nombre_empresa": "",
    "telefono": "+503 7000-0000",
    "identificacion_fiscal": "",
    "direccion": "",
}


class PerfilClienteTests(TestCase):
    def setUp(self):
        self.a = crear_usuario("a@example.com", GRUPO_CLIENTE)
        self.b = crear_usuario("b@example.com", GRUPO_CLIENTE)
        self.cliente_a = asegurar_cliente(self.a)
        self.cliente_b = asegurar_cliente(self.b)

    def test_cliente_edita_solo_su_propio_perfil(self):
        iniciar_sesion(self.client, self.a)
        respuesta = self.client.post(reverse("customer:cuenta"), DATOS)
        self.assertEqual(respuesta.status_code, 302)
        self.cliente_a.refresh_from_db()
        self.cliente_b.refresh_from_db()
        self.assertEqual(self.cliente_a.apellidos, "Nueva")
        self.assertNotEqual(self.cliente_b.apellidos, "Nueva")

    def test_correo_no_se_puede_modificar_desde_el_perfil(self):
        iniciar_sesion(self.client, self.a)
        self.client.post(reverse("customer:cuenta"), {**DATOS, "correo": "otro@example.com"})
        self.cliente_a.refresh_from_db()
        self.assertEqual(self.cliente_a.correo, "a@example.com")

    def test_telefono_invalido_es_rechazado(self):
        iniciar_sesion(self.client, self.a)
        respuesta = self.client.post(reverse("customer:cuenta"), {**DATOS, "telefono": "abc"})
        self.assertEqual(respuesta.status_code, 200)
        self.cliente_a.refresh_from_db()
        self.assertNotEqual(self.cliente_a.telefono, "abc")

    def test_empresa_exige_nombre_de_empresa(self):
        iniciar_sesion(self.client, self.a)
        respuesta = self.client.post(reverse("customer:cuenta"), {**DATOS, "tipo_cliente": "EMPRESA"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Cliente.objects.filter(usuario=self.a, tipo_cliente="EMPRESA").count(), 0)

    def test_perfil_requiere_sesion(self):
        self.assertEqual(self.client.get(reverse("customer:cuenta")).status_code, 302)
