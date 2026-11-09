from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.catalogo.models import Producto
from apps.core.storage import almacenamiento_privado
from apps.cotizaciones.services import cotizaciones as cot
from apps.cotizaciones.tests.utiles import (
    AlmacenTemporalMixin,
    archivo_stl,
    crear_cliente,
    crear_personal,
    crear_servicio,
)
from apps.encargos.models import Encargo, EncargoDetalle, EstadoEncargo
from apps.encargos.services import encargos as srv
from apps.usuarios.models import Empleado
from apps.usuarios.tests.utiles import iniciar_sesion


@override_settings(TASA_IMPUESTO=Decimal("0.13"))
class BaseEncargoTests(AlmacenTemporalMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.usuario, self.cliente = crear_cliente("cliente@example.com")
        self.operador = crear_personal("operador@example.com")
        self.servicio = crear_servicio()

    def cotizacion_aceptada(self, archivos=()):
        c = cot.solicitar_cotizacion(
            cliente=self.cliente, usuario=self.usuario, servicio=self.servicio, cantidad=Decimal("2"),
            descripcion="Pieza", solicitud="Necesito una pieza.", archivos=list(archivos),
        )
        lineas = [
            {"id": d.pk, "cantidad": Decimal("2"), "precio_unitario": Decimal("15.00"), "descuento": Decimal("0")}
            for d in c.detalles.all()
        ]
        cot.revisar_cotizacion(c.pk, self.operador, lineas, plazo_entrega_dias=5)
        cot.enviar_cotizacion(c.pk, self.operador)
        cot.aceptar_cotizacion(c.pk, self.usuario)
        c.refresh_from_db()
        return c


class CreacionTests(BaseEncargoTests):
    def test_crea_encargo_con_copias_historial_y_es_idempotente(self):
        c = self.cotizacion_aceptada(archivos=[archivo_stl()])
        e = srv.crear_desde_cotizacion(c.pk, self.operador)
        self.assertTrue(e.codigo.startswith("ENC-"))
        self.assertEqual(e.estado, EstadoEncargo.PENDIENTE)
        self.assertEqual(e.total, c.total)
        self.assertIsNotNone(e.fecha_entrega_estimada)
        self.assertEqual(e.detalles.count(), 1)
        archivo = e.detalles.get().archivos.get()
        self.assertTrue(almacenamiento_privado.exists(archivo.ruta_archivo))
        self.assertEqual(e.historial.count(), 1)
        self.assertEqual(srv.crear_desde_cotizacion(c.pk, self.operador).pk, e.pk)
        self.assertEqual(Encargo.objects.count(), 1)

    def test_solo_desde_cotizacion_aceptada(self):
        c = cot.solicitar_cotizacion(
            cliente=self.cliente, usuario=self.usuario, servicio=self.servicio, cantidad=Decimal("1"),
            descripcion="x", solicitud="Una solicitud cualquiera.",
        )
        with self.assertRaises(srv.ErrorEncargo):
            srv.crear_desde_cotizacion(c.pk, self.operador)

    def test_cliente_no_crea_encargos(self):
        c = self.cotizacion_aceptada()
        with self.assertRaises(PermissionDenied):
            srv.crear_desde_cotizacion(c.pk, self.usuario)


class FlujoTests(BaseEncargoTests):
    def setUp(self):
        super().setUp()
        self.encargo = srv.crear_desde_cotizacion(self.cotizacion_aceptada().pk, self.operador)

    def test_ciclo_completo_con_historial(self):
        for estado in ("APROBADO", "EN_PRODUCCION", "FINALIZADO", "ENTREGADO"):
            srv.cambiar_estado(self.encargo.pk, self.operador, estado, "ok")
        self.encargo.refresh_from_db()
        self.assertEqual(self.encargo.estado, EstadoEncargo.ENTREGADO)
        self.assertIsNotNone(self.encargo.fecha_entrega_real)
        self.assertEqual(self.encargo.historial.count(), 5)

    def test_transicion_invalida_y_estados_cerrados(self):
        with self.assertRaises(srv.TransicionInvalida):
            srv.cambiar_estado(self.encargo.pk, self.operador, "ENTREGADO")
        srv.cambiar_estado(self.encargo.pk, self.operador, "CANCELADO")
        with self.assertRaises(srv.TransicionInvalida):
            srv.cambiar_estado(self.encargo.pk, self.operador, "APROBADO")

    def test_cliente_cancela_solo_pendiente_y_solo_lo_suyo(self):
        otro, _ = crear_cliente("otro@example.com")
        with self.assertRaises(PermissionDenied):
            srv.cancelar_por_cliente(self.encargo.pk, otro)
        srv.cambiar_estado(self.encargo.pk, self.operador, "APROBADO")
        with self.assertRaises(srv.TransicionInvalida):
            srv.cancelar_por_cliente(self.encargo.pk, self.usuario)

    def test_asignar_responsable(self):
        activo = Empleado.objects.create(usuario=self.operador, codigo_empleado="EMP-001", cargo="Operador")
        srv.asignar_responsable(self.encargo.pk, self.operador, activo.pk)
        self.encargo.refresh_from_db()
        self.assertEqual(self.encargo.empleado_responsable, activo)
        Empleado.objects.filter(pk=activo.pk).update(activo=False)
        with self.assertRaises(srv.ErrorEncargo):
            srv.asignar_responsable(self.encargo.pk, self.operador, activo.pk)

    def test_subir_archivo_valida_contenido(self):
        detalle = self.encargo.detalles.get()
        srv.subir_archivo(self.encargo.pk, detalle.pk, self.operador, archivo_stl("avance.stl"))
        self.assertEqual(detalle.archivos.count(), 1)
        with self.assertRaises(ValidationError):
            srv.subir_archivo(self.encargo.pk, detalle.pk, self.operador, SimpleUploadedFile("x.png", b"no es png"))


class StockTests(BaseEncargoTests):
    def test_cancelar_compra_directa_repone_stock_una_sola_vez(self):
        producto = Producto.objects.create(sku="CAN-001", nombre="p", precio=Decimal("5.00"), stock=3)
        encargo = Encargo.objects.create(cliente=self.cliente, codigo="ENC-T-1", descripcion="Compra")
        EncargoDetalle.objects.create(
            encargo=encargo, producto=producto, descripcion="p", cantidad=Decimal("2"),
            precio_unitario=Decimal("5.00"), subtotal=Decimal("10.00"),
        )
        srv.cambiar_estado(encargo.pk, self.operador, "CANCELADO")
        producto.refresh_from_db()
        self.assertEqual(producto.stock, 5)
        with self.assertRaises(srv.TransicionInvalida):
            srv.cambiar_estado(encargo.pk, self.operador, "CANCELADO")
        producto.refresh_from_db()
        self.assertEqual(producto.stock, 5)


class VistasTests(BaseEncargoTests):
    def test_flujo_por_vistas_y_aislamiento(self):
        c = self.cotizacion_aceptada(archivos=[archivo_stl()])
        iniciar_sesion(self.client, self.operador)
        respuesta = self.client.post(reverse("operator:cotizacion_encargo", args=[c.pk]))
        encargo = Encargo.objects.get()
        self.assertRedirects(respuesta, reverse("operator:encargo", args=[encargo.pk]), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse("operator:encargos")).status_code, 200)
        self.assertEqual(self.client.get(reverse("operator:encargo", args=[encargo.pk])).status_code, 200)
        self.client.post(reverse("operator:encargo_accion", args=[encargo.pk, "estado"]), {"estado": "APROBADO", "comentario": "ok"})
        encargo.refresh_from_db()
        self.assertEqual(encargo.estado, EstadoEncargo.APROBADO)
        archivo = encargo.detalles.get().archivos.get()
        resp = self.client.get(reverse("operator:encargo_archivo", args=[encargo.pk, archivo.pk]))
        self.assertEqual(resp.status_code, 200)
        b"".join(resp.streaming_content)

        self.client.logout()
        iniciar_sesion(self.client, self.usuario)
        self.assertEqual(self.client.get(reverse("customer:pedidos")).status_code, 200)
        self.assertEqual(self.client.get(reverse("customer:pedido", args=[encargo.pk])).status_code, 200)
        resp = self.client.get(reverse("customer:pedido_archivo", args=[encargo.pk, archivo.pk]))
        self.assertEqual(resp.status_code, 200)
        b"".join(resp.streaming_content)
        self.assertEqual(self.client.get(reverse("operator:encargos")).status_code, 403)

        otro, _ = crear_cliente("otro@example.com")
        self.client.logout()
        iniciar_sesion(self.client, otro)
        self.assertEqual(self.client.get(reverse("customer:pedido", args=[encargo.pk])).status_code, 404)
        self.assertEqual(
            self.client.get(reverse("customer:pedido_archivo", args=[encargo.pk, archivo.pk])).status_code, 404
        )
        self.assertEqual(self.client.post(reverse("customer:pedido_cancelar", args=[encargo.pk])).status_code, 404)
