import json

from django.core import mail
from django.test import Client, override_settings
from django.urls import reverse

from allauth.account.models import EmailAddress

from apps.api.tests.base import ApiTestCase
from apps.clientes.models import Cliente
from apps.cotizaciones.tests.utiles import crear_cliente, crear_personal
from apps.usuarios.constants import ESTADO_PENDIENTE, GRUPO_CLIENTE
from apps.usuarios.models import Usuario
from apps.usuarios.tests.utiles import BACKEND, CLAVE, crear_usuario

DATOS = {
    "nombres": "Luis",
    "apellidos": "Pérez",
    "correo": "luis.api@example.com",
    "telefono": "+503 7000-1111",
    "password": "Clave-Segura-123",
    "password2": "Clave-Segura-123",
}


class AutenticacionApiTests(ApiTestCase):
    def test_salud_es_publica(self):
        respuesta = self.get("salud")
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.json()["ok"])

    def test_login_correcto_devuelve_token_y_cliente(self):
        crear_cliente("ana@example.com")
        respuesta = self.client.post(
            reverse("api:login"), json.dumps({"correo": "ANA@example.com", "password": CLAVE}), content_type="application/json"
        )
        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo["tipo"], "Bearer")
        self.assertEqual(cuerpo["cliente"]["correo"], "ana@example.com")
        self.assertEqual(self.get("perfil", cuerpo["token"]).status_code, 200)

    def test_credenciales_incorrectas(self):
        crear_cliente("ana@example.com")
        respuesta = self.client.post(
            reverse("api:login"), json.dumps({"correo": "ana@example.com", "password": "otra-clave-1"}), content_type="application/json"
        )
        self.assertEqual(respuesta.status_code, 401)
        self.assertEqual(respuesta.json()["error"]["codigo"], "credenciales_invalidas")

    def test_endpoint_protegido_sin_token_o_con_token_invalido(self):
        self.assertEqual(self.get("perfil").status_code, 401)
        self.assertEqual(self.get("perfil", "a" * 32).status_code, 401)
        self.assertEqual(self.get("perfil", "no-es-un-token!").status_code, 401)

    def test_el_personal_no_entra_a_la_app_de_clientes(self):
        crear_personal("operador@example.com")
        respuesta = self.client.post(
            reverse("api:login"), json.dumps({"correo": "operador@example.com", "password": CLAVE}), content_type="application/json"
        )
        self.assertEqual(respuesta.status_code, 403)

    def test_cuenta_pendiente_no_entra(self):
        crear_usuario("pendiente@example.com", GRUPO_CLIENTE, estado_id=ESTADO_PENDIENTE)
        respuesta = self.client.post(
            reverse("api:login"), json.dumps({"correo": "pendiente@example.com", "password": CLAVE}), content_type="application/json"
        )
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.json()["error"]["codigo"], "correo_no_confirmado")

    def test_tipo_de_contenido_incorrecto(self):
        respuesta = self.client.post(reverse("api:login"), {"correo": "a@b.com", "password": "x"})
        self.assertEqual(respuesta.status_code, 415)

    def test_logout_invalida_el_token(self):
        crear_cliente("ana@example.com")
        token = self.token_de("ana@example.com")
        self.assertEqual(self.post("logout", token).status_code, 200)
        self.assertEqual(self.get("perfil", token).status_code, 401)

    def test_refrescar_entrega_otro_token_y_cierra_el_anterior(self):
        crear_cliente("ana@example.com")
        viejo = self.token_de("ana@example.com")
        nuevo = self.post("refrescar", viejo).json()["token"]
        self.assertNotEqual(viejo, nuevo)
        self.assertEqual(self.get("perfil", viejo).status_code, 401)
        self.assertEqual(self.get("perfil", nuevo).status_code, 200)

    def test_cambiar_password_cierra_las_otras_sesiones_y_conserva_la_actual(self):
        crear_cliente("ana@example.com")
        actual, otro = self.token_de("ana@example.com"), self.token_de("ana@example.com")
        erronea = self.post("cambiar_password", actual, datos={"password_actual": "mala", "password_nueva": "Nueva-Clave-456"})
        self.assertEqual(erronea.status_code, 400)
        debil = self.post("cambiar_password", actual, datos={"password_actual": CLAVE, "password_nueva": "123"})
        self.assertEqual(debil.status_code, 400)
        ok = self.post("cambiar_password", actual, datos={"password_actual": CLAVE, "password_nueva": "Nueva-Clave-456"})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(self.get("perfil", actual).status_code, 200)
        self.assertEqual(self.get("perfil", otro).status_code, 401)
        self.assertTrue(self.token_de("ana@example.com", "Nueva-Clave-456"))

    def test_iniciar_sesion_en_la_web_no_cierra_el_token_de_la_app(self):
        usuario, _ = crear_cliente("web@example.com")
        token = self.token_de("web@example.com")
        Client().force_login(usuario, backend=BACKEND)
        self.assertEqual(self.get("perfil", token).status_code, 200)

    def test_sesion_unica_de_la_app_es_configurable(self):
        crear_cliente("ana@example.com")
        with override_settings(API_SESION_UNICA=True):
            primero = self.token_de("ana@example.com")
            segundo = self.token_de("ana@example.com")
        self.assertEqual(self.get("perfil", primero).status_code, 401)
        self.assertEqual(self.get("perfil", segundo).status_code, 200)

    def test_bloqueo_por_intentos_fallidos(self):
        crear_cliente("lock@example.com")
        estados = [
            self.client.post(
                reverse("api:login"), json.dumps({"correo": "lock@example.com", "password": "mala-clave-1"}), content_type="application/json"
            ).status_code
            for _ in range(6)
        ]
        self.assertEqual(estados[0], 401)
        self.assertEqual(estados[-1], 429)
        correcta = self.client.post(
            reverse("api:login"), json.dumps({"correo": "lock@example.com", "password": CLAVE}), content_type="application/json"
        )
        self.assertEqual(correcta.status_code, 429)


class RegistroApiTests(ApiTestCase):
    def registrar(self, **cambios):
        return self.client.post(reverse("api:registro"), json.dumps({**DATOS, **cambios}), content_type="application/json")

    def test_registro_crea_cuenta_pendiente_con_perfil_y_correo(self):
        respuesta = self.registrar()
        self.assertEqual(respuesta.status_code, 201)
        usuario = Usuario.objects.get(correo=DATOS["correo"])
        self.assertEqual(usuario.estado_id, ESTADO_PENDIENTE)
        self.assertTrue(usuario.groups.filter(name=GRUPO_CLIENTE).exists())
        self.assertEqual(Cliente.objects.filter(usuario=usuario).count(), 1)
        self.assertTrue(EmailAddress.objects.filter(user=usuario, verified=False).exists())
        self.assertEqual(len(mail.outbox), 1)

    def test_correo_repetido_no_duplica_ni_revela_nada(self):
        self.registrar()
        respuesta = self.registrar()
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(Usuario.objects.filter(correo=DATOS["correo"]).count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_validaciones_del_registro(self):
        malos = self.registrar(nombres="Luis123", password="123", correo="no-es-correo")
        self.assertEqual(malos.status_code, 400)
        campos = malos.json()["error"]["campos"]
        self.assertIn("nombres", campos)
        self.assertIn("correo", campos)
        debil = self.registrar(password="123", password2="123")
        self.assertEqual(debil.status_code, 400)
        self.assertIn("password", debil.json()["error"]["campos"])
        distintas = self.registrar(password2="otra-distinta")
        self.assertIn("password2", distintas.json()["error"]["campos"])

    def test_registro_y_recuperacion_tienen_limite_por_ip(self):
        for indice in range(10):
            self.registrar(correo=f"u{indice}.api@example.com")
        self.assertEqual(self.registrar(correo="exceso.api@example.com").status_code, 429)

    def test_recuperar_password_siempre_responde_igual(self):
        crear_cliente("ana@example.com")
        existente = self.client.post(reverse("api:recuperar"), json.dumps({"correo": "ana@example.com"}), content_type="application/json")
        inexistente = self.client.post(reverse("api:recuperar"), json.dumps({"correo": "nadie@example.com"}), content_type="application/json")
        self.assertEqual((existente.status_code, inexistente.status_code), (200, 200))
        self.assertEqual(existente.json(), inexistente.json())
