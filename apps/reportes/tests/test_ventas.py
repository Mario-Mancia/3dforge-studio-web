import uuid
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.cotizaciones.tests.utiles import crear_cliente, crear_personal
from apps.facturacion.models import EstadoFactura, Factura
from apps.pagos.models import EstadoPago, MetodoPago, Pago
from apps.reportes.forms import fechas_filtro
from apps.reportes.selectors import ventas as sel
from apps.usuarios.constants import GRUPO_ADMINISTRADOR
from apps.usuarios.tests.utiles import crear_usuario, iniciar_sesion


def factura(cliente, total="100.00", estado=EstadoFactura.PENDIENTE, emision=None, nombre="Cliente", saldo=None):
    return Factura.objects.create(
        cliente=cliente, numero_factura=f"FAC-V{uuid.uuid4().hex[:8].upper()}", nombre_facturacion=nombre,
        subtotal=Decimal(total), total=Decimal(total), estado=estado, fecha_emision=emision or timezone.now(),
        saldo_pendiente=Decimal(saldo if saldo is not None else (total if estado != EstadoFactura.ANULADA else "0.00")),
    )


class BaseVentas(TestCase):
    def setUp(self):
        self.usuario, self.cliente = crear_cliente("cliente@example.com")
        self.metodo, _ = MetodoPago.objects.get_or_create(nombre="Efectivo")
        self.hoy = timezone.localdate()


class ResumenTests(BaseVentas):
    def test_totales_por_rango_y_metodo(self):
        f = factura(self.cliente, "100.00")
        factura(self.cliente, "40.00", estado=EstadoFactura.ANULADA)
        factura(self.cliente, "500.00", emision=timezone.now() - timedelta(days=90))
        Pago.objects.create(factura=f, metodo_pago=self.metodo, monto=Decimal("60.00"), estado=EstadoPago.CONFIRMADO)
        Pago.objects.create(factura=f, metodo_pago=self.metodo, monto=Decimal("5.00"), estado=EstadoPago.CANCELADO)
        resumen = sel.resumen_ventas(self.hoy - timedelta(days=1), self.hoy)
        self.assertEqual(resumen["facturado"], Decimal("100.00"))
        self.assertEqual(resumen["cobrado"], Decimal("60.00"))
        self.assertEqual(resumen["cantidad_facturas"], 1)
        self.assertEqual(resumen["cantidad_anuladas"], 1)
        self.assertEqual(resumen["ticket_promedio"], Decimal("100.00"))
        self.assertEqual(resumen["por_metodo"][0]["metodo"], "Efectivo")

    def test_los_limites_incluyen_todo_el_dia_final(self):
        factura(self.cliente, "10.00")
        self.assertEqual(sel.facturas_en_rango(self.hoy, self.hoy).count(), 1)
        self.assertEqual(sel.facturas_en_rango(self.hoy - timedelta(days=5), self.hoy - timedelta(days=1)).count(), 0)

    def test_filtro_de_fechas_invalidas(self):
        desde, hasta, errores = fechas_filtro({"desde": "2026-13-45"})
        self.assertEqual(len(errores), 1)
        self.assertEqual(hasta, self.hoy)
        _, _, errores = fechas_filtro({"desde": "2026-05-10", "hasta": "2026-05-01"})
        self.assertEqual(len(errores), 1)
        _, _, errores = fechas_filtro({"desde": "2000-01-01", "hasta": "2026-01-01"})
        self.assertEqual(len(errores), 1)
        self.assertEqual(fechas_filtro({})[2], [])


class VistasVentasTests(BaseVentas):
    def setUp(self):
        super().setUp()
        self.admin = crear_usuario("admin@example.com", GRUPO_ADMINISTRADOR, is_staff=True)

    def test_pagina_de_ventas_y_filtros(self):
        factura(self.cliente, "80.00")
        iniciar_sesion(self.client, self.admin)
        respuesta = self.client.get(reverse("administrator:ventas"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["resumen"]["facturado"], Decimal("80.00"))
        self.assertNotIn(" style=", respuesta.content.decode())
        for consulta in ({"desde": "basura"}, {"desde": "2026-05-10", "hasta": "2026-05-01"}, {"desde": "2026-01-01", "hasta": "2026-02-01"}):
            self.assertEqual(self.client.get(reverse("administrator:ventas"), consulta).status_code, 200)

    def test_csv_de_facturas_y_pagos(self):
        f = factura(self.cliente, "100.00")
        Pago.objects.create(factura=f, metodo_pago=self.metodo, monto=Decimal("25.00"), estado=EstadoPago.CONFIRMADO, referencia="R-1")
        iniciar_sesion(self.client, self.admin)
        respuesta = self.client.get(reverse("administrator:ventas_exportar", args=["facturas"]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("text/csv", respuesta["Content-Type"])
        self.assertIn("attachment", respuesta["Content-Disposition"])
        texto = respuesta.content.decode("utf-8")
        self.assertTrue(texto.startswith("\ufeff"))
        self.assertIn("Numero,Fecha emision", texto)
        self.assertIn(f.numero_factura, texto)
        pagos = self.client.get(reverse("administrator:ventas_exportar", args=["pagos"])).content.decode("utf-8")
        self.assertIn("R-1", pagos)
        self.assertIn("25.00", pagos)

    def test_csv_neutraliza_formulas(self):
        factura(self.cliente, "10.00", nombre='=HYPERLINK("http://malo")')
        iniciar_sesion(self.client, self.admin)
        texto = self.client.get(reverse("administrator:ventas_exportar", args=["facturas"])).content.decode("utf-8")
        self.assertIn("'=HYPERLINK", texto)

    def test_tipo_de_exportacion_invalido_y_permisos(self):
        iniciar_sesion(self.client, self.admin)
        self.assertEqual(self.client.get(reverse("administrator:ventas_exportar", args=["otro"])).status_code, 404)
        self.client.logout()
        iniciar_sesion(self.client, crear_personal("operador@example.com"))
        self.assertEqual(self.client.get(reverse("administrator:ventas")).status_code, 403)
        self.assertEqual(self.client.get(reverse("administrator:ventas_exportar", args=["facturas"])).status_code, 403)
        self.client.logout()
        iniciar_sesion(self.client, self.usuario)
        self.assertEqual(self.client.get(reverse("administrator:ventas_exportar", args=["pagos"])).status_code, 403)
