import os
import shutil
import tempfile
from decimal import Decimal
from io import BytesIO
from unittest import mock

from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from apps.catalogo.forms.catalogo import ProductoForm
from apps.catalogo.models import Producto
from apps.catalogo.services.catalogo import StockInsuficiente, descontar_stock
from apps.cotizaciones.tests.utiles import crear_cliente, crear_servicio
from apps.encargos.models import Encargo, EncargoDetalle


def crear_producto(sku="DISP-001", **extra):
    datos = {"nombre": "Producto de prueba", "precio": Decimal("5.00"), "stock": 10, "stock_minimo": 2}
    datos.update(extra)
    return Producto.objects.create(sku=sku, **datos)


def imagen(nombre="foto.png", formato="PNG"):
    buffer = BytesIO()
    Image.new("RGB", (4, 4), "red").save(buffer, formato)
    return SimpleUploadedFile(nombre, buffer.getvalue())


class DisponibilidadTests(TestCase):
    def test_producto_agotado_se_muestra_pero_no_se_puede_comprar(self):
        producto = crear_producto("AGO-001", stock=0)
        self.assertEqual(producto.disponibilidad_codigo, "agotado")
        with self.assertRaises(StockInsuficiente):
            descontar_stock({producto.pk: 1})


class SnapshotHistoricoTests(TestCase):
    def test_detalle_conserva_descripcion_y_precio_aunque_cambie_el_producto(self):
        _, cliente = crear_cliente("snapshot@example.com")
        producto = crear_producto("SNAP-001")
        encargo = Encargo.objects.create(
            cliente=cliente,
            codigo="ENC-SNAP-1",
            descripcion="Compra de prueba",
            subtotal=Decimal("10.00"),
            descuento=Decimal("0.00"),
            impuesto=Decimal("1.30"),
            total=Decimal("11.30"),
        )
        detalle = EncargoDetalle.objects.create(
            encargo=encargo,
            producto=producto,
            descripcion="Producto de prueba (SNAP-001)",
            cantidad=Decimal("2"),
            precio_unitario=Decimal("5.00"),
            descuento=Decimal("0.00"),
            impuesto=Decimal("1.30"),
            subtotal=Decimal("10.00"),
        )
        producto.precio = Decimal("9.99")
        producto.nombre = "Nombre nuevo"
        producto.save()
        detalle.refresh_from_db()
        self.assertEqual(detalle.precio_unitario, Decimal("5.00"))
        self.assertEqual(detalle.descripcion, "Producto de prueba (SNAP-001)")

    def test_detalle_no_puede_referirse_a_servicio_y_producto(self):
        _, cliente = crear_cliente("xor@example.com")
        encargo = Encargo.objects.create(cliente=cliente, codigo="ENC-XOR-1", descripcion="x")
        detalle = EncargoDetalle(
            encargo=encargo,
            producto=crear_producto("XOR-001"),
            servicio=crear_servicio("Servicio xor"),
            descripcion="x",
            cantidad=Decimal("1"),
            precio_unitario=Decimal("1.00"),
            subtotal=Decimal("1.00"),
        )
        with self.assertRaises(ValidationError):
            detalle.full_clean()


class ImagenesProductoTests(TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        contexto = override_settings(MEDIA_ROOT=self._tmp)
        contexto.enable()
        self.addCleanup(contexto.disable)
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)

    def datos(self, **extra):
        datos = {"sku": "IMG-001", "nombre": "Con imagen", "precio": "3.00", "stock_minimo": "0", "activo": "on"}
        datos.update(extra)
        return datos

    def test_guardado_fallido_no_deja_archivos_huerfanos(self):
        form = ProductoForm(self.datos(stock="1"), {"imagen_archivo": imagen()})
        self.assertTrue(form.is_valid(), form.errors)
        with mock.patch.object(Producto, "save", side_effect=RuntimeError("fallo")):
            with self.assertRaises(RuntimeError):
                form.save()
        restantes = [f for _, _, archivos in os.walk(self._tmp) for f in archivos]
        self.assertEqual(restantes, [])

    def test_reemplazo_elimina_la_imagen_anterior(self):
        primero = ProductoForm(self.datos(stock="1"), {"imagen_archivo": imagen()})
        self.assertTrue(primero.is_valid(), primero.errors)
        producto = primero.save()
        anterior = producto.imagen
        self.assertTrue(default_storage.exists(anterior))
        segundo = ProductoForm(self.datos(), {"imagen_archivo": imagen("otra.png")}, instance=producto)
        self.assertTrue(segundo.is_valid(), segundo.errors)
        producto = segundo.save()
        self.assertNotEqual(producto.imagen, anterior)
        self.assertFalse(default_storage.exists(anterior))
        self.assertTrue(default_storage.exists(producto.imagen))

    def test_quitar_imagen_la_elimina(self):
        producto = ProductoForm(self.datos(stock="1"), {"imagen_archivo": imagen()})
        producto.is_valid()
        producto = producto.save()
        ruta = producto.imagen
        form = ProductoForm(self.datos(quitar_imagen="on"), instance=producto)
        self.assertTrue(form.is_valid(), form.errors)
        producto = form.save()
        self.assertIsNone(producto.imagen)
        self.assertFalse(default_storage.exists(ruta))

    def test_rechaza_archivo_que_no_es_imagen(self):
        falso = SimpleUploadedFile("foto.png", b"esto no es una imagen")
        self.assertFalse(ProductoForm(self.datos(stock="1"), {"imagen_archivo": falso}).is_valid())

    def test_rechaza_extension_no_permitida(self):
        self.assertFalse(
            ProductoForm(self.datos(stock="1"), {"imagen_archivo": imagen("foto.gif", "GIF")}).is_valid()
        )
