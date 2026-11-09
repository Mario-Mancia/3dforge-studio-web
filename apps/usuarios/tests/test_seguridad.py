from pathlib import Path

from django.conf import settings
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.usuarios.constants import GRUPO_ADMINISTRADOR, GRUPO_CLIENTE, GRUPO_OPERADOR
from apps.usuarios.models import Empleado
from apps.usuarios.tests.utiles import crear_usuario, iniciar_sesion


class BackstackTests(TestCase):
    def test_paginas_privadas_no_se_guardan_en_cache(self):
        usuario = crear_usuario("operador@example.com", GRUPO_OPERADOR, is_staff=True)
        iniciar_sesion(self.client, usuario)
        respuesta = self.client.get(reverse("operator:panel"))
        self.assertIn("no-store", respuesta["Cache-Control"])
        self.assertEqual(respuesta["Pragma"], "no-cache")

    def test_ruta_privada_sin_sesion_tampoco_se_cachea(self):
        respuesta = self.client.get(reverse("customer:panel"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("no-store", respuesta["Cache-Control"])

    def test_pagina_publica_anonima_no_fuerza_no_store(self):
        respuesta = self.client.get(reverse("guest:inicio"))
        self.assertNotIn("no-store", respuesta.get("Cache-Control", ""))

    def test_cerrar_sesion_limpia_cache_y_bloquea_el_acceso(self):
        usuario = crear_usuario("cliente@example.com", GRUPO_CLIENTE)
        iniciar_sesion(self.client, usuario)
        self.assertEqual(self.client.get(reverse("customer:panel")).status_code, 200)
        respuesta = self.client.post(reverse("account_logout"))
        self.assertEqual(respuesta["Clear-Site-Data"], '"cache"')
        self.assertEqual(self.client.get(reverse("customer:panel")).status_code, 302)


class SesionUnicaTests(TestCase):
    def test_un_segundo_inicio_cierra_la_primera_sesion(self):
        usuario = crear_usuario("unica@example.com", GRUPO_CLIENTE)
        primero, segundo = Client(), Client()
        iniciar_sesion(primero, usuario)
        self.assertEqual(primero.get(reverse("customer:panel")).status_code, 200)
        iniciar_sesion(segundo, usuario)
        self.assertEqual(segundo.get(reverse("customer:panel")).status_code, 200)
        self.assertEqual(primero.get(reverse("customer:panel")).status_code, 302)

    @override_settings(SESION_UNICA=False)
    def test_puede_desactivarse(self):
        usuario = crear_usuario("multi@example.com", GRUPO_CLIENTE)
        primero, segundo = Client(), Client()
        iniciar_sesion(primero, usuario)
        iniciar_sesion(segundo, usuario)
        self.assertEqual(primero.get(reverse("customer:panel")).status_code, 200)

    def test_otro_usuario_no_pierde_su_sesion(self):
        a = crear_usuario("a@example.com", GRUPO_CLIENTE)
        b = crear_usuario("b@example.com", GRUPO_CLIENTE)
        cliente_a, cliente_b = Client(), Client()
        iniciar_sesion(cliente_a, a)
        iniciar_sesion(cliente_b, b)
        self.assertEqual(cliente_a.get(reverse("customer:panel")).status_code, 200)


class EmpleadoInactivoTests(TestCase):
    def test_empleado_inactivo_pierde_el_acceso_del_personal(self):
        usuario = crear_usuario("inactivo@example.com", GRUPO_OPERADOR, is_staff=True)
        empleado = Empleado.objects.create(usuario=usuario, codigo_empleado="EMP-900", cargo="Operador")
        iniciar_sesion(self.client, usuario)
        self.assertEqual(self.client.get(reverse("operator:panel")).status_code, 200)
        Empleado.objects.filter(pk=empleado.pk).update(activo=False)
        self.assertEqual(self.client.get(reverse("operator:panel")).status_code, 403)
        respuesta = self.client.get(reverse("redirigir"))
        self.assertRedirects(respuesta, reverse("guest:inicio"), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse("operator:panel")).status_code, 302)

    def test_administrador_inactivo_tampoco_entra(self):
        usuario = crear_usuario("admin.inactivo@example.com", GRUPO_ADMINISTRADOR, is_staff=True)
        Empleado.objects.create(usuario=usuario, codigo_empleado="EMP-901", cargo="Jefe", activo=False)
        iniciar_sesion(self.client, usuario)
        self.assertEqual(self.client.get(reverse("administrator:dashboard")).status_code, 403)


class ScriptsNuevasVistasTests(TestCase):
    def test_existen_los_scripts_de_las_vistas_nuevas(self):
        base = Path(settings.BASE_DIR) / "static" / "js" / "vistas"
        for ruta in (
            "customer/notificaciones", "customer/soporte", "customer/soporte_detalle", "operator/notificaciones",
            "operator/cliente", "operator/soporte", "operator/soporte_detalle",
        ):
            self.assertTrue((base / f"{ruta}.js").exists(), ruta)
