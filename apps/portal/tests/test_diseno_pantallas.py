from decimal import Decimal

from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse

from apps.catalogo.models import Producto
from apps.cotizaciones.models import Cotizacion
from apps.cotizaciones.tests.utiles import crear_cliente, crear_personal
from apps.crm.services.crm import crear_solicitud
from apps.encargos.models import Encargo
from apps.facturacion.models import Factura
from apps.usuarios.constants import GRUPO_ADMINISTRADOR
from apps.usuarios.tests.utiles import crear_usuario, iniciar_sesion


class TarjetasDeProductoTests(TestCase):
    def setUp(self):
        Producto.objects.create(sku="CARD-001", nombre="Producto con stock", precio=Decimal("12.50"), stock=10)
        Producto.objects.create(sku="CARD-002", nombre="Producto agotado", precio=Decimal("5.00"), stock=0)

    def test_catalogo_publico_muestra_tarjetas_con_chip_y_enlace(self):
        respuesta = self.client.get(reverse("guest:catalogo"))
        for texto in ("tarjeta-producto", "chip-disponible", "chip-agotado", "precio-grande", "Ver detalle"):
            self.assertContains(respuesta, texto)
        self.assertNotContains(respuesta, "add_shopping_cart")

    def test_la_tienda_solo_permite_agregar_lo_que_tiene_stock(self):
        usuario, _ = crear_cliente("cliente@example.com")
        iniciar_sesion(self.client, usuario)
        respuesta = self.client.get(reverse("customer:tienda"))
        con_stock = Producto.objects.get(sku="CARD-001")
        agotado = Producto.objects.get(sku="CARD-002")
        self.assertContains(respuesta, reverse("customer:carrito_agregar", args=[con_stock.pk]))
        self.assertNotContains(respuesta, reverse("customer:carrito_agregar", args=[agotado.pk]))

    def test_estado_vacio_del_catalogo(self):
        Producto.objects.all().delete()
        respuesta = self.client.get(reverse("guest:catalogo"))
        self.assertContains(respuesta, "estado-vacio")

    def test_detalle_de_producto_conserva_el_boton_de_copiar_sku(self):
        producto = Producto.objects.get(sku="CARD-001")
        respuesta = self.client.get(reverse("guest:producto", args=[producto.pk]))
        self.assertContains(respuesta, 'id="copiar-sku"')
        self.assertContains(respuesta, "imagen-detalle")


class AssetsYComponentesTests(TestCase):
    def test_base_enlaza_componentes_css_y_ui_js(self):
        respuesta = self.client.get(reverse("guest:inicio"))
        self.assertContains(respuesta, "css/componentes.css")
        self.assertContains(respuesta, "js/components/ui.js")

    def test_tarjeta_de_indicador_con_icono(self):
        html = render_to_string("components/kpi.html", {"titulo": "Ventas del mes", "valor": 10, "prefijo": "$", "decimales": 2})
        self.assertIn("payments", html)
        self.assertIn("$10.00", html)
        self.assertIn("event_busy", render_to_string("components/kpi.html", {"titulo": "Facturas vencidas", "valor": 1}))


class TablasConAccionesTests(TestCase):
    def setUp(self):
        self.usuario, self.cliente = crear_cliente("cliente@example.com")
        self.operador = crear_personal("operador@example.com")
        self.encargo = Encargo.objects.create(cliente=self.cliente, codigo="ENC-UI-1", descripcion="x")
        self.cotizacion = Cotizacion.objects.create(cliente=self.cliente, codigo="COT-UI-1")
        self.factura = Factura.objects.create(
            cliente=self.cliente, numero_factura="FAC-UI-1", nombre_facturacion="Cliente",
            subtotal=Decimal("10.00"), total=Decimal("10.00"), saldo_pendiente=Decimal("10.00"),
        )
        self.solicitud = crear_solicitud(self.cliente, "Duda UI", "Descripcion suficiente aqui.")

    def comprobar(self, nombre, destino, veces=2):
        respuesta = self.client.get(reverse(nombre))
        self.assertContains(respuesta, f'href="{destino}"', count=veces, msg_prefix=nombre)
        self.assertContains(respuesta, "visibility", msg_prefix=nombre)
        self.assertNotIn(" style=", respuesta.content.decode(), nombre)

    def test_listas_del_operador_tienen_boton_ver(self):
        iniciar_sesion(self.client, self.operador)
        self.comprobar("operator:encargos", reverse("operator:encargo", args=[self.encargo.pk]))
        self.comprobar("operator:cotizaciones", reverse("operator:cotizacion", args=[self.cotizacion.pk]))
        self.comprobar("operator:facturas", reverse("operator:factura", args=[self.factura.pk]))
        self.comprobar("operator:clientes", reverse("operator:cliente", args=[self.cliente.pk]))
        self.comprobar("operator:soporte", reverse("operator:soporte_detalle", args=[self.solicitud.pk]))

    def test_listas_del_cliente_tienen_boton_ver(self):
        self.encargo.estado = "PENDIENTE"
        iniciar_sesion(self.client, self.usuario)
        self.comprobar("customer:pedidos", reverse("customer:pedido", args=[self.encargo.pk]))
        self.comprobar("customer:facturas", reverse("customer:factura", args=[self.factura.pk]))
        self.comprobar("customer:cotizaciones", reverse("customer:cotizacion", args=[self.cotizacion.pk]))

    def test_listas_vacias_muestran_estado_vacio(self):
        Encargo.objects.all().delete()
        iniciar_sesion(self.client, self.operador)
        self.assertContains(self.client.get(reverse("operator:encargos")), "estado-vacio")


class FormulariosEnColumnaTests(TestCase):
    def test_encargo_con_los_tres_formularios_en_el_panel_de_gestion(self):
        usuario, cliente = crear_cliente("cliente@example.com")
        operador = crear_personal("operador@example.com")
        encargo = Encargo.objects.create(cliente=cliente, codigo="ENC-UI-2", descripcion="x")
        iniciar_sesion(self.client, operador)
        respuesta = self.client.get(reverse("operator:encargo", args=[encargo.pk]))
        contenido = respuesta.content.decode()
        self.assertIn("panel-gestion", contenido)
        for accion in ("estado", "asignar", "archivo"):
            self.assertContains(respuesta, reverse("operator:encargo_accion", args=[encargo.pk, accion]))
        self.assertNotIn(" style=", contenido)

    def test_factura_y_cliente_mantienen_sus_formularios(self):
        usuario, cliente = crear_cliente("cliente@example.com")
        operador = crear_personal("operador@example.com")
        factura = Factura.objects.create(
            cliente=cliente, numero_factura="FAC-UI-2", nombre_facturacion="Cliente",
            subtotal=Decimal("10.00"), total=Decimal("10.00"), saldo_pendiente=Decimal("10.00"),
        )
        iniciar_sesion(self.client, operador)
        respuesta = self.client.get(reverse("operator:factura", args=[factura.pk]))
        for texto in ("panel-gestion", 'id="usar-saldo"', 'data-validar="pago"', "data-saldo"):
            self.assertContains(respuesta, texto)
        respuesta = self.client.get(reverse("operator:cliente", args=[cliente.pk]))
        for texto in ("panel-gestion", 'data-validar="nota"', 'data-validar="interaccion"'):
            self.assertContains(respuesta, texto)

    def test_cotizar_y_perfil_por_secciones(self):
        usuario, _ = crear_cliente("cliente@example.com")
        iniciar_sesion(self.client, usuario)
        respuesta = self.client.get(reverse("customer:cotizar"))
        for texto in ("zona-archivos", "seccion-formulario", "paso-numerado", "enctype=\"multipart/form-data\"", 'data-validar="cotizar"'):
            self.assertContains(respuesta, texto)
        respuesta = self.client.get(reverse("customer:cuenta"))
        for texto in ("avatar-grande", "seccion-formulario", 'data-validar="perfil"', 'data-campo="nombre_empresa"'):
            self.assertContains(respuesta, texto)

    def test_administrador_ve_acciones_en_sus_tablas(self):
        iniciar_sesion(self.client, crear_usuario("admin@example.com", GRUPO_ADMINISTRADOR, is_staff=True))
        for nombre in ("administrator:inventario", "administrator:servicios", "administrator:usuarios"):
            respuesta = self.client.get(reverse(nombre))
            self.assertEqual(respuesta.status_code, 200, nombre)
            self.assertContains(respuesta, "tabla-acciones", msg_prefix=nombre)
