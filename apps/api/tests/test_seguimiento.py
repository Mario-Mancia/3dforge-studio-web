from apps.api.tests.base import ApiTestCase
from apps.cotizaciones.tests.utiles import crear_cliente
from apps.notificaciones.models import Notificacion
from apps.notificaciones.services.notificaciones import notificar


class NotificacionesApiTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.usuario, _ = crear_cliente("ana@example.com")
        self.otro, _ = crear_cliente("otro@example.com")
        self.token = self.token_de("ana@example.com")
        self.token_otro = self.token_de("otro@example.com")

    def test_listado_contador_y_lectura(self):
        propia = notificar(self.usuario, "Aviso propio", "x", "cotizacion", 1)
        notificar(self.usuario, "Segundo aviso", "x", "encargo", 2)
        ajena = notificar(self.otro, "Aviso ajeno", "x", "cotizacion", 1)
        lista = self.get("notificaciones", self.token).json()
        self.assertEqual(sorted(n["titulo"] for n in lista["resultados"]), ["Aviso propio", "Segundo aviso"])
        self.assertEqual(self.get("notificaciones_contador", self.token).json()["no_leidas"], 2)
        self.assertEqual(self.post("notificacion_leer", self.token, args=(ajena.pk,)).status_code, 404)
        self.assertEqual(self.post("notificacion_leer", self.token, args=(propia.pk,)).json()["no_leidas"], 1)
        self.assertEqual(len(self.get("notificaciones", self.token, params={"no_leidas": "1"}).json()["resultados"]), 1)
        self.assertEqual(self.post("notificaciones_leer_todas", self.token).json()["no_leidas"], 0)
        self.assertFalse(Notificacion.objects.get(pk=ajena.pk).leida)


class SoporteApiTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        crear_cliente("ana@example.com")
        crear_cliente("otro@example.com")
        self.token = self.token_de("ana@example.com")
        self.token_otro = self.token_de("otro@example.com")

    def test_crear_listar_ver_y_cerrar(self):
        malo = self.post("soporte", self.token, datos={"asunto": "", "descripcion": "corta", "prioridad": "URGENTE"})
        self.assertEqual(malo.status_code, 400)
        self.assertIn("prioridad", malo.json()["error"]["campos"])
        creada = self.post("soporte", self.token, datos={"asunto": "Duda", "descripcion": "Necesito ayuda con mi pedido.", "prioridad": "ALTA"})
        self.assertEqual(creada.status_code, 201, creada.content)
        solicitud_id = creada.json()["id"]
        self.assertEqual(creada.json()["estado"], "ABIERTA")
        self.assertEqual(self.get("soporte", self.token).json()["total"], 1)
        self.assertEqual(self.get("soporte", self.token_otro).json()["total"], 0)
        self.assertEqual(self.get("soporte_detalle", self.token_otro, args=(solicitud_id,)).status_code, 404)
        self.assertEqual(self.post("soporte_cerrar", self.token_otro, args=(solicitud_id,)).status_code, 404)
        cerrada = self.post("soporte_cerrar", self.token, args=(solicitud_id,))
        self.assertEqual(cerrada.json()["estado"], "CERRADA")
        self.assertEqual(self.post("soporte_cerrar", self.token, args=(solicitud_id,)).status_code, 409)
