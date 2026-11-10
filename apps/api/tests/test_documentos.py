import json
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.api.tests.base import ApiTestCase
from apps.catalogo.models import Producto
from apps.cotizaciones.models import Cotizacion
from apps.cotizaciones.services import cotizaciones as servicios_cot
from apps.cotizaciones.tests.utiles import AlmacenTemporalMixin, archivo_stl, crear_cliente, crear_personal, crear_servicio
from apps.facturacion.models import Factura
from apps.pagos.models import EstadoPago, MetodoPago, Pago


class CotizacionesApiTests(AlmacenTemporalMixin, ApiTestCase):
    def setUp(self):
        super().setUp()
        self.usuario, self.cliente = crear_cliente("ana@example.com")
        self.otro, _ = crear_cliente("otro@example.com")
        self.token = self.token_de("ana@example.com")
        self.token_otro = self.token_de("otro@example.com")

    def solicitar(self, servicio, archivos=(), **extra):
        datos = {"servicio": servicio.pk, "cantidad": "2", "descripcion": "Pieza", "solicitud": "Necesito una pieza de prueba."}
        datos.update(extra)
        if archivos:
            datos["archivos"] = list(archivos)
        return self.client.post(reverse("api:cotizaciones"), datos, **self.cabecera(self.token))

    def test_solicitud_multipart_con_archivo_valido(self):
        servicio = crear_servicio(requiere_archivo=True)
        respuesta = self.solicitar(servicio, [archivo_stl()], material="PLA")
        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        cuerpo = respuesta.json()
        self.assertTrue(cuerpo["codigo"].startswith("COT-"))
        self.assertEqual(cuerpo["estado"], "SOLICITADA")
        self.assertTrue(cuerpo["puede_cancelar"])
        self.assertEqual(cuerpo["lineas"][0]["especificaciones"], {"material": "PLA"})
        self.assertEqual(len(cuerpo["archivos"]), 1)
        self.assertNotIn("ruta_archivo", cuerpo["archivos"][0])

    def test_archivos_invalidos_o_faltantes_se_rechazan(self):
        servicio = crear_servicio(requiere_archivo=True)
        falso = SimpleUploadedFile("malo.stl", b"MZ\x90\x00binario", content_type="application/octet-stream")
        self.assertIn("archivos", self.solicitar(servicio, [falso]).json()["error"]["campos"])
        self.assertIn("archivos", self.solicitar(servicio).json()["error"]["campos"])
        self.assertEqual(Cotizacion.objects.count(), 0)

    def test_solicitud_json_sin_archivos_para_servicios_que_no_lo_requieren(self):
        servicio = crear_servicio()
        respuesta = self.post(
            "cotizaciones", self.token,
            datos={"servicio": servicio.pk, "cantidad": 3, "descripcion": "Prototipo", "solicitud": "Prototipo de prueba largo.", "especificaciones": {"color": "Rojo"}},
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        self.assertEqual(respuesta.json()["lineas"][0]["especificaciones"], {"color": "Rojo"})
        malo = self.post("cotizaciones", self.token, datos={"servicio": servicio.pk, "cantidad": 0, "descripcion": "", "solicitud": "corta"})
        self.assertEqual(malo.status_code, 400)

    def test_flujo_completo_aceptar_y_aislamiento_entre_clientes(self):
        servicio = crear_servicio()
        cotizacion_id = self.solicitar(servicio).json()["id"]
        self.assertEqual(self.get("cotizacion", self.token_otro, args=(cotizacion_id,)).status_code, 404)
        self.assertEqual(self.post("cotizacion_accion", self.token_otro, args=(cotizacion_id, "cancelar")).status_code, 404)
        self.assertEqual(self.post("cotizacion_accion", self.token, args=(cotizacion_id, "aceptar")).status_code, 409)

        operador = crear_personal("operador@example.com")
        cotizacion = Cotizacion.objects.get(pk=cotizacion_id)
        lineas = [{"id": d.pk, "cantidad": Decimal("2"), "precio_unitario": Decimal("15.00"), "descuento": Decimal("0")} for d in cotizacion.detalles.all()]
        servicios_cot.revisar_cotizacion(cotizacion.pk, operador, lineas)
        servicios_cot.enviar_cotizacion(cotizacion.pk, operador)

        detalle = self.get("cotizacion", self.token, args=(cotizacion_id,)).json()
        self.assertTrue(detalle["puede_responder"])
        aceptada = self.post("cotizacion_accion", self.token, args=(cotizacion_id, "aceptar"))
        self.assertEqual((aceptada.status_code, aceptada.json()["estado"]), (200, "ACEPTADA"))
        self.assertEqual(self.post("cotizacion_accion", self.token, args=(cotizacion_id, "rechazar")).status_code, 409)
        self.assertEqual(self.post("cotizacion_accion", self.token, args=(cotizacion_id, "inventada")).status_code, 404)

    def test_cancelar_solicitud_sin_revisar(self):
        cotizacion_id = self.solicitar(crear_servicio()).json()["id"]
        respuesta = self.post("cotizacion_accion", self.token, args=(cotizacion_id, "cancelar"))
        self.assertEqual(respuesta.json()["estado"], "CANCELADA")

    def test_descarga_de_archivos_solo_para_su_dueno(self):
        servicio = crear_servicio(requiere_archivo=True)
        cuerpo = self.solicitar(servicio, [archivo_stl()]).json()
        argumentos = (cuerpo["id"], cuerpo["archivos"][0]["id"])
        respuesta = self.get("cotizacion_archivo", self.token, args=argumentos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn(b"solid pieza", b"".join(respuesta.streaming_content))
        self.assertEqual(self.get("cotizacion_archivo", self.token_otro, args=argumentos).status_code, 404)
        self.assertEqual(self.get("cotizacion_archivo", None, args=argumentos).status_code, 401)

    def test_listado_paginado(self):
        servicio = crear_servicio()
        for _ in range(3):
            self.solicitar(servicio)
        pagina = self.get("cotizaciones", self.token, params={"por_pagina": 2}).json()
        self.assertEqual((len(pagina["resultados"]), pagina["total"], pagina["hay_mas"]), (2, 3, True))
        self.assertEqual(self.get("cotizaciones", self.token, params={"por_pagina": "x"}).status_code, 400)


class ComprasYPedidosApiTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.usuario, self.cliente = crear_cliente("ana@example.com")
        self.otro, _ = crear_cliente("otro@example.com")
        self.token = self.token_de("ana@example.com")
        self.token_otro = self.token_de("otro@example.com")
        self.producto = Producto.objects.create(sku="API-001", nombre="Producto API", precio=Decimal("10.00"), stock=5, stock_minimo=1)

    def items(self, cantidad):
        return [{"producto_id": self.producto.pk, "cantidad": cantidad}]

    def test_validar_carrito_calcula_totales_y_detecta_problemas(self):
        bueno = self.post("carrito_validar", self.token, datos={"items": self.items(2)}).json()
        self.assertFalse(bueno["hay_problemas"])
        self.assertEqual(bueno["totales"], {"subtotal": "20.00", "descuento": "0.00", "impuesto": "2.60", "total": "22.60"})
        malo = self.post("carrito_validar", self.token, datos={"items": self.items(9)}).json()
        self.assertTrue(malo["hay_problemas"])
        self.assertEqual(self.post("carrito_validar", self.token, datos={"items": []}).status_code, 400)
        self.assertEqual(self.post("carrito_validar", self.token, datos={"items": [{"producto_id": "x", "cantidad": 1}]}).status_code, 400)
        self.assertEqual(self.post("carrito_validar", self.token, datos={"items": self.items(100)}).status_code, 400)

    def test_compra_descuenta_stock_y_es_idempotente(self):
        respuesta = self.post("comprar", self.token, datos={"items": self.items(2), "token": "token-compra-0001"})
        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        pedido = respuesta.json()["pedido"]
        self.assertEqual((pedido["estado"], pedido["total"]), ("PENDIENTE", "22.60"))
        self.assertTrue(pedido["codigo"].startswith("ENC-"))
        self.assertEqual(pedido["historial"][0]["comentario"], "Compra confirmada desde la tienda.")
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 3)
        repetida = self.post("comprar", self.token, datos={"items": self.items(2), "token": "token-compra-0001"})
        self.assertEqual(repetida.status_code, 200)
        self.assertTrue(repetida.json()["duplicado"])
        self.assertEqual(repetida.json()["pedido"]["id"], pedido["id"])
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 3)

    def test_compra_sin_existencias_o_con_token_invalido(self):
        sin_stock = self.post("comprar", self.token, datos={"items": self.items(9), "token": "token-compra-0002"})
        self.assertEqual(sin_stock.status_code, 400)
        self.assertIn("Existencias insuficientes", sin_stock.json()["error"]["mensaje"])
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 5)
        self.assertEqual(self.post("comprar", self.token, datos={"items": self.items(1), "token": "x"}).status_code, 400)

    def test_cancelar_pedido_repone_stock_y_no_se_repite(self):
        pedido_id = self.post("comprar", self.token, datos={"items": self.items(2), "token": "token-compra-0003"}).json()["pedido"]["id"]
        self.assertEqual(self.post("pedido_cancelar", self.token_otro, args=(pedido_id,)).status_code, 404)
        cancelado = self.post("pedido_cancelar", self.token, args=(pedido_id,))
        self.assertEqual((cancelado.status_code, cancelado.json()["estado"]), (200, "CANCELADO"))
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 5)
        self.assertEqual(self.post("pedido_cancelar", self.token, args=(pedido_id,)).status_code, 409)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 5)

    def test_listado_y_detalle_de_pedidos_aislados(self):
        pedido_id = self.post("comprar", self.token, datos={"items": self.items(1), "token": "token-compra-0004"}).json()["pedido"]["id"]
        self.assertEqual([p["id"] for p in self.get("pedidos", self.token).json()["resultados"]], [pedido_id])
        self.assertEqual(self.get("pedidos", self.token_otro).json()["total"], 0)
        self.assertEqual(self.get("pedido", self.token_otro, args=(pedido_id,)).status_code, 404)
        detalle = self.get("pedido", self.token, args=(pedido_id,)).json()
        self.assertEqual(detalle["progreso"], 25)
        self.assertTrue(detalle["puede_cancelar"])
        self.assertEqual(len(detalle["lineas"]), 1)

    def test_facturas_solo_muestran_pagos_confirmados(self):
        factura = Factura.objects.create(
            cliente=self.cliente, numero_factura="FAC-API-1", nombre_facturacion="Cliente",
            subtotal=Decimal("50.00"), total=Decimal("50.00"), saldo_pendiente=Decimal("30.00"),
        )
        metodo, _ = MetodoPago.objects.get_or_create(nombre="Efectivo")
        Pago.objects.create(factura=factura, metodo_pago=metodo, monto=Decimal("20.00"), estado=EstadoPago.CONFIRMADO)
        Pago.objects.create(factura=factura, metodo_pago=metodo, monto=Decimal("5.00"), estado=EstadoPago.CANCELADO)
        self.assertEqual(self.get("facturas", self.token).json()["total"], 1)
        detalle = self.get("factura", self.token, args=(factura.pk,)).json()
        self.assertEqual([p["monto"] for p in detalle["pagos"]], ["20.00"])
        self.assertEqual(detalle["saldo_pendiente"], "30.00")
        self.assertEqual(self.get("factura", self.token_otro, args=(factura.pk,)).status_code, 404)
        self.assertEqual(self.get("facturas", self.token_otro).json()["total"], 0)
