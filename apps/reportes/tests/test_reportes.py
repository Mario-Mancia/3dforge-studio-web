import uuid
from datetime import timedelta
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.catalogo.models import Producto
from apps.cotizaciones.tests.utiles import crear_cliente, crear_personal, crear_servicio
from apps.encargos.models import Encargo
from apps.facturacion.models import EstadoFactura, Factura, FacturaDetalle
from apps.pagos.models import EstadoPago, MetodoPago, Pago
from apps.reportes.selectors import reportes as sel
from apps.usuarios.constants import GRUPO_ADMINISTRADOR
from apps.usuarios.models import Empleado
from apps.usuarios.tests.utiles import crear_usuario, iniciar_sesion


def factura(cliente, total="100.00", estado=EstadoFactura.PENDIENTE, saldo=None, emision=None, vence=None):
    return Factura.objects.create(
        cliente=cliente, numero_factura=f"FAC-T{uuid.uuid4().hex[:8].upper()}", nombre_facturacion="Cliente",
        subtotal=Decimal(total), total=Decimal(total),
        saldo_pendiente=Decimal(saldo if saldo is not None else (total if estado != EstadoFactura.ANULADA else "0.00")),
        estado=estado, fecha_emision=emision or timezone.now(), fecha_vencimiento=vence,
    )


def detalle(f, monto, servicio=None, producto=None):
    return FacturaDetalle.objects.create(
        factura=f, servicio=servicio, producto=producto, descripcion="Linea", cantidad=Decimal("1"),
        precio_unitario=Decimal(monto), subtotal=Decimal(monto),
    )


class BaseReportes(TestCase):
    def setUp(self):
        cache.clear()
        self.usuario, self.cliente = crear_cliente("cliente@example.com")
        self.metodo, _ = MetodoPago.objects.get_or_create(nombre="Efectivo")


class IndicadoresTests(BaseReportes):
    def test_kpis_excluyen_anuladas_y_suman_cobros(self):
        f = factura(self.cliente, "100.00")
        factura(self.cliente, "50.00", estado=EstadoFactura.ANULADA)
        Pago.objects.create(factura=f, metodo_pago=self.metodo, monto=Decimal("40.00"), estado=EstadoPago.CONFIRMADO)
        Pago.objects.create(factura=f, metodo_pago=self.metodo, monto=Decimal("10.00"), estado=EstadoPago.CANCELADO)
        kpis = sel.kpis_admin()
        self.assertEqual(kpis["ventas_mes"], Decimal("100.00"))
        self.assertEqual(kpis["cobrado_mes"], Decimal("40.00"))
        self.assertEqual(kpis["por_cobrar"], Decimal("100.00"))

    def test_facturas_vencidas_y_stock_bajo_y_clientes_nuevos(self):
        factura(self.cliente, emision=timezone.now() - timedelta(days=10), vence=timezone.now() - timedelta(days=2))
        factura(self.cliente, vence=timezone.now() + timedelta(days=5))
        Producto.objects.create(sku="BAJ-001", nombre="Bajo", precio=Decimal("1.00"), stock=1, stock_minimo=3)
        Producto.objects.create(sku="OK-001", nombre="Bien", precio=Decimal("1.00"), stock=9, stock_minimo=3)
        kpis = sel.kpis_admin()
        self.assertEqual(kpis["facturas_vencidas"], 1)
        self.assertEqual(kpis["productos_bajo_stock"], 1)
        self.assertEqual(kpis["clientes_nuevos"], 1)

    def test_valores_en_cero_sin_datos(self):
        kpis = sel.kpis_admin()
        self.assertEqual((kpis["ventas_mes"], kpis["cobrado_mes"], kpis["por_cobrar"]), (Decimal("0.00"),) * 3)
        self.assertIsNone(sel.conversion_cotizaciones(sel.periodo("6m")))


class GraficosTests(BaseReportes):
    def test_cantidad_de_periodos_por_rango(self):
        for rango, cantidad in (("30d", 30), ("6m", 6), ("12m", 12), ("invalido", 6)):
            self.assertEqual(len(sel.periodo(rango)["pasos"]), cantidad, rango)

    def test_serie_mensual_ubica_la_venta_en_su_mes(self):
        hace_mes_y_medio = timezone.now() - timedelta(days=45)
        factura(self.cliente, "70.00", emision=hace_mes_y_medio)
        factura(self.cliente, "30.00")
        graficos = sel.graficos_admin(sel.periodo("6m"))["ventas_cobros"]
        ventas = graficos["series"][0]["valores"]
        etiqueta = timezone.localtime(hace_mes_y_medio).strftime("%m/%Y")
        self.assertEqual(ventas[graficos["etiquetas"].index(etiqueta)], 70.0)
        self.assertEqual(ventas[-1], 30.0)
        self.assertEqual(sum(ventas), 100.0)

    def test_ingresos_por_tipo_y_top(self):
        servicio = crear_servicio("Impresión X")
        producto = Producto.objects.create(sku="TOP-001", nombre="Producto Top", precio=Decimal("1.00"), stock=5)
        f = factura(self.cliente, "100.00")
        detalle(f, "60.00", servicio=servicio)
        detalle(f, "30.00", producto=producto)
        detalle(f, "10.00")
        graficos = sel.graficos_admin(sel.periodo("6m"))
        self.assertEqual(graficos["ingresos_tipo"]["series"][0]["valores"], [60.0, 30.0, 10.0])
        self.assertEqual(graficos["top_ventas"]["etiquetas"], ["Impresión X", "Producto Top", "Sin catálogo"])

    def test_encargos_por_estado_cubre_todos_los_estados(self):
        Encargo.objects.create(cliente=self.cliente, codigo="ENC-R-1", descripcion="x")
        grafico = sel.graficos_admin(sel.periodo("6m"))["encargos_estado"]
        self.assertEqual(len(grafico["etiquetas"]), 8)
        self.assertEqual(sum(grafico["series"][0]["valores"]), 1)

    def test_carga_semanal_del_operador(self):
        Encargo.objects.create(cliente=self.cliente, codigo="ENC-R-2", descripcion="x")
        semanal = sel.datos_operador()["graficos"]["carga_semanal"]
        self.assertEqual(len(semanal["etiquetas"]), 8)
        self.assertEqual(semanal["series"][0]["valores"][-1], 1)


class CacheYTrabajoTests(BaseReportes):
    def test_segunda_lectura_usa_cache(self):
        sel.datos_admin("6m")
        with self.assertNumQueries(0):
            sel.datos_admin("6m")

    def test_trabajo_del_operador_solo_incluye_lo_suyo(self):
        operador = crear_personal("operador@example.com")
        empleado = Empleado.objects.create(usuario=operador, codigo_empleado="EMP-R1", cargo="Operador")
        Encargo.objects.create(cliente=self.cliente, codigo="ENC-MIO", descripcion="x", empleado_responsable=empleado)
        Encargo.objects.create(cliente=self.cliente, codigo="ENC-OTRO", descripcion="x")
        trabajo = sel.trabajo_operador(operador)
        self.assertEqual([e.codigo for e in trabajo["mis_encargos"]], ["ENC-MIO"])
        self.assertEqual(trabajo["mis_encargos_total"], 1)


class VistasDashboardTests(BaseReportes):
    def test_dashboard_admin_con_y_sin_datos(self):
        admin = crear_usuario("admin@example.com", GRUPO_ADMINISTRADOR, is_staff=True)
        iniciar_sesion(self.client, admin)
        respuesta = self.client.get(reverse("administrator:dashboard"))
        self.assertEqual(respuesta.status_code, 200)
        contenido = respuesta.content.decode()
        self.assertIn("datos-graficos", contenido)
        self.assertIn("chart.js@4.4.1", contenido)
        self.assertNotIn(" style=", contenido)
        f = factura(self.cliente, "80.00")
        detalle(f, "80.00")
        cache.clear()
        for rango in ("30d", "6m", "12m", "otro"):
            self.assertEqual(self.client.get(reverse("administrator:dashboard"), {"rango": rango}).status_code, 200)

    def test_operador_no_ve_dinero_global_ni_el_dashboard_admin(self):
        operador = crear_personal("operador@example.com")
        iniciar_sesion(self.client, operador)
        self.assertEqual(self.client.get(reverse("administrator:dashboard")).status_code, 403)
        respuesta = self.client.get(reverse("operator:panel"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, "Ventas del mes")
        self.assertNotContains(respuesta, "Cobrado del mes")
        self.assertContains(respuesta, "Mi trabajo pendiente")

    def test_cliente_no_accede_a_los_paneles_del_personal(self):
        iniciar_sesion(self.client, self.usuario)
        self.assertEqual(self.client.get(reverse("operator:panel")).status_code, 403)
        self.assertEqual(self.client.get(reverse("administrator:dashboard")).status_code, 403)

    def test_chart_js_solo_se_carga_en_los_dashboards(self):
        admin = crear_usuario("admin2@example.com", GRUPO_ADMINISTRADOR, is_staff=True)
        iniciar_sesion(self.client, admin)
        self.assertNotContains(self.client.get(reverse("administrator:inventario")), "chart.js")
