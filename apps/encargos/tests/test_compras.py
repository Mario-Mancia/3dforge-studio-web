from decimal import Decimal

from django.contrib.sessions.backends.base import SessionBase
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.catalogo.models import Producto
from apps.cotizaciones.tests.utiles import crear_cliente, crear_personal
from apps.encargos.models import Encargo, EstadoEncargo
from apps.encargos.services import compras
from apps.encargos.services import encargos as srv_encargos
from apps.usuarios.tests.utiles import iniciar_sesion


def producto(sku, stock=5, precio="10.00", **extra):
    return Producto.objects.create(sku=sku, nombre=f"Producto {sku}", precio=Decimal(precio), stock=stock, **extra)


@override_settings(TASA_IMPUESTO=Decimal("0.13"))
class CompraBase(TestCase):
    def setUp(self):
        cache.clear()
        self.usuario, self.cliente = crear_cliente("cliente@example.com")
        self.sesion = SessionBase()
        self.carrito = compras.Carrito(self.sesion)

    def comprar(self):
        token = compras.iniciar_checkout(self.sesion)
        return token, compras.confirmar_compra(self.cliente, self.usuario, self.sesion, token)


class CarritoTests(CompraBase):
    def test_agregar_actualizar_y_quitar(self):
        p = producto("CAR-001")
        self.carrito.agregar(p.pk, 2)
        self.carrito.agregar(p.pk, 1)
        self.assertEqual(self.carrito.items(), {p.pk: 3})
        self.carrito.actualizar(p.pk, 1)
        self.assertEqual(self.carrito.unidades, 1)
        self.carrito.actualizar(p.pk, 0)
        self.assertEqual(len(self.carrito), 0)

    def test_valida_cantidad_producto_y_stock(self):
        p = producto("CAR-002", stock=2)
        inactivo = producto("CAR-003", activo=False)
        for cantidad in (0, -1, 100, "abc"):
            with self.assertRaises(compras.ErrorCompra):
                self.carrito.agregar(p.pk, cantidad)
        with self.assertRaises(compras.ErrorCompra):
            self.carrito.agregar(inactivo.pk, 1)
        with self.assertRaises(compras.ErrorCompra):
            self.carrito.agregar(p.pk, 3)
        with self.assertRaises(compras.ErrorCompra):
            self.carrito.agregar(999999, 1)

    def test_los_precios_los_decide_el_servidor(self):
        p = producto("CAR-004", precio="10.00")
        self.carrito.agregar(p.pk, 2)
        Producto.objects.filter(pk=p.pk).update(precio=Decimal("12.00"))
        self.assertEqual(self.carrito.totales()["subtotal"], Decimal("24.00"))


class CompraTests(CompraBase):
    def test_confirmar_crea_encargo_descuenta_stock_y_vacia_el_carrito(self):
        a, b = producto("COM-001", stock=5), producto("COM-002", stock=3, precio="4.00")
        self.carrito.agregar(a.pk, 2)
        self.carrito.agregar(b.pk, 1)
        _, encargo = self.comprar()
        self.assertEqual(encargo.estado, EstadoEncargo.PENDIENTE)
        self.assertIsNone(encargo.cotizacion_id)
        self.assertTrue(encargo.codigo.startswith("ENC-"))
        self.assertEqual(encargo.subtotal, Decimal("24.00"))
        self.assertEqual(encargo.impuesto, Decimal("3.12"))
        self.assertEqual(encargo.total, Decimal("27.12"))
        self.assertEqual(encargo.detalles.count(), 2)
        self.assertEqual(encargo.historial.count(), 1)
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual((a.stock, b.stock), (3, 2))
        self.assertEqual(len(compras.Carrito(self.sesion)), 0)

    def test_stock_insuficiente_no_cambia_nada(self):
        p = producto("COM-003", stock=3)
        self.carrito.agregar(p.pk, 3)
        token = compras.iniciar_checkout(self.sesion)
        Producto.objects.filter(pk=p.pk).update(stock=1)
        with self.assertRaises(compras.ErrorCompra):
            compras.confirmar_compra(self.cliente, self.usuario, self.sesion, token)
        p.refresh_from_db()
        self.assertEqual(p.stock, 1)
        self.assertEqual(Encargo.objects.count(), 0)

    def test_doble_envio_no_duplica_la_compra(self):
        p = producto("COM-004", stock=5)
        self.carrito.agregar(p.pk, 2)
        token, encargo = self.comprar()
        with self.assertRaises(compras.CompraDuplicada) as contexto:
            compras.confirmar_compra(self.cliente, self.usuario, self.sesion, token)
        self.assertEqual(contexto.exception.encargo_id, encargo.pk)
        p.refresh_from_db()
        self.assertEqual(p.stock, 3)
        self.assertEqual(Encargo.objects.count(), 1)

    def test_token_invalido_o_carrito_vacio(self):
        with self.assertRaises(compras.ErrorCompra):
            compras.iniciar_checkout(self.sesion)
        p = producto("COM-005")
        self.carrito.agregar(p.pk, 1)
        compras.iniciar_checkout(self.sesion)
        with self.assertRaises(compras.ErrorCompra):
            compras.confirmar_compra(self.cliente, self.usuario, self.sesion, "falso")

    def test_cancelar_la_compra_repone_el_stock_una_vez(self):
        p = producto("COM-006", stock=4)
        self.carrito.agregar(p.pk, 3)
        _, encargo = self.comprar()
        operador = crear_personal("operador@example.com")
        srv_encargos.cambiar_estado(encargo.pk, operador, "CANCELADO")
        p.refresh_from_db()
        self.assertEqual(p.stock, 4)


class VistasCompraTests(CompraBase):
    def test_flujo_completo_por_vistas(self):
        p = producto("VIS-001", stock=4)
        iniciar_sesion(self.client, self.usuario)
        self.assertEqual(self.client.get(reverse("customer:tienda")).status_code, 200)
        self.client.post(reverse("customer:carrito_agregar", args=[p.pk]), {"cantidad": "2"})
        self.assertContains(self.client.get(reverse("customer:carrito")), p.nombre)
        respuesta = self.client.get(reverse("customer:checkout"))
        self.assertEqual(respuesta.status_code, 200)
        token = respuesta.context["token"]
        respuesta = self.client.post(reverse("customer:checkout"), {"token": token})
        encargo = Encargo.objects.get()
        self.assertRedirects(respuesta, reverse("customer:pedido", args=[encargo.pk]), fetch_redirect_response=False)
        repetido = self.client.post(reverse("customer:checkout"), {"token": token})
        self.assertRedirects(repetido, reverse("customer:pedido", args=[encargo.pk]), fetch_redirect_response=False)
        self.assertEqual(Encargo.objects.count(), 1)
        p.refresh_from_db()
        self.assertEqual(p.stock, 2)

    def test_solo_clientes_acceden_y_los_demas_no_ven_el_pedido(self):
        self.assertEqual(self.client.get(reverse("customer:carrito")).status_code, 302)
        iniciar_sesion(self.client, crear_personal("op@example.com"))
        self.assertEqual(self.client.get(reverse("customer:tienda")).status_code, 403)
