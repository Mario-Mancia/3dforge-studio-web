import json
import time
from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.test import override_settings
from django.urls import reverse

from apps.api.respuestas import ErrorAPI
from apps.api.tests.base import ApiTestCase
from apps.clientes.models import Cliente
from apps.cotizaciones.tests.utiles import crear_cliente, crear_personal
from apps.usuarios.constants import ESTADO_ACTIVO, ESTADO_PENDIENTE, GRUPO_CLIENTE
from apps.usuarios.models import Usuario
from apps.usuarios.tests.utiles import crear_usuario

CLIENTE_WEB = "cliente-web.apps.googleusercontent.com"
AJUSTES = {"google": {"APP": {"client_id": CLIENTE_WEB, "secret": "x", "key": ""}}}


def datos_google(**cambios):
    datos = {
        "aud": CLIENTE_WEB, "iss": "https://accounts.google.com", "exp": str(int(time.time()) + 600),
        "email": "nueva.google@gmail.com", "email_verified": "true", "given_name": "Marta", "family_name": "Lopez",
    }
    datos.update(cambios)
    return datos


@override_settings(SOCIALACCOUNT_PROVIDERS=AJUSTES)
class LoginGoogleApiTests(ApiTestCase):
    def entrar(self, datos=None, cuerpo=None):
        with patch("apps.api.vistas.google._consultar_google", return_value=datos or datos_google()):
            return self.client.post(
                reverse("api:login_google"), json.dumps(cuerpo or {"id_token": "token-de-prueba"}), content_type="application/json"
            )

    def test_cuenta_nueva_se_crea_activa_con_perfil_y_token(self):
        respuesta = self.entrar()
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        cuerpo = respuesta.json()
        usuario = Usuario.objects.get(correo="nueva.google@gmail.com")
        self.assertEqual(usuario.estado_id, ESTADO_ACTIVO)
        self.assertFalse(usuario.has_usable_password())
        self.assertTrue(usuario.groups.filter(name=GRUPO_CLIENTE).exists())
        self.assertEqual(Cliente.objects.filter(usuario=usuario).count(), 1)
        self.assertTrue(EmailAddress.objects.filter(user=usuario, verified=True).exists())
        self.assertEqual(cuerpo["usuario"]["nombres"], "Marta")
        self.assertEqual(self.get("perfil", cuerpo["token"]).status_code, 200)

    def test_cuenta_existente_entra_sin_duplicarse(self):
        crear_cliente("ana@example.com")
        self.entrar(datos_google(email="ANA@example.com"))
        self.entrar(datos_google(email="ana@example.com"))
        self.assertEqual(Usuario.objects.filter(correo__iexact="ana@example.com").count(), 1)

    def test_cuenta_pendiente_se_activa_porque_google_verifico_el_correo(self):
        crear_usuario("pendiente@example.com", GRUPO_CLIENTE, estado_id=ESTADO_PENDIENTE)
        respuesta = self.entrar(datos_google(email="pendiente@example.com"))
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(Usuario.objects.get(correo="pendiente@example.com").estado_id, ESTADO_ACTIVO)

    def test_el_personal_no_entra(self):
        crear_personal("operador@example.com")
        self.assertEqual(self.entrar(datos_google(email="operador@example.com")).status_code, 403)

    def test_credenciales_de_google_invalidas_se_rechazan(self):
        for cambios in ({"aud": "otro-cliente"}, {"iss": "https://falso.example"}, {"email_verified": "false"}, {"exp": "1"}, {"email": ""}):
            respuesta = self.entrar(datos_google(**cambios))
            self.assertEqual(respuesta.status_code, 401, (cambios, respuesta.content))
        self.assertFalse(Usuario.objects.filter(correo="nueva.google@gmail.com").exists())

    def test_nonce_debe_coincidir_si_se_envia(self):
        import hashlib

        bueno = datos_google(nonce=hashlib.sha256(b"crudo-123").hexdigest())
        self.assertEqual(self.entrar(bueno, {"id_token": "t", "nonce": "crudo-123"}).status_code, 200)
        self.assertEqual(self.entrar(bueno, {"id_token": "t", "nonce": "otro"}).status_code, 401)

    def test_sin_credencial_o_con_google_caido(self):
        self.assertEqual(self.client.post(reverse("api:login_google"), "{}", content_type="application/json").status_code, 400)
        with patch("apps.api.vistas.google._consultar_google", side_effect=ErrorAPI("caído", "google_no_disponible", 503)):
            caido = self.client.post(reverse("api:login_google"), json.dumps({"id_token": "t"}), content_type="application/json")
        self.assertEqual(caido.status_code, 503)

    @override_settings(SOCIALACCOUNT_PROVIDERS={"google": {"APP": {"client_id": "", "secret": "", "key": ""}}})
    def test_sin_configuracion_del_servidor(self):
        self.assertEqual(self.entrar().status_code, 503)
