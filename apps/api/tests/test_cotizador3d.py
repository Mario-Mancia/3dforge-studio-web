import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from apps.api.tests.base import ApiTestCase
from apps.cotizaciones.models import Cotizacion, Filamento
from apps.cotizaciones.tests.test_cotizador_3d import crear_filamento, cubo_stl, requiere_trimesh
from apps.cotizaciones.tests.utiles import AlmacenTemporalMixin, crear_cliente, crear_personal


@override_settings(COTIZADOR_AISLADO=False)
class CotizadorApiTests(AlmacenTemporalMixin, ApiTestCase):
    def setUp(self):
        super().setUp()
        self.usuario, self.cliente = crear_cliente("ana@example.com")
        self.token = self.token_de("ana@example.com")
        self.filamento = crear_filamento()

    def opciones(self, **cambios):
        datos = {
            "filamento": self.filamento.pk, "relleno": 20, "calidad": "estandar", "escala": 100,
            "unidades": "mm", "soportes": "auto", "cantidad": 1,
        }
        datos.update(cambios)
        return datos

    def multipart(self, nombre, datos, token="__propio__"):
        token = self.token if token == "__propio__" else token
        return self.client.post(reverse(f"api:{nombre}"), datos, **self.cabecera(token))

    def test_opciones_exigen_sesion_y_describen_el_formulario(self):
        self.assertEqual(self.get("opciones_3d").status_code, 401)
        cuerpo = self.get("opciones_3d", self.token).json()
        self.assertTrue(cuerpo["disponible"])
        self.assertEqual(cuerpo["filamentos"][0]["id"], self.filamento.pk)
        self.assertIn("stl", cuerpo["formatos"])
        self.assertIn(20, cuerpo["rellenos"])
        self.assertIn("estandar", [c["codigo"] for c in cuerpo["calidades"]])
        self.assertIn("aproximadas", cuerpo["aviso"])
        self.assertEqual(len(cuerpo["cama_mm"]), 3)

    def test_sin_filamentos_no_esta_disponible(self):
        Filamento.objects.update(activo=False)
        cuerpo = self.get("opciones_3d", self.token).json()
        self.assertFalse(cuerpo["disponible"])
        self.assertEqual(cuerpo["filamentos"], [])

    def test_el_personal_no_usa_el_cotizador_de_clientes(self):
        crear_personal("operador@example.com")
        token = self.token_de("operador@example.com")
        self.assertEqual(self.get("opciones_3d", token).status_code, 403)

    @requiere_trimesh
    def test_estimacion_con_archivo_y_luego_solo_con_el_analisis(self):
        primera = self.multipart("estimar_3d", {**self.opciones(), "archivo": cubo_stl()})
        self.assertEqual(primera.status_code, 200, primera.content)
        cuerpo = primera.json()
        self.assertEqual(cuerpo["estimacion"]["dimensiones"], [20.0, 20.0, 20.0])
        self.assertIn("aproximadas", cuerpo["estimacion"]["aviso"])
        self.assertTrue(cuerpo["estimacion"]["cabe"])
        segunda = self.multipart("estimar_3d", {**self.opciones(escala=200), "analisis": json.dumps(cuerpo["analisis"])})
        self.assertEqual(segunda.status_code, 200, segunda.content)
        self.assertEqual(segunda.json()["estimacion"]["dimensiones"], [40.0, 40.0, 40.0])
        self.assertGreater(Decimal(segunda.json()["estimacion"]["total"]), Decimal(cuerpo["estimacion"]["total"]))
        self.assertEqual(Cotizacion.objects.count(), 0)

    @requiere_trimesh
    def test_estimacion_rechaza_archivos_y_datos_invalidos(self):
        imagen = SimpleUploadedFile("foto.png", b"\x89PNG\r\n\x1a\n" + b"0" * 20)
        malo = self.multipart("estimar_3d", {**self.opciones(), "archivo": imagen})
        self.assertEqual(malo.status_code, 400)
        self.assertEqual(malo.json()["error"]["codigo"], "archivo_invalido")
        sin_nada = self.multipart("estimar_3d", self.opciones())
        self.assertEqual(sin_nada.status_code, 400)
        mala_opcion = self.multipart("estimar_3d", {**self.opciones(relleno=77), "archivo": cubo_stl()})
        self.assertEqual(mala_opcion.status_code, 400)
        self.assertIn("relleno", mala_opcion.json()["error"]["campos"])
        self.assertEqual(self.multipart("estimar_3d", {**self.opciones(), "archivo": cubo_stl()}, token=None).status_code, 401)

    @requiere_trimesh
    def test_la_estimacion_con_archivo_tiene_limite_por_minuto(self):
        reloj_fijo = SimpleNamespace(time=lambda: 12345.0)
        with patch("apps.api.vistas.cotizador3d.LIMITE_ANALISIS_POR_MINUTO", 2), patch(
            "apps.api.vistas.cotizador3d.time", reloj_fijo
        ):
            estados = [
                self.multipart("estimar_3d", {**self.opciones(), "archivo": cubo_stl()}).status_code for _ in range(3)
            ]
        self.assertEqual(estados, [200, 200, 429])

    @requiere_trimesh
    def test_solicitar_crea_una_cotizacion_normal_preliminar(self):
        respuesta = self.multipart(
            "solicitar_3d", {**self.opciones(cantidad=2), "archivo": cubo_stl(), "descripcion": "Soporte", "comentarios": "Urge"}
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo["estado"], "SOLICITADA")
        self.assertTrue(cuerpo["puede_cancelar"])
        self.assertIn("aproximadas", cuerpo["solicitud"])
        self.assertIn("Urge", cuerpo["solicitud"])
        self.assertEqual(len(cuerpo["archivos"]), 1)
        linea = cuerpo["lineas"][0]
        self.assertEqual(linea["descripcion"], "Impresión 3D: Soporte")
        self.assertEqual(linea["especificaciones"]["Tipo"], "Cotización automática 3D")
        self.assertGreater(Decimal(cuerpo["total"]), Decimal("0"))
        detalle = self.get("cotizacion", self.token, args=(cuerpo["id"],))
        self.assertEqual(detalle.status_code, 200)

    @requiere_trimesh
    def test_otro_cliente_no_ve_la_cotizacion(self):
        cuerpo = self.multipart("solicitar_3d", {**self.opciones(), "archivo": cubo_stl()}).json()
        crear_cliente("beto@example.com")
        ajeno = self.get("cotizacion", self.token_de("beto@example.com"), args=(cuerpo["id"],))
        self.assertEqual(ajeno.status_code, 404)

    @requiere_trimesh
    def test_solicitar_rechaza_pieza_que_no_cabe_o_archivo_invalido(self):
        grande = self.multipart("solicitar_3d", {**self.opciones(escala=200), "archivo": cubo_stl(lado=200)})
        self.assertEqual(grande.status_code, 400)
        self.assertEqual(grande.json()["error"]["codigo"], "cotizacion_invalida")
        imagen = SimpleUploadedFile("foto.png", b"\x89PNG\r\n\x1a\n" + b"0" * 20)
        malo = self.multipart("solicitar_3d", {**self.opciones(), "archivo": imagen})
        self.assertEqual(malo.status_code, 400)
        self.assertIn("archivo", malo.json()["error"]["campos"])
        self.assertEqual(Cotizacion.objects.count(), 0)
