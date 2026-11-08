from django.test import TestCase

from apps.clientes.forms.clientes import PerfilClienteForm
from apps.clientes.services.clientes import asegurar_cliente, guardar_perfil
from apps.usuarios.constants import GRUPO_CLIENTE
from apps.usuarios.tests.utiles import crear_usuario

PERSONA = {
    "tipo_cliente": "PERSONA",
    "nombres": "Ana",
    "apellidos": "Gómez",
    "nombre_empresa": "",
    "telefono": "+503 7000-1111",
    "identificacion_fiscal": "",
    "direccion": "",
}
EMPRESA = {**PERSONA, "tipo_cliente": "EMPRESA", "nombre_empresa": "Taller Uno"}


class TiposClienteTests(TestCase):
    def setUp(self):
        self.usuario = crear_usuario("tipos@example.com", GRUPO_CLIENTE)
        self.cliente = asegurar_cliente(self.usuario)

    def formulario(self, datos):
        return PerfilClienteForm(datos, instance=self.cliente)

    def test_persona_requiere_nombres_y_apellidos(self):
        self.assertFalse(self.formulario({**PERSONA, "nombres": "", "apellidos": ""}).is_valid())

    def test_empresa_requiere_nombre_de_empresa(self):
        self.assertFalse(self.formulario({**EMPRESA, "nombre_empresa": ""}).is_valid())

    def test_cambio_a_empresa_conserva_los_datos_del_usuario(self):
        form = self.formulario({**EMPRESA, "nombres": "Otro", "telefono": "+503 7000-2222"})
        self.assertTrue(form.is_valid(), form.errors)
        guardar_perfil(form)
        self.cliente.refresh_from_db()
        self.usuario.refresh_from_db()
        self.assertEqual(self.cliente.tipo_cliente, "EMPRESA")
        self.assertEqual(self.usuario.nombres, "Ana")
        self.assertNotEqual(self.usuario.telefono, "+503 7000-2222")

    def test_cambio_a_persona_limpia_el_nombre_de_empresa(self):
        form = self.formulario(EMPRESA)
        self.assertTrue(form.is_valid(), form.errors)
        guardar_perfil(form)
        self.cliente.refresh_from_db()
        form = self.formulario({**PERSONA, "nombre_empresa": "Taller Uno"})
        self.assertTrue(form.is_valid(), form.errors)
        guardar_perfil(form)
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.tipo_cliente, "PERSONA")
        self.assertIsNone(self.cliente.nombre_empresa)

    def test_telefono_de_persona_se_sincroniza_con_el_usuario(self):
        form = self.formulario({**PERSONA, "telefono": "+503 7000-3333"})
        self.assertTrue(form.is_valid(), form.errors)
        guardar_perfil(form)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.telefono, "+503 7000-3333")
