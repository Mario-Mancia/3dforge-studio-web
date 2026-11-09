import uuid
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.cotizaciones.tests.utiles import crear_cliente, crear_personal
from apps.encargos.models import Encargo, EncargoDetalle, EstadoEncargo
from apps.facturacion.models import EstadoFactura, Factura
from apps.facturacion.services import facturacion as srv
from apps.pagos.models import EstadoPago, MetodoPago, Pago
from apps.pagos.services import pagos
from apps.usuarios.tests.utiles import iniciar_sesion


def encargo_aprobado(cliente, estado=EstadoEncargo.APROBADO):
    encargo = Encargo.objects.create(
        cliente=cliente, codigo=f"ENC-F{uuid.uuid4().hex[:8].upper()}", descripcion="Trabajo de prueba",
        subtotal=Decimal("20.00"), impuesto=Decimal("2.60"), total=Decimal("22.60"), estado=estado,
    )
    EncargoDetalle.objects.create(
        encargo=encargo, descripcion="Pieza", cantidad=Decimal("2"), precio_unitario=Decimal("10.00"),
        impuesto=Decimal("2.60"), subtotal=Decimal("20.00"),
    )
    return encargo


class BaseFacturaTests(TestCase):
    def setUp(self):
        self.usuario, self.cliente = crear_cliente("cliente@example.com")
        self.operador = crear_personal("operador@example.com")
        self.efectivo, _ = MetodoPago.objects.get_or_create(nombre="Efectivo")

    def factura(self):
        return srv.crear_desde_encargo(encargo_aprobado(self.cliente).pk, self.operador)

    def pagar(self, factura, monto, **extra):
        return pagos.registrar_pago(factura.pk, self.operador, self.efectivo.pk, Decimal(monto), **extra)


class CreacionTests(BaseFacturaTests):
    def test_crea_factura_con_snapshot_e_idempotencia(self):
        encargo = encargo_aprobado(self.cliente)
        f = srv.crear_desde_encargo(encargo.pk, self.operador)
        self.assertTrue(f.numero_factura.startswith("FAC-"))
        self.assertEqual(f.estado, EstadoFactura.PENDIENTE)
        self.assertEqual((f.total, f.saldo_pendiente), (Decimal("22.60"), Decimal("22.60")))
        self.assertEqual(f.detalles.count(), 1)
        self.assertGreater(f.fecha_vencimiento, timezone.now())
        self.assertEqual(srv.crear_desde_encargo(encargo.pk, self.operador).pk, f.pk)
        self.assertEqual(Factura.objects.count(), 1)

    def test_reglas_de_creacion(self):
        with self.assertRaises(srv.ErrorFacturacion):
            srv.crear_desde_encargo(encargo_aprobado(self.cliente, EstadoEncargo.PENDIENTE).pk, self.operador)
        with self.assertRaises(PermissionDenied):
            srv.crear_desde_encargo(encargo_aprobado(self.cliente).pk, self.usuario)


class PagosTests(BaseFacturaTests):
    def test_pagos_parciales_y_completo(self):
        f = self.factura()
        self.pagar(f, "10.00")
        f.refresh_from_db()
        self.assertEqual((f.estado, f.saldo_pendiente), (EstadoFactura.PARCIALMENTE_PAGADA, Decimal("12.60")))
        self.pagar(f, "12.60")
        f.refresh_from_db()
        self.assertEqual((f.estado, f.saldo_pendiente), (EstadoFactura.PAGADA, Decimal("0.00")))
        with self.assertRaises(pagos.ErrorPago):
            self.pagar(f, "1.00")

    def test_validaciones_de_monto_y_metodo(self):
        f = self.factura()
        for monto in ("0", "-5", "22.61"):
            with self.assertRaises(pagos.ErrorPago):
                self.pagar(f, monto)
        with self.assertRaises(pagos.ErrorPago):
            pagos.registrar_pago(f.pk, self.operador, 999999, Decimal("5.00"))
        pasarela, _ = MetodoPago.objects.get_or_create(nombre="Pasarela de pagos")
        with self.assertRaises(pagos.ErrorPago):
            pagos.registrar_pago(f.pk, self.operador, pasarela.pk, Decimal("5.00"))
        self.assertEqual(Pago.objects.count(), 0)

    def test_cliente_no_registra_pagos(self):
        f = self.factura()
        with self.assertRaises(PermissionDenied):
            pagos.registrar_pago(f.pk, self.usuario, self.efectivo.pk, Decimal("5.00"))

    def test_pago_identico_inmediato_se_rechaza(self):
        f = self.factura()
        self.pagar(f, "5.00")
        with self.assertRaises(pagos.ErrorPago):
            self.pagar(f, "5.00")

    def test_cancelar_pago_restituye_saldo_y_estado(self):
        f = self.factura()
        p = self.pagar(f, "22.60")
        pagos.anular_pago(p.pk, self.operador, "Error de captura")
        f.refresh_from_db()
        p.refresh_from_db()
        self.assertEqual((f.estado, f.saldo_pendiente, p.estado), (EstadoFactura.PENDIENTE, Decimal("22.60"), EstadoPago.CANCELADO))
        with self.assertRaises(pagos.ErrorPago):
            pagos.anular_pago(p.pk, self.operador, "otra vez")

    def test_factura_vencida_sigue_cobrandose(self):
        f = self.factura()
        Factura.objects.filter(pk=f.pk).update(fecha_vencimiento=timezone.now() - timedelta(days=1))
        self.assertEqual(srv.marcar_vencidas(), 1)
        f.refresh_from_db()
        self.assertEqual(f.estado, EstadoFactura.VENCIDA)
        self.pagar(f, "22.60")
        f.refresh_from_db()
        self.assertEqual(f.estado, EstadoFactura.PAGADA)


class AnulacionTests(BaseFacturaTests):
    def test_anular_libera_el_encargo_y_bloquea_pagos(self):
        f = self.factura()
        encargo_id = f.encargo_id
        srv.anular_factura(f.pk, self.operador, "Datos incorrectos")
        f.refresh_from_db()
        self.assertEqual((f.estado, f.saldo_pendiente, f.encargo_id), (EstadoFactura.ANULADA, Decimal("0.00"), None))
        with self.assertRaises(pagos.ErrorPago):
            self.pagar(f, "5.00")
        self.assertEqual(srv.crear_desde_encargo(encargo_id, self.operador).estado, EstadoFactura.PENDIENTE)

    def test_no_se_anula_con_pagos_confirmados(self):
        f = self.factura()
        self.pagar(f, "5.00")
        with self.assertRaises(srv.ErrorFacturacion):
            srv.anular_factura(f.pk, self.operador, "x")


class VistasFacturaTests(BaseFacturaTests):
    def test_flujo_por_vistas_y_aislamiento(self):
        encargo = encargo_aprobado(self.cliente)
        iniciar_sesion(self.client, self.operador)
        respuesta = self.client.post(reverse("operator:encargo_factura", args=[encargo.pk]))
        f = Factura.objects.get()
        self.assertRedirects(respuesta, reverse("operator:factura", args=[f.pk]), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse("operator:facturas")).status_code, 200)
        self.assertEqual(self.client.get(reverse("operator:factura", args=[f.pk])).status_code, 200)
        self.client.post(reverse("operator:factura_accion", args=[f.pk, "pagar"]),
                         {"metodo": self.efectivo.pk, "monto": "10.00", "referencia": "R-1"})
        f.refresh_from_db()
        self.assertEqual(f.saldo_pendiente, Decimal("12.60"))
        self.client.post(reverse("operator:factura_accion", args=[f.pk, "pagar"]),
                         {"metodo": self.efectivo.pk, "monto": "99.00"})
        f.refresh_from_db()
        self.assertEqual(f.saldo_pendiente, Decimal("12.60"))

        self.client.logout()
        iniciar_sesion(self.client, self.usuario)
        self.assertEqual(self.client.get(reverse("customer:facturas")).status_code, 200)
        self.assertEqual(self.client.get(reverse("customer:factura", args=[f.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("operator:facturas")).status_code, 403)
        otro, _ = crear_cliente("otro@example.com")
        self.client.logout()
        iniciar_sesion(self.client, otro)
        self.assertEqual(self.client.get(reverse("customer:factura", args=[f.pk])).status_code, 404)
