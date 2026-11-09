from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.templatetags.bootstrap import progreso_clase, progreso_valor
from apps.cotizaciones.models import Cotizacion
from apps.cotizaciones.tests.utiles import crear_cliente
from apps.crm.services.crm import crear_solicitud
from apps.encargos.models import Encargo
from apps.facturacion.models import Factura
from apps.notificaciones.services.notificaciones import notificar
from apps.usuarios.tests.utiles import iniciar_sesion


def cotizacion_enviada(cliente, codigo):
    return Cotizacion.objects.create(
        cliente=cliente, codigo=codigo, estado="ENVIADA", subtotal=Decimal("20.00"), impuesto=Decimal("2.60"),
        total=Decimal("22.60"), fecha_vencimiento=timezone.now() + timedelta(days=5),
    )


class FiltrosProgresoTests(TestCase):
    def test_progreso_por_estado(self):
        self.assertEqual(progreso_valor("EN_PRODUCCION"), 75)
        self.assertEqual(progreso_clase("EN_PRODUCCION"), "w-75")
        self.assertEqual(progreso_clase("PENDIENTE"), "w-25")
        self.assertEqual(progreso_clase("FINALIZADO"), "w-100")
        self.assertEqual(progreso_valor("DESCONOCIDO"), 0)


class PanelClienteTests(TestCase):
    def setUp(self):
        self.usuario, self.cliente = crear_cliente("cliente@example.com")
        self.otro, self.cliente_otro = crear_cliente("otro@example.com")

    def test_panel_vacio_responde_con_estados_vacios(self):
        iniciar_sesion(self.client, self.usuario)
        respuesta = self.client.get(reverse("customer:panel"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "No tiene pedidos en curso.")
        self.assertContains(respuesta, "No tiene facturas con saldo pendiente.")

    def test_panel_muestra_solo_los_datos_del_cliente(self):
        cotizacion_enviada(self.cliente, "COT-P-MIA")
        cotizacion_enviada(self.cliente_otro, "COT-P-AJENA")
        Encargo.objects.create(cliente=self.cliente, codigo="ENC-P-MIO", descripcion="x", estado="EN_PRODUCCION")
        Encargo.objects.create(cliente=self.cliente_otro, codigo="ENC-P-AJENO", descripcion="x")
        Encargo.objects.create(cliente=self.cliente, codigo="ENC-P-FIN", descripcion="x", estado="ENTREGADO")
        Factura.objects.create(
            cliente=self.cliente, numero_factura="FAC-P-MIA", nombre_facturacion="C", subtotal=Decimal("50.00"),
            total=Decimal("50.00"), saldo_pendiente=Decimal("30.00"),
        )
        crear_solicitud(self.cliente, "Duda propia", "Descripcion suficiente aqui.")
        crear_solicitud(self.cliente_otro, "Duda ajena", "Descripcion suficiente aqui.")
        notificar(self.usuario, "Aviso propio", "x", "cotizacion", 1)
        notificar(self.otro, "Aviso ajeno", "x", "cotizacion", 1)
        iniciar_sesion(self.client, self.usuario)
        respuesta = self.client.get(reverse("customer:panel"))
        for visible in ("COT-P-MIA", "ENC-P-MIO", "w-75", "FAC-P-MIA", "Duda propia", "Aviso propio"):
            self.assertContains(respuesta, visible)
        for oculto in ("COT-P-AJENA", "ENC-P-AJENO", "Duda ajena", "Aviso ajeno"):
            self.assertNotContains(respuesta, oculto)
        self.assertEqual([e.codigo for e in respuesta.context["pedidos"]], ["ENC-P-MIO"])
        self.assertEqual(respuesta.context["kpis"]["saldo_pendiente"], Decimal("30.00"))
        self.assertEqual(respuesta.context["kpis"]["pedidos_en_curso"], 1)

    def test_el_panel_no_tiene_style_y_requiere_rol_cliente(self):
        iniciar_sesion(self.client, self.usuario)
        self.assertNotIn(" style=", self.client.get(reverse("customer:panel")).content.decode())
        self.client.logout()
        self.assertEqual(self.client.get(reverse("customer:panel")).status_code, 302)
