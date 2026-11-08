import os
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.core.storage import almacenamiento_privado
from apps.cotizaciones.models import ArchivoCotizacion, Cotizacion, EstadoCotizacion
from apps.cotizaciones.services import cotizaciones as srv
from apps.cotizaciones.tests.utiles import (
    AlmacenTemporalMixin,
    archivo_stl,
    crear_cliente,
    crear_personal,
    crear_servicio,
)
from apps.crm.models import InteraccionCliente


@override_settings(TASA_IMPUESTO=Decimal("0.13"))
class BaseCotizacionTests(AlmacenTemporalMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.usuario, self.cliente = crear_cliente("cliente@example.com")
        self.operador = crear_personal("operador@example.com")
        self.servicio = crear_servicio()

    def solicitar(self, **extra):
        datos = {
            "cliente": self.cliente,
            "usuario": self.usuario,
            "servicio": self.servicio,
            "cantidad": Decimal("2"),
            "descripcion": "Pieza de prueba",
            "solicitud": "Necesito imprimir una pieza de prueba.",
        }
        datos.update(extra)
        return srv.solicitar_cotizacion(**datos)

    def lineas(self, cotizacion, precio="15.00", cantidad="2", descuento="0"):
        return [
            {
                "id": d.pk,
                "cantidad": Decimal(cantidad),
                "precio_unitario": Decimal(precio),
                "descuento": Decimal(descuento),
            }
            for d in cotizacion.detalles.all()
        ]

    def enviada(self):
        cotizacion = self.solicitar()
        srv.revisar_cotizacion(cotizacion.pk, self.operador, self.lineas(cotizacion))
        srv.enviar_cotizacion(cotizacion.pk, self.operador)
        cotizacion.refresh_from_db()
        return cotizacion


class SolicitudTests(BaseCotizacionTests):
    def test_importes_los_calcula_el_servidor(self):
        cotizacion = self.solicitar()
        self.assertEqual(cotizacion.estado, EstadoCotizacion.SOLICITADA)
        self.assertTrue(cotizacion.codigo.startswith("COT-"))
        self.assertEqual(cotizacion.subtotal, Decimal("20.00"))
        self.assertEqual(cotizacion.impuesto, Decimal("2.60"))
        self.assertEqual(cotizacion.total, Decimal("22.60"))
        self.assertEqual(cotizacion.detalles.get().precio_unitario, Decimal("10.00"))

    def test_codigos_unicos(self):
        self.assertNotEqual(self.solicitar().codigo, self.solicitar().codigo)

    def test_servicio_inactivo_es_rechazado(self):
        with self.assertRaises(srv.ErrorCotizacion):
            self.solicitar(servicio=crear_servicio("Inactivo", activo=False))

    def test_archivo_se_guarda_en_almacenamiento_privado(self):
        cotizacion = self.solicitar(archivos=[archivo_stl()])
        archivo = cotizacion.archivos.get()
        self.assertEqual(archivo.formato, "STL")
        self.assertEqual(archivo.nombre_archivo, "pieza.stl")
        self.assertFalse(archivo.ruta_archivo.startswith("/"))
        self.assertTrue(almacenamiento_privado.exists(archivo.ruta_archivo))

    def test_extension_no_permitida(self):
        with self.assertRaises(ValidationError):
            self.solicitar(archivos=[SimpleUploadedFile("virus.exe", b"MZ" + b"\x00" * 20)])
        self.assertEqual(Cotizacion.objects.count(), 0)

    def test_contenido_que_no_corresponde_al_formato(self):
        with self.assertRaises(ValidationError):
            self.solicitar(archivos=[SimpleUploadedFile("foto.png", b"esto no es un png")])

    @override_settings(MAX_ARCHIVO_BYTES=10)
    def test_archivo_demasiado_grande(self):
        with self.assertRaises(ValidationError):
            self.solicitar(archivos=[archivo_stl()])

    @override_settings(COTIZACION_MAX_ARCHIVOS=1)
    def test_limite_de_archivos(self):
        with self.assertRaises(srv.ErrorCotizacion):
            self.solicitar(archivos=[archivo_stl("a.stl"), archivo_stl("b.stl")])

    def test_fallo_posterior_no_deja_archivos_huerfanos(self):
        with mock.patch.object(ArchivoCotizacion, "save", side_effect=RuntimeError("fallo")):
            with self.assertRaises(RuntimeError):
                self.solicitar(archivos=[archivo_stl()])
        restantes = [f for _, _, archivos in os.walk(self._tmp) for f in archivos]
        self.assertEqual(restantes, [])


class FlujoTests(BaseCotizacionTests):
    def test_flujo_completo(self):
        cotizacion = self.solicitar()
        srv.revisar_cotizacion(
            cotizacion.pk,
            self.operador,
            self.lineas(cotizacion, precio="15.00", cantidad="2", descuento="5.00"),
            observaciones="Entrega en taller.",
            plazo_entrega_dias=7,
        )
        cotizacion.refresh_from_db()
        self.assertEqual(cotizacion.estado, EstadoCotizacion.BORRADOR)
        self.assertEqual(cotizacion.usuario_responsable, self.operador)
        self.assertEqual(cotizacion.subtotal, Decimal("30.00"))
        self.assertEqual(cotizacion.descuento, Decimal("5.00"))
        self.assertEqual(cotizacion.impuesto, Decimal("3.25"))
        self.assertEqual(cotizacion.total, Decimal("28.25"))

        srv.enviar_cotizacion(cotizacion.pk, self.operador)
        cotizacion.refresh_from_db()
        self.assertEqual(cotizacion.estado, EstadoCotizacion.ENVIADA)
        self.assertGreater(cotizacion.fecha_vencimiento, timezone.now())

        srv.aceptar_cotizacion(cotizacion.pk, self.usuario)
        cotizacion.refresh_from_db()
        self.assertEqual(cotizacion.estado, EstadoCotizacion.ACEPTADA)
        self.assertGreaterEqual(InteraccionCliente.objects.filter(cliente=self.cliente).count(), 3)

    def test_no_se_envia_sin_revision(self):
        cotizacion = self.solicitar()
        with self.assertRaises(srv.TransicionInvalida):
            srv.enviar_cotizacion(cotizacion.pk, self.operador)

    def test_cliente_no_acepta_una_solicitud_sin_enviar(self):
        cotizacion = self.solicitar()
        with self.assertRaises(srv.TransicionInvalida):
            srv.aceptar_cotizacion(cotizacion.pk, self.usuario)

    def test_otro_cliente_no_puede_aceptar(self):
        otro, _ = crear_cliente("otro@example.com")
        cotizacion = self.enviada()
        with self.assertRaises(PermissionDenied):
            srv.aceptar_cotizacion(cotizacion.pk, otro)

    def test_cliente_no_puede_revisar_ni_enviar(self):
        cotizacion = self.solicitar()
        with self.assertRaises(PermissionDenied):
            srv.revisar_cotizacion(cotizacion.pk, self.usuario, self.lineas(cotizacion))
        with self.assertRaises(PermissionDenied):
            srv.enviar_cotizacion(cotizacion.pk, self.usuario)

    def test_rechazada_no_se_puede_aceptar(self):
        cotizacion = self.enviada()
        srv.rechazar_cotizacion(cotizacion.pk, self.usuario)
        with self.assertRaises(srv.TransicionInvalida):
            srv.aceptar_cotizacion(cotizacion.pk, self.usuario)

    def test_cancelada_no_se_puede_aceptar(self):
        cotizacion = self.enviada()
        srv.cancelar_cotizacion(cotizacion.pk, self.operador)
        with self.assertRaises(srv.TransicionInvalida):
            srv.aceptar_cotizacion(cotizacion.pk, self.usuario)

    def test_vencida_no_se_acepta_y_queda_marcada(self):
        cotizacion = self.enviada()
        Cotizacion.objects.filter(pk=cotizacion.pk).update(fecha_vencimiento=timezone.now() - timedelta(days=1))
        with self.assertRaises(srv.CotizacionVencida):
            srv.aceptar_cotizacion(cotizacion.pk, self.usuario)
        cotizacion.refresh_from_db()
        self.assertEqual(cotizacion.estado, EstadoCotizacion.VENCIDA)

    def test_vencimiento_masivo(self):
        vencida, vigente = self.enviada(), self.enviada()
        Cotizacion.objects.filter(pk=vencida.pk).update(fecha_vencimiento=timezone.now() - timedelta(days=1))
        self.assertEqual(srv.vencer_cotizaciones_vencidas(), 1)
        vigente.refresh_from_db()
        self.assertEqual(vigente.estado, EstadoCotizacion.ENVIADA)

    def test_cliente_cancela_solo_antes_de_la_revision(self):
        cotizacion = self.solicitar()
        srv.revisar_cotizacion(cotizacion.pk, self.operador, self.lineas(cotizacion))
        with self.assertRaises(srv.TransicionInvalida):
            srv.cancelar_cotizacion(cotizacion.pk, self.usuario)
        nueva = self.solicitar()
        srv.cancelar_cotizacion(nueva.pk, self.usuario)
        nueva.refresh_from_db()
        self.assertEqual(nueva.estado, EstadoCotizacion.CANCELADA)

    def test_revision_exige_todas_las_lineas_propias(self):
        cotizacion = self.solicitar()
        lineas = self.lineas(cotizacion)
        lineas[0]["id"] = 999999
        with self.assertRaises(srv.ErrorCotizacion):
            srv.revisar_cotizacion(cotizacion.pk, self.operador, lineas)

    def test_descuento_mayor_al_importe_es_rechazado(self):
        cotizacion = self.solicitar()
        with self.assertRaises(ValidationError):
            srv.revisar_cotizacion(
                cotizacion.pk, self.operador, self.lineas(cotizacion, precio="1.00", cantidad="1", descuento="50")
            )
