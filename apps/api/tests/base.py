import json

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from apps.usuarios.tests.utiles import CLAVE


class ApiTestCase(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def cabecera(self, token):
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}

    def token_de(self, correo, clave=CLAVE):
        respuesta = self.client.post(
            reverse("api:login"), json.dumps({"correo": correo, "password": clave}), content_type="application/json"
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        return respuesta.json()["token"]

    def get(self, nombre, token=None, args=(), params=None):
        return self.client.get(reverse(f"api:{nombre}", args=args), params or {}, **self.cabecera(token))

    def enviar(self, metodo, nombre, token=None, args=(), datos=None):
        return getattr(self.client, metodo)(
            reverse(f"api:{nombre}", args=args),
            json.dumps({} if datos is None else datos),
            content_type="application/json",
            **self.cabecera(token),
        )

    def post(self, nombre, token=None, args=(), datos=None):
        return self.enviar("post", nombre, token, args, datos)
