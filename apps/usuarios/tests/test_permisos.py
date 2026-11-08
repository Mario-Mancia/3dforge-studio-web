from django.test import TestCase
from django.urls import reverse

from apps.usuarios.constants import (
    ESTADO_ACTIVO,
    ESTADO_SUSPENDIDO,
    GRUPO_ADMINISTRADOR,
    GRUPO_CLIENTE,
    GRUPO_OPERADOR,
)
from apps.usuarios.tests.utiles import crear_usuario, iniciar_sesion


class PermisosPorRolTests(TestCase):
    def setUp(self):
        self.cliente_u = crear_usuario("cliente@example.com", GRUPO_CLIENTE)
        self.operador_u = crear_usuario("operador@example.com", GRUPO_OPERADOR, is_staff=True)
        self.admin_u = crear_usuario("admin@example.com", GRUPO_ADMINISTRADOR, is_staff=True)

    def _codigo(self, usuario, nombre):
        if usuario is not None:
            iniciar_sesion(self.client, usuario)
        return self.client.get(reverse(nombre)).status_code

    def test_anonimo_es_redirigido_al_acceso(self):
        respuesta = self.client.get(reverse("customer:panel"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("guest:acceso"), respuesta.url)

    def test_cliente_solo_accede_a_su_area(self):
        self.assertEqual(self._codigo(self.cliente_u, "customer:panel"), 200)
        self.assertEqual(self._codigo(None, "operator:panel"), 403)
        self.assertEqual(self._codigo(None, "administrator:dashboard"), 403)
        self.assertEqual(self._codigo(None, "administrator:inventario"), 403)

    def test_operador_no_ejecuta_funciones_de_administrador(self):
        self.assertEqual(self._codigo(self.operador_u, "operator:panel"), 200)
        self.assertEqual(self._codigo(None, "administrator:dashboard"), 403)
        self.assertEqual(self._codigo(None, "administrator:producto_crear"), 403)
        self.assertEqual(self._codigo(None, "customer:panel"), 403)

    def test_administrador_accede_a_su_area(self):
        self.assertEqual(self._codigo(self.admin_u, "administrator:dashboard"), 200)
        self.assertEqual(self._codigo(None, "administrator:inventario"), 200)
        self.assertEqual(self._codigo(None, "administrator:servicios"), 200)

    def test_redireccion_posterior_al_login_segun_rol(self):
        esperados = {
            self.cliente_u: reverse("customer:panel"),
            self.operador_u: reverse("operator:panel"),
            self.admin_u: reverse("administrator:dashboard"),
        }
        for usuario, destino in esperados.items():
            self.client.logout()
            iniciar_sesion(self.client, usuario)
            self.assertRedirects(
                self.client.get(reverse("redirigir")), destino, fetch_redirect_response=False
            )


class EstadoUsuarioTests(TestCase):
    def test_suspender_desactiva_y_reactivar_activa(self):
        usuario = crear_usuario("estado@example.com", GRUPO_CLIENTE)
        usuario.estado_id = ESTADO_SUSPENDIDO
        usuario.save()
        usuario.refresh_from_db()
        self.assertFalse(usuario.is_active)
        usuario.estado_id = ESTADO_ACTIVO
        usuario.save()
        usuario.refresh_from_db()
        self.assertTrue(usuario.is_active)

    def test_usuario_suspendido_pierde_acceso(self):
        usuario = crear_usuario("suspendido@example.com", GRUPO_CLIENTE)
        usuario.estado_id = ESTADO_SUSPENDIDO
        usuario.save()
        self.assertFalse(usuario.tiene_algun_rol((GRUPO_CLIENTE,)))
