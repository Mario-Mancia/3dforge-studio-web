from decimal import Decimal

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.cotizaciones.services import cotizaciones as cot
from apps.cotizaciones.tests.utiles import AlmacenTemporalMixin, crear_cliente, crear_personal, crear_servicio
from apps.encargos.services import encargos as srv_enc
from apps.notificaciones.models import Notificacion
from apps.notificaciones.services.notificaciones import (
    marcar_leida,
    marcar_todas,
    notificar,
    notificar_personal,
)
from apps.usuarios.tests.utiles import iniciar_sesion


class ServicioNotificacionesTests(TestCase):
    def setUp(self):
        self.usuario, self.cliente = crear_cliente("cliente@example.com")
        self.otro, _ = crear_cliente("otro@example.com")

    def test_evita_duplicados_ante_reintentos(self):
        a = notificar(self.usuario, "Aviso", "Mensaje", "cotizacion", 1)
        b = notificar(self.usuario, "Aviso", "Mensaje", "cotizacion", 1)
        self.assertEqual(a.pk, b.pk)
        self.assertEqual(Notificacion.objects.filter(usuario=self.usuario).count(), 1)
        notificar(self.usuario, "Aviso", "Mensaje", "cotizacion", 2)
        self.assertEqual(Notificacion.objects.filter(usuario=self.usuario).count(), 2)

    def test_marcar_leidas_solo_afecta_al_propietario(self):
        n = notificar(self.usuario, "Aviso", "Mensaje", "cotizacion", 1)
        self.assertEqual(marcar_leida(self.otro, n.pk), 0)
        n.refresh_from_db()
        self.assertFalse(n.leida)
        self.assertEqual(marcar_leida(self.usuario, n.pk), 1)
        notificar(self.usuario, "Otro", "Mensaje", "cotizacion", 3)
        self.assertEqual(marcar_todas(self.usuario), 1)

    def test_correo_se_envia_al_confirmar(self):
        with self.captureOnCommitCallbacks(execute=True):
            notificar(self.usuario, "Con correo", "Hola", "cotizacion", 9, correo=True)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Con correo", mail.outbox[0].subject)

    def test_inactivos_no_reciben(self):
        self.usuario.is_active = False
        self.assertIsNone(notificar(self.usuario, "x", "y", "cotizacion", 1))

    def test_notificar_personal_llega_a_operadores(self):
        operador = crear_personal("op@example.com")
        notificar_personal("Para el equipo", "Mensaje", "cotizacion", 5)
        self.assertTrue(Notificacion.objects.filter(usuario=operador, titulo="Para el equipo").exists())
        self.assertFalse(Notificacion.objects.filter(usuario=self.usuario).exists())


@override_settings(TASA_IMPUESTO=Decimal("0.13"))
class EventosTests(AlmacenTemporalMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.usuario, self.cliente = crear_cliente("cliente@example.com")
        self.operador = crear_personal("operador@example.com")
        self.servicio = crear_servicio()

    def solicitar(self):
        return cot.solicitar_cotizacion(
            cliente=self.cliente, usuario=self.usuario, servicio=self.servicio, cantidad=Decimal("2"),
            descripcion="Pieza", solicitud="Necesito una pieza de prueba.",
        )

    def lineas(self, c):
        return [{"id": d.pk, "cantidad": Decimal("2"), "precio_unitario": Decimal("15.00"), "descuento": Decimal("0")} for d in c.detalles.all()]

    def test_flujo_de_cotizacion_y_encargo_genera_notificaciones(self):
        c = self.solicitar()
        self.assertTrue(Notificacion.objects.filter(usuario=self.operador, tipo="cotizacion", referencia_id=c.pk).exists())
        self.assertIn(c.codigo, Notificacion.objects.get(usuario=self.operador, referencia_id=c.pk).titulo)
        cot.revisar_cotizacion(c.pk, self.operador, self.lineas(c))
        with self.captureOnCommitCallbacks(execute=True):
            cot.enviar_cotizacion(c.pk, self.operador)
        self.assertTrue(Notificacion.objects.filter(usuario=self.usuario, titulo__contains="disponible").exists())
        self.assertEqual(len(mail.outbox), 1)
        cot.aceptar_cotizacion(c.pk, self.usuario)
        self.assertTrue(Notificacion.objects.filter(usuario=self.operador, titulo__contains="aceptada").exists())
        encargo = srv_enc.crear_desde_cotizacion(c.pk, self.operador)
        self.assertTrue(Notificacion.objects.filter(usuario=self.usuario, tipo="encargo", referencia_id=encargo.pk).exists())
        srv_enc.cambiar_estado(encargo.pk, self.operador, "APROBADO")
        self.assertTrue(Notificacion.objects.filter(usuario=self.usuario, titulo__contains="Aprobado").exists())

    def test_cada_usuario_ve_solo_sus_notificaciones(self):
        notificar(self.usuario, "Mia", "x", "cotizacion", 1)
        otro, _ = crear_cliente("otro@example.com")
        notificar(otro, "Ajena", "x", "cotizacion", 1)
        iniciar_sesion(self.client, self.usuario)
        respuesta = self.client.get(reverse("customer:notificaciones"))
        self.assertContains(respuesta, "Mia")
        self.assertNotContains(respuesta, "Ajena")
        self.client.post(reverse("customer:notificacion_accion", args=["leer"]), {"pk": Notificacion.objects.get(usuario=otro).pk})
        self.assertFalse(Notificacion.objects.get(usuario=otro).leida)
        self.client.post(reverse("customer:notificacion_accion", args=["todas"]))
        self.assertTrue(Notificacion.objects.get(usuario=self.usuario).leida)

    def test_contador_en_la_navegacion(self):
        notificar(self.usuario, "Pendiente", "x", "cotizacion", 1)
        iniciar_sesion(self.client, self.usuario)
        respuesta = self.client.get(reverse("customer:panel"))
        self.assertEqual(respuesta.context["notificaciones_no_leidas"], 1)
