from decimal import Decimal

from apps.api.tests.base import ApiTestCase
from apps.catalogo.models import CategoriaServicio, Producto
from apps.cotizaciones.tests.utiles import crear_cliente, crear_servicio


class CatalogoApiTests(ApiTestCase):
    def test_catalogo_publico_solo_muestra_lo_activo(self):
        Producto.objects.create(sku="CAT-001", nombre="Visible", precio=Decimal("9.99"), stock=5, stock_minimo=1)
        Producto.objects.create(sku="CAT-002", nombre="Agotado", precio=Decimal("5.00"), stock=0)
        Producto.objects.create(sku="CAT-003", nombre="Oculto", precio=Decimal("5.00"), stock=5, activo=False)
        resultados = self.get("productos").json()["resultados"]
        self.assertEqual([p["nombre"] for p in resultados], ["Agotado", "Visible"])
        self.assertEqual({p["nombre"]: p["disponibilidad"] for p in resultados}, {"Visible": "disponible", "Agotado": "agotado"})
        self.assertEqual(resultados[1]["precio"], "9.99")
        oculto = Producto.objects.get(sku="CAT-003")
        self.assertEqual(self.get("producto", args=(oculto.pk,)).status_code, 404)
        self.assertEqual(len(self.get("productos", params={"q": "visi"}).json()["resultados"]), 1)

    def test_servicios_y_categorias_publicos(self):
        servicio = crear_servicio("Impresión API", requiere_archivo=True)
        crear_servicio("Servicio oculto", activo=False)
        resultados = self.get("servicios").json()["resultados"]
        self.assertEqual([s["nombre"] for s in resultados], ["Impresión API"])
        self.assertTrue(resultados[0]["requiere_archivo"])
        self.assertEqual(self.get("servicio", args=(servicio.pk,)).status_code, 200)
        self.assertEqual(self.get("servicios", params={"categoria": "x"}).status_code, 400)
        self.assertEqual(len(self.get("categorias").json()["resultados"]), CategoriaServicio.objects.filter(activo=True).count())

    def test_negocio_responde_aunque_no_haya_configuracion(self):
        self.assertEqual(self.get("negocio").status_code, 200)


class CuentaApiTests(ApiTestCase):
    def test_perfil_ver_y_editar_con_las_reglas_de_la_web(self):
        usuario, cliente = crear_cliente("ana@example.com")
        token = self.token_de("ana@example.com")
        self.assertEqual(self.get("perfil", token).json()["tipo_cliente"], "PERSONA")
        malo = self.enviar("patch", "perfil", token, datos={"tipo_cliente": "EMPRESA", "telefono": "abc"})
        self.assertEqual(malo.status_code, 400)
        campos = malo.json()["error"]["campos"]
        self.assertIn("nombre_empresa", campos)
        self.assertIn("telefono", campos)
        bueno = self.enviar("put", "perfil", token, datos={"tipo_cliente": "PERSONA", "nombres": "Ana María", "apellidos": "Gómez", "telefono": "+503 7000-2222"})
        self.assertEqual(bueno.status_code, 200)
        usuario.refresh_from_db()
        self.assertEqual((usuario.nombres, usuario.telefono), ("Ana María", "+503 7000-2222"))

    def test_panel_con_indicadores(self):
        crear_cliente("ana@example.com")
        token = self.token_de("ana@example.com")
        cuerpo = self.get("panel", token).json()
        self.assertEqual(cuerpo["kpis"]["pedidos_en_curso"], 0)
        self.assertEqual(cuerpo["kpis"]["saldo_pendiente"], "0.00")
        self.assertEqual(cuerpo["cotizaciones"], [])
