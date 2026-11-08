from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from apps.catalogo.models import CategoriaServicio, Producto, Servicio
from apps.catalogo.services.catalogo import (
    ProductoNoDisponible,
    StockInsuficiente,
    ajustar_stock,
    descontar_stock,
    reponer_stock,
)
from apps.usuarios.constants import GRUPO_ADMINISTRADOR, GRUPO_OPERADOR
from apps.usuarios.tests.utiles import crear_usuario, iniciar_sesion


def crear_producto(sku="TEST-001", **extra):
    datos = {"nombre": "Producto de prueba", "precio": Decimal("5.00"), "stock": 10, "stock_minimo": 2}
    datos.update(extra)
    return Producto.objects.create(sku=sku, **datos)


class CatalogoPublicoTests(TestCase):
    def test_solo_se_listan_productos_activos(self):
        crear_producto("ACT-001", nombre="Visible")
        crear_producto("INA-001", nombre="Oculto", activo=False)
        respuesta = self.client.get(reverse("guest:catalogo"))
        self.assertContains(respuesta, "Visible")
        self.assertNotContains(respuesta, "Oculto")

    def test_detalle_de_producto_inactivo_da_404(self):
        inactivo = crear_producto("INA-002", activo=False)
        self.assertEqual(self.client.get(reverse("guest:producto", args=[inactivo.pk])).status_code, 404)

    def test_solo_se_listan_servicios_activos(self):
        categoria = CategoriaServicio.objects.create(nombre="Categoria de prueba")
        Servicio.objects.create(categoria=categoria, nombre="Servicio visible", descripcion="x", precio_base=Decimal("10"))
        Servicio.objects.create(
            categoria=categoria, nombre="Servicio oculto", descripcion="x", precio_base=Decimal("10"), activo=False
        )
        respuesta = self.client.get(reverse("guest:servicios"))
        self.assertContains(respuesta, "Servicio visible")
        self.assertNotContains(respuesta, "Servicio oculto")

    def test_busqueda_filtra_por_nombre(self):
        crear_producto("BUS-001", nombre="Llavero azul")
        crear_producto("BUS-002", nombre="Maceta roja")
        respuesta = self.client.get(reverse("guest:catalogo"), {"q": "llavero"})
        self.assertContains(respuesta, "Llavero azul")
        self.assertNotContains(respuesta, "Maceta roja")


class StockTests(TestCase):
    def test_stock_negativo_es_rechazado_por_el_modelo(self):
        producto = Producto(sku="NEG-001", nombre="x", precio=Decimal("1"), stock=-1)
        with self.assertRaises(ValidationError):
            producto.full_clean()

    def test_stock_negativo_es_rechazado_por_la_base_de_datos(self):
        producto = crear_producto("NEG-002")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Producto.objects.filter(pk=producto.pk).update(stock=-5)

    def test_descontar_y_reponer(self):
        producto = crear_producto("MOV-001", stock=5)
        descontar_stock({producto.pk: 3})
        producto.refresh_from_db()
        self.assertEqual(producto.stock, 2)
        reponer_stock({producto.pk: 3})
        producto.refresh_from_db()
        self.assertEqual(producto.stock, 5)

    def test_no_se_vende_mas_de_lo_disponible(self):
        producto = crear_producto("MOV-002", stock=2)
        with self.assertRaises(StockInsuficiente):
            descontar_stock({producto.pk: 3})
        producto.refresh_from_db()
        self.assertEqual(producto.stock, 2)

    def test_producto_inactivo_no_se_puede_comprar(self):
        producto = crear_producto("MOV-003", activo=False)
        with self.assertRaises(ProductoNoDisponible):
            descontar_stock({producto.pk: 1})

    def test_ajuste_no_deja_stock_negativo(self):
        producto = crear_producto("AJU-001", stock=1)
        with self.assertRaises(StockInsuficiente):
            ajustar_stock(producto.pk, -2)
        self.assertEqual(ajustar_stock(producto.pk, 4).stock, 5)


class AdministracionCatalogoTests(TestCase):
    def test_operador_no_puede_crear_productos(self):
        iniciar_sesion(self.client, crear_usuario("op@example.com", GRUPO_OPERADOR, is_staff=True))
        self.assertEqual(self.client.get(reverse("administrator:producto_crear")).status_code, 403)
        respuesta = self.client.post(reverse("administrator:producto_crear"), {"sku": "X-1", "nombre": "x", "precio": "1"})
        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(Producto.objects.filter(sku="X-1").exists())

    def test_administrador_crea_producto_y_sku_se_normaliza(self):
        iniciar_sesion(self.client, crear_usuario("adm@example.com", GRUPO_ADMINISTRADOR, is_staff=True))
        respuesta = self.client.post(
            reverse("administrator:producto_crear"),
            {"sku": "nuevo-01", "nombre": "Nuevo", "precio": "3.50", "stock": "4", "stock_minimo": "1", "activo": "on"},
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(Producto.objects.filter(sku="NUEVO-01", stock=4).exists())

    def test_administrador_ajusta_stock(self):
        iniciar_sesion(self.client, crear_usuario("adm2@example.com", GRUPO_ADMINISTRADOR, is_staff=True))
        producto = crear_producto("AJU-002", stock=3)
        self.client.post(reverse("administrator:producto_stock", args=[producto.pk]), {"delta": "-2"})
        producto.refresh_from_db()
        self.assertEqual(producto.stock, 1)
        self.client.post(reverse("administrator:producto_stock", args=[producto.pk]), {"delta": "-5"})
        producto.refresh_from_db()
        self.assertEqual(producto.stock, 1)
