import re
from pathlib import Path

from django.conf import settings
from django.contrib.messages.storage.base import Message
from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse

from apps.usuarios.constants import GRUPO_ADMINISTRADOR, GRUPO_CLIENTE, GRUPO_OPERADOR
from apps.usuarios.tests.utiles import crear_usuario, iniciar_sesion


class LayoutTests(TestCase):
    def test_layout_incluye_tema_iconos_y_css_global(self):
        respuesta = self.client.get(reverse("guest:inicio"))
        for texto in ("localStorage.getItem", "Material+Symbols+Rounded", "css/app.css", "data-alternar-tema", "js/components/tema.js"):
            self.assertContains(respuesta, texto)
        self.assertNotIn(" style=", respuesta.content.decode())

    def test_alternador_de_tema_en_cada_pantalla(self):
        paginas = {
            None: ["guest:inicio", "guest:catalogo", "guest:servicios", "guest:acceso", "guest:terminos"],
            GRUPO_CLIENTE: ["customer:panel", "customer:tienda", "customer:cuenta"],
            GRUPO_OPERADOR: ["operator:panel", "operator:cotizaciones"],
            GRUPO_ADMINISTRADOR: ["administrator:dashboard", "administrator:usuarios", "administrator:ventas"],
        }
        for indice, (rol, nombres) in enumerate(paginas.items()):
            if rol:
                self.client.logout()
                iniciar_sesion(self.client, crear_usuario(f"ui{indice}@example.com", rol, is_staff=rol != GRUPO_CLIENTE))
            for nombre in nombres:
                respuesta = self.client.get(reverse(nombre))
                self.assertEqual(respuesta.status_code, 200, nombre)
                self.assertContains(respuesta, "data-alternar-tema", msg_prefix=nombre)

    def test_terminos_y_enlace_en_el_pie(self):
        respuesta = self.client.get(reverse("guest:terminos"))
        self.assertContains(respuesta, "Términos y condiciones de uso")
        self.assertContains(self.client.get(reverse("guest:inicio")), reverse("guest:terminos"))

    def test_css_define_ambas_paletas_y_la_fuente(self):
        css = (Path(settings.BASE_DIR) / "static" / "css" / "app.css").read_text(encoding="utf-8")
        for texto in ("#167C80", "#11666A", "#D5F0ED", "#65D4CE", "#101819", "family=Roboto", '[data-bs-theme="dark"]'):
            self.assertIn(texto, css)
        self.assertTrue((Path(settings.BASE_DIR) / "static" / "js" / "vistas" / "guest" / "terminos.js").exists())


class BarraTests(TestCase):
    def test_menu_de_usuario_del_cliente(self):
        usuario = crear_usuario("cliente@example.com", GRUPO_CLIENTE)
        iniciar_sesion(self.client, usuario)
        respuesta = self.client.get(reverse("customer:panel"))
        for texto in ("Cerrar sesión", "Mi perfil", reverse("customer:cuenta"), usuario.nombres, "data-bs-toggle=\"dropdown\""):
            self.assertContains(respuesta, texto)

    def test_menu_de_usuario_del_personal(self):
        iniciar_sesion(self.client, crear_usuario("op@example.com", GRUPO_OPERADOR, is_staff=True))
        respuesta = self.client.get(reverse("operator:panel"))
        self.assertContains(respuesta, "Mi cuenta")
        self.assertContains(respuesta, reverse("account_change_password"))

    def test_ruta_activa_resaltada(self):
        iniciar_sesion(self.client, crear_usuario("cliente2@example.com", GRUPO_CLIENTE))
        contenido = self.client.get(reverse("customer:tienda")).content.decode()
        self.assertIn(f'nav-link active" href="{reverse("customer:tienda")}"', contenido)
        self.assertNotIn(f'nav-link active" href="{reverse("customer:pedidos")}"', contenido)

    def test_visitante_ve_ingresar_y_no_el_menu_de_usuario(self):
        contenido = self.client.get(reverse("guest:inicio")).content.decode()
        self.assertIn(reverse("guest:acceso"), contenido)
        self.assertNotIn("Cerrar sesión", contenido)


class ToastsTests(TestCase):
    def test_los_cuatro_tipos_con_su_icono(self):
        html = render_to_string(
            "components/mensajes.html",
            {"messages": [Message(25, "ok"), Message(40, "falla"), Message(30, "cuidado"), Message(20, "dato")]},
        )
        for clase, icono in (("toast-success", "check_circle"), ("toast-error", "error"), ("toast-warning", "warning"), ("toast-info", "info")):
            self.assertIn(clase, html)
            self.assertIn(f'aria-hidden="true">{icono}</span>', html)
        self.assertIn("toast-progreso", html)

    def test_un_mensaje_de_negocio_se_muestra_como_toast(self):
        iniciar_sesion(self.client, crear_usuario("toast@example.com", GRUPO_CLIENTE))
        respuesta = self.client.post(reverse("customer:carrito_agregar", args=[999999]), {"cantidad": "1"}, follow=True)
        self.assertContains(respuesta, "toast-error")


class AutenticacionTests(TestCase):
    def activa(self, contenido):
        return re.findall(r'tab-pane fade show active" id="(panel-[a-z]+)"', contenido)

    def test_acceso_muestra_una_sola_pestana(self):
        self.assertEqual(self.activa(self.client.get(reverse("guest:acceso")).content.decode()), ["panel-login"])
        self.assertEqual(self.activa(self.client.get(reverse("guest:acceso"), {"registro": "1"}).content.decode()), ["panel-registro"])

    def test_login_fallido_mantiene_el_diseno_y_el_error(self):
        respuesta = self.client.post(reverse("account_login"), {"login": "nadie@example.com", "password": "incorrecta"})
        self.assertEqual(respuesta.status_code, 200)
        contenido = respuesta.content.decode()
        for texto in ("bootstrap.min.css", "css/app.css", "auth-tarjeta", "alert-danger", "data-alternar-tema"):
            self.assertIn(texto, contenido)
        self.assertEqual(self.activa(contenido), ["panel-login"])
        self.assertIn("nadie@example.com", contenido)

    def test_registro_con_errores_reabre_la_pestana_de_registro(self):
        datos = {"nombres": "Luis", "apellidos": "Pérez", "email": "luis.ui@example.com", "telefono": "", "password1": "Clave-Segura-123", "password2": "distinta"}
        respuesta = self.client.post(reverse("account_signup"), datos)
        self.assertEqual(respuesta.status_code, 200)
        contenido = respuesta.content.decode()
        self.assertEqual(self.activa(contenido), ["panel-registro"])
        self.assertIn("is-invalid", contenido)
        self.assertIn("luis.ui@example.com", contenido)

    def test_paginas_de_allauth_usan_el_layout(self):
        respuesta = self.client.get(reverse("account_reset_password"))
        self.assertEqual(respuesta.status_code, 200)
        for texto in ("css/app.css", "data-alternar-tema", "auth-contenido"):
            self.assertContains(respuesta, texto)

    def test_paginas_de_error_usan_el_diseno(self):
        respuesta = self.client.get("/ruta/que/no/existe/")
        self.assertEqual(respuesta.status_code, 404)
        self.assertContains(respuesta, "css/app.css", status_code=404)
