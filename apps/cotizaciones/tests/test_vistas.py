from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.cotizaciones.models import Cotizacion, EstadoCotizacion
from apps.cotizaciones.tests.utiles import (
    AlmacenTemporalMixin,
    archivo_stl,
    crear_cliente,
    crear_personal,
    crear_servicio,
)
from apps.usuarios.tests.utiles import iniciar_sesion


@override_settings(TASA_IMPUESTO=Decimal("0.13"))
class VistasCotizacionTests(AlmacenTemporalMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.usuario, self.cliente = crear_cliente("cliente@example.com")
        self.otro, _ = crear_cliente("otro@example.com")
        self.operador = crear_personal("operador@example.com")
        self.servicio = crear_servicio()

    def solicitar_por_vista(self, **extra):
        datos = {
            "servicio": self.servicio.pk,
            "cantidad": "2",
            "descripcion": "Pieza",
            "solicitud": "Necesito una pieza impresa.",
            "archivos": [archivo_stl()],
            "precio_unitario": "0.01",
        }
        datos.update(extra)
        iniciar_sesion(self.client, self.usuario)
        return self.client.post(reverse("customer:cotizar"), datos)

    def test_cliente_solicita_y_el_precio_no_lo_define_el_navegador(self):
        respuesta = self.solicitar_por_vista()
        cotizacion = Cotizacion.objects.get()
        self.assertRedirects(
            respuesta, reverse("customer:cotizacion", args=[cotizacion.pk]), fetch_redirect_response=False
        )
        self.assertEqual(cotizacion.detalles.get().precio_unitario, Decimal("10.00"))
        self.assertEqual(cotizacion.archivos.count(), 1)

    def test_servicio_que_requiere_archivo_lo_exige(self):
        exigente = crear_servicio("Con archivo", requiere_archivo=True)
        respuesta = self.solicitar_por_vista(servicio=exigente.pk, archivos=[])
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Cotizacion.objects.count(), 0)

    def test_otro_cliente_no_ve_ni_descarga_ni_responde(self):
        self.solicitar_por_vista()
        cotizacion = Cotizacion.objects.get()
        archivo = cotizacion.archivos.get()
        self.client.logout()
        iniciar_sesion(self.client, self.otro)
        self.assertEqual(self.client.get(reverse("customer:cotizacion", args=[cotizacion.pk])).status_code, 404)
        self.assertEqual(
            self.client.get(reverse("customer:cotizacion_archivo", args=[cotizacion.pk, archivo.pk])).status_code, 404
        )
        self.assertEqual(
            self.client.post(reverse("customer:cotizacion_accion", args=[cotizacion.pk, "aceptar"])).status_code, 404
        )

    def test_descarga_del_propietario_y_del_operador(self):
        self.solicitar_por_vista()
        cotizacion = Cotizacion.objects.get()
        archivo = cotizacion.archivos.get()
        respuesta = self.client.get(reverse("customer:cotizacion_archivo", args=[cotizacion.pk, archivo.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("attachment", respuesta["Content-Disposition"])
        b"".join(respuesta.streaming_content)
        self.client.logout()
        iniciar_sesion(self.client, self.operador)
        respuesta = self.client.get(reverse("operator:cotizacion_archivo", args=[cotizacion.pk, archivo.pk]))
        self.assertEqual(respuesta.status_code, 200)
        b"".join(respuesta.streaming_content)

    def test_cliente_no_accede_al_area_del_operador(self):
        self.solicitar_por_vista()
        cotizacion = Cotizacion.objects.get()
        self.assertEqual(self.client.get(reverse("operator:cotizaciones")).status_code, 403)
        self.assertEqual(self.client.get(reverse("operator:cotizacion", args=[cotizacion.pk])).status_code, 403)
        self.assertEqual(
            self.client.post(reverse("operator:cotizacion_accion", args=[cotizacion.pk, "enviar"])).status_code, 403
        )

    def test_flujo_por_vistas(self):
        self.solicitar_por_vista()
        cotizacion = Cotizacion.objects.get()
        detalle = cotizacion.detalles.get()
        self.client.logout()
        iniciar_sesion(self.client, self.operador)
        self.assertEqual(self.client.get(reverse("operator:cotizaciones")).status_code, 200)
        self.assertEqual(self.client.get(reverse("operator:cotizacion", args=[cotizacion.pk])).status_code, 200)

        respuesta = self.client.post(
            reverse("operator:cotizacion", args=[cotizacion.pk]),
            {
                "lineas-TOTAL_FORMS": "1",
                "lineas-INITIAL_FORMS": "1",
                "lineas-0-id": str(detalle.pk),
                "lineas-0-cantidad": "2",
                "lineas-0-precio_unitario": "15.00",
                "lineas-0-descuento": "0",
                "observaciones": "Listo para producir.",
                "plazo_entrega_dias": "5",
            },
        )
        self.assertEqual(respuesta.status_code, 302)
        cotizacion.refresh_from_db()
        self.assertEqual(cotizacion.estado, EstadoCotizacion.BORRADOR)
        self.assertEqual(cotizacion.subtotal, Decimal("30.00"))

        self.client.post(reverse("operator:cotizacion_accion", args=[cotizacion.pk, "enviar"]))
        cotizacion.refresh_from_db()
        self.assertEqual(cotizacion.estado, EstadoCotizacion.ENVIADA)

        self.client.logout()
        iniciar_sesion(self.client, self.usuario)
        self.assertEqual(self.client.get(reverse("customer:cotizacion", args=[cotizacion.pk])).status_code, 200)
        self.client.post(reverse("customer:cotizacion_accion", args=[cotizacion.pk, "aceptar"]))
        cotizacion.refresh_from_db()
        self.assertEqual(cotizacion.estado, EstadoCotizacion.ACEPTADA)
