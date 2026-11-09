from django.test import TestCase
from django.urls import reverse

from apps.catalogo.models import Producto
from apps.clientes.services.clientes import asegurar_cliente
from apps.usuarios.constants import GRUPO_ADMINISTRADOR, GRUPO_CLIENTE, GRUPO_OPERADOR
from apps.usuarios.tests.utiles import crear_usuario, iniciar_sesion


class ValidacionAjaxTests(TestCase):
    def validar(self, clave, **datos):
        return self.client.post(reverse("validar_campo", args=[clave]), datos)

    def test_requiere_sesion(self):
        self.assertEqual(self.validar("perfil", campo="telefono", telefono="abc").status_code, 302)

    def test_cliente_valida_su_perfil(self):
        usuario = crear_usuario("cliente@example.com", GRUPO_CLIENTE)
        asegurar_cliente(usuario)
        iniciar_sesion(self.client, usuario)
        malo = self.validar("perfil", campo="telefono", tipo_cliente="PERSONA", nombres="Ana", apellidos="Gómez", telefono="abc")
        self.assertFalse(malo.json()["valido"])
        self.assertTrue(malo.json()["errores"])
        bueno = self.validar("perfil", campo="telefono", tipo_cliente="PERSONA", nombres="Ana", apellidos="Gómez", telefono="+503 7000-1111")
        self.assertTrue(bueno.json()["valido"])

    def test_cada_rol_solo_valida_sus_formularios(self):
        iniciar_sesion(self.client, crear_usuario("op@example.com", GRUPO_OPERADOR, is_staff=True))
        self.assertEqual(self.validar("perfil", campo="telefono").status_code, 403)
        self.assertEqual(self.validar("producto", campo="sku").status_code, 403)
        self.assertEqual(self.validar("inexistente", campo="x").status_code, 404)

    def test_administrador_detecta_sku_duplicado_y_lo_excluye_al_editar(self):
        existente = Producto.objects.create(sku="DUP-001", nombre="Uno", precio="1.00")
        iniciar_sesion(self.client, crear_usuario("adm@example.com", GRUPO_ADMINISTRADOR, is_staff=True))
        datos = {"campo": "sku", "sku": "dup-001", "nombre": "Otro", "precio": "2.00", "stock": "1", "stock_minimo": "0"}
        self.assertFalse(self.client.post(reverse("validar_campo", args=["producto"]), datos).json()["valido"])
        self.assertTrue(self.client.post(reverse("validar_campo", args=["producto"]), {**datos, "pk": existente.pk}).json()["valido"])

    def test_campo_desconocido_no_da_error(self):
        iniciar_sesion(self.client, crear_usuario("adm2@example.com", GRUPO_ADMINISTRADOR, is_staff=True))
        respuesta = self.validar("categoria", campo="inventado", nombre="x")
        self.assertTrue(respuesta.json()["valido"])
