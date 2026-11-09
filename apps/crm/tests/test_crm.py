from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse

from apps.cotizaciones.tests.utiles import crear_cliente, crear_personal
from apps.crm.models import InteraccionCliente, NotaCliente, SolicitudSoporte
from apps.crm.services import crm as srv
from apps.notificaciones.models import Notificacion
from apps.usuarios.tests.utiles import iniciar_sesion


class CRMServiciosTests(TestCase):
    def setUp(self):
        self.usuario, self.cliente = crear_cliente("cliente@example.com")
        self.operador = crear_personal("operador@example.com")

    def test_notas_e_interacciones_solo_del_personal(self):
        srv.agregar_nota(self.cliente.pk, self.operador, "Llamar el lunes")
        srv.registrar_interaccion(self.cliente.pk, self.operador, "LLAMADA", "Consulta inicial", "Detalle")
        self.assertEqual(NotaCliente.objects.count(), 1)
        self.assertEqual(InteraccionCliente.objects.filter(asunto="Consulta inicial").count(), 1)
        with self.assertRaises(PermissionDenied):
            srv.agregar_nota(self.cliente.pk, self.usuario, "no")
        with self.assertRaises(PermissionDenied):
            srv.registrar_interaccion(self.cliente.pk, self.usuario, "LLAMADA", "no")

    def test_evento_no_se_duplica(self):
        srv.registrar_evento(self.cliente, self.operador, "Evento X")
        self.assertIsNone(srv.registrar_evento(self.cliente, self.operador, "Evento X"))
        self.assertEqual(InteraccionCliente.objects.filter(asunto="Evento X").count(), 1)

    def test_ciclo_de_soporte(self):
        s = srv.crear_solicitud(self.cliente, "No abre el archivo", "El archivo STL no se carga bien.", "ALTA")
        self.assertTrue(Notificacion.objects.filter(usuario=self.operador, tipo="soporte", referencia_id=s.pk).exists())
        srv.tomar_solicitud(s.pk, self.operador)
        s.refresh_from_db()
        self.assertEqual((s.estado, s.usuario_responsable), ("EN_PROCESO", self.operador))
        srv.cambiar_estado_solicitud(s.pk, self.operador, "RESUELTA")
        self.assertTrue(Notificacion.objects.filter(usuario=self.usuario, titulo__contains="Resuelta").exists())
        srv.cerrar_por_cliente(s.pk, self.usuario)
        with self.assertRaises(srv.ErrorCRM):
            srv.cambiar_estado_solicitud(s.pk, self.operador, "EN_PROCESO")

    def test_prioridad_urgente_no_la_fija_el_cliente(self):
        with self.assertRaises(srv.ErrorCRM):
            srv.crear_solicitud(self.cliente, "x", "descripcion larga", "URGENTE")

    def test_otro_cliente_no_cierra_solicitud_ajena(self):
        s = srv.crear_solicitud(self.cliente, "Asunto", "Descripcion suficiente.")
        otro, _ = crear_cliente("otro@example.com")
        with self.assertRaises(PermissionDenied):
            srv.cerrar_por_cliente(s.pk, otro)


class CRMVistasTests(TestCase):
    def setUp(self):
        self.usuario, self.cliente = crear_cliente("cliente@example.com")
        self.operador = crear_personal("operador@example.com")

    def test_cliente_crea_y_consulta_su_soporte_y_otro_no_lo_ve(self):
        iniciar_sesion(self.client, self.usuario)
        respuesta = self.client.post(
            reverse("customer:soporte"), {"asunto": "Duda", "descripcion": "Necesito ayuda con mi pedido.", "prioridad": "MEDIA"}
        )
        s = SolicitudSoporte.objects.get()
        self.assertRedirects(respuesta, reverse("customer:soporte_detalle", args=[s.pk]), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse("customer:soporte_detalle", args=[s.pk])).status_code, 200)
        otro, _ = crear_cliente("otro@example.com")
        self.client.logout()
        iniciar_sesion(self.client, otro)
        self.assertEqual(self.client.get(reverse("customer:soporte_detalle", args=[s.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("customer:soporte_cerrar", args=[s.pk])).status_code, 404)

    def test_operador_gestiona_clientes_y_soporte(self):
        s = srv.crear_solicitud(self.cliente, "Duda", "Necesito ayuda con mi pedido.")
        iniciar_sesion(self.client, self.operador)
        for nombre, args in (("operator:clientes", []), ("operator:cliente", [self.cliente.pk]),
                             ("operator:soporte", []), ("operator:soporte_detalle", [s.pk]), ("operator:notificaciones", [])):
            self.assertEqual(self.client.get(reverse(nombre, args=args)).status_code, 200, nombre)
        self.client.post(reverse("operator:cliente_accion", args=[self.cliente.pk, "nota"]), {"contenido": "Cliente puntual"})
        self.assertEqual(NotaCliente.objects.count(), 1)
        self.client.post(reverse("operator:soporte_accion", args=[s.pk, "tomar"]))
        s.refresh_from_db()
        self.assertEqual(s.estado, "EN_PROCESO")

    def test_cliente_no_accede_al_crm_del_operador(self):
        iniciar_sesion(self.client, self.usuario)
        self.assertEqual(self.client.get(reverse("operator:clientes")).status_code, 403)
        self.assertEqual(self.client.get(reverse("operator:soporte")).status_code, 403)

    def test_validacion_ajax_de_las_formas_nuevas(self):
        iniciar_sesion(self.client, self.usuario)
        r = self.client.post(reverse("validar_campo", args=["soporte"]), {"campo": "asunto", "asunto": "", "descripcion": "x"})
        self.assertFalse(r.json()["valido"])
        self.assertEqual(self.client.post(reverse("validar_campo", args=["nota"]), {"campo": "contenido"}).status_code, 403)
