from pathlib import Path

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from apps.usuarios.constants import GRUPO_ADMINISTRADOR, GRUPO_CLIENTE, GRUPO_OPERADOR
from apps.usuarios.tests.utiles import crear_usuario, iniciar_sesion

PAGINAS = {
    None: ["guest:inicio", "guest:catalogo", "guest:servicios", "guest:acceso"],
    GRUPO_CLIENTE: [
        "customer:panel", "customer:tienda", "customer:carrito", "customer:cotizar",
        "customer:cotizaciones", "customer:pedidos", "customer:facturas", "customer:cuenta",
    ],
    GRUPO_OPERADOR: [
        "operator:panel", "operator:cotizaciones", "operator:encargos", "operator:facturas", "operator:clientes",
    ],
    GRUPO_ADMINISTRADOR: [
        "administrator:dashboard", "administrator:inventario", "administrator:servicios", "administrator:usuarios",
        "administrator:ventas", "administrator:configuracion", "administrator:producto_crear",
        "administrator:servicio_crear", "administrator:categoria_crear", "administrator:usuario_crear",
    ],
}

SCRIPTS_POR_VISTA = [
    "guest:inicio", "guest:catalogo", "guest:producto", "guest:servicios", "guest:servicio", "guest:acceso",
    "customer:panel", "customer:tienda", "customer:carrito", "customer:checkout", "customer:cotizar",
    "customer:cotizaciones", "customer:cotizacion", "customer:pedidos", "customer:pedido", "customer:facturas",
    "customer:factura", "customer:cuenta", "operator:panel", "operator:cotizaciones", "operator:cotizacion",
    "operator:encargos", "operator:encargo", "operator:facturas", "operator:factura", "operator:clientes",
    "administrator:dashboard", "administrator:inventario", "administrator:producto_crear",
    "administrator:producto_editar", "administrator:servicios", "administrator:servicio_crear",
    "administrator:servicio_editar", "administrator:categoria_crear", "administrator:categoria_editar",
    "administrator:usuarios", "administrator:usuario_crear", "administrator:usuario_editar",
    "administrator:ventas", "administrator:configuracion",
]


class PaginasBootstrapTests(TestCase):
    def comprobar(self, nombres):
        for nombre in nombres:
            respuesta = self.client.get(reverse(nombre))
            self.assertEqual(respuesta.status_code, 200, nombre)
            contenido = respuesta.content.decode()
            self.assertIn("bootstrap.min.css", contenido, nombre)
            self.assertIn("jquery-3.7.1.min.js", contenido, nombre)
            self.assertNotIn(" style=", contenido, nombre)
            self.assertNotIn("<style", contenido, nombre)

    def test_paginas_publicas(self):
        self.comprobar(PAGINAS[None])

    def test_paginas_por_rol(self):
        for indice, (rol, nombres) in enumerate((r for r in PAGINAS.items() if r[0])):
            self.client.logout()
            usuario = crear_usuario(f"rol{indice}@example.com", rol, is_staff=rol != GRUPO_CLIENTE)
            iniciar_sesion(self.client, usuario)
            self.comprobar(nombres)

    def test_cada_vista_tiene_su_script(self):
        base = Path(settings.BASE_DIR) / "static" / "js" / "vistas"
        for nombre in SCRIPTS_POR_VISTA:
            espacio, vista = nombre.split(":")
            self.assertTrue((base / espacio / f"{vista}.js").exists(), nombre)

    def test_componentes_js_existen(self):
        base = Path(settings.BASE_DIR) / "static" / "js" / "components"
        for archivo in ("toasts.js", "formularios.js"):
            self.assertTrue((base / archivo).exists(), archivo)
