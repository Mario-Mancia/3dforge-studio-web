from allauth.account.models import EmailAddress
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.usuarios.constants import ESTADO_ACTIVO, ESTADO_SUSPENDIDO, GRUPO_ADMINISTRADOR, GRUPO_CLIENTE, GRUPO_OPERADOR
from apps.usuarios.models import Empleado, EstadoUsuario, Usuario
from apps.usuarios.services import usuarios as srv
from apps.usuarios.tests.utiles import CLAVE, crear_usuario, iniciar_sesion

DATOS = {
    "correo": "nuevo.operador@example.com",
    "nombres": "Luis",
    "apellidos": "Pérez",
    "telefono": "",
    "rol": GRUPO_OPERADOR,
    "codigo_empleado": "emp-010",
    "cargo": "Operador de impresión",
    "fecha_contratacion": "",
    "password1": "Clave-Segura-456",
    "password2": "Clave-Segura-456",
}


class GestionUsuariosTests(TestCase):
    def setUp(self):
        self.admin = crear_usuario("admin@example.com", GRUPO_ADMINISTRADOR, is_staff=True)
        Empleado.objects.create(usuario=self.admin, codigo_empleado="EMP-001", cargo="Administrador")

    def test_administrador_crea_empleado_que_puede_ingresar(self):
        iniciar_sesion(self.client, self.admin)
        respuesta = self.client.post(reverse("administrator:usuario_crear"), DATOS)
        self.assertEqual(respuesta.status_code, 302)
        usuario = Usuario.objects.get(correo="nuevo.operador@example.com")
        self.assertTrue(usuario.is_staff)
        self.assertTrue(usuario.groups.filter(name=GRUPO_OPERADOR).exists())
        self.assertEqual(usuario.empleado.codigo_empleado, "EMP-010")
        self.assertTrue(EmailAddress.objects.get(user=usuario).verified)
        self.assertTrue(usuario.check_password("Clave-Segura-456"))

    def test_solo_administradores_acceden_a_la_gestion(self):
        iniciar_sesion(self.client, crear_usuario("op@example.com", GRUPO_OPERADOR, is_staff=True))
        self.assertEqual(self.client.get(reverse("administrator:usuarios")).status_code, 403)
        self.assertEqual(self.client.post(reverse("administrator:usuario_crear"), DATOS).status_code, 403)
        self.assertFalse(Usuario.objects.filter(correo=DATOS["correo"]).exists())

    def test_validaciones_de_alta(self):
        iniciar_sesion(self.client, self.admin)
        url = reverse("administrator:usuario_crear")
        self.assertEqual(self.client.post(url, {**DATOS, "password1": "123", "password2": "123"}).status_code, 200)
        self.assertEqual(self.client.post(url, {**DATOS, "password2": "otra-clave-distinta"}).status_code, 200)
        self.assertEqual(self.client.post(url, {**DATOS, "correo": "ADMIN@example.com"}).status_code, 200)
        self.assertEqual(self.client.post(url, {**DATOS, "codigo_empleado": "EMP-001"}).status_code, 200)
        self.assertEqual(self.client.post(url, {**DATOS, "rol": "Customer"}).status_code, 200)
        self.assertEqual(Usuario.objects.filter(correo=DATOS["correo"]).count(), 0)

    def test_no_puede_desactivarse_a_si_mismo_ni_dejar_sin_administradores(self):
        estado = EstadoUsuario.objects.get(pk=ESTADO_SUSPENDIDO)
        base = {"nombres": "Ana", "apellidos": "Prueba", "telefono": "", "estado": estado, "rol": GRUPO_ADMINISTRADOR,
                "codigo_empleado": "EMP-001", "cargo": "Administrador", "fecha_contratacion": None, "empleado_activo": True}
        with self.assertRaises(srv.ErrorUsuarios):
            srv.actualizar_usuario(self.admin.pk, self.admin, base)
        activo = EstadoUsuario.objects.get(pk=ESTADO_ACTIVO)
        with self.assertRaises(srv.ErrorUsuarios):
            srv.actualizar_usuario(self.admin.pk, self.admin, {**base, "estado": activo, "rol": GRUPO_OPERADOR})

    def test_suspender_y_reactivar_empleado(self):
        otro = srv.crear_empleado(
            correo="otro@example.com", nombres="Otro", apellidos="Empleado", telefono="", rol=GRUPO_OPERADOR,
            password="Clave-Segura-789", codigo_empleado="EMP-020", cargo="Operador",
        )
        base = {"nombres": "Otro", "apellidos": "Empleado", "telefono": "", "rol": GRUPO_OPERADOR,
                "codigo_empleado": "EMP-020", "cargo": "Operador", "fecha_contratacion": None, "empleado_activo": True}
        srv.actualizar_usuario(otro.pk, self.admin, {**base, "estado": EstadoUsuario.objects.get(pk=ESTADO_SUSPENDIDO)})
        otro.refresh_from_db()
        self.assertFalse(otro.is_active)
        srv.actualizar_usuario(otro.pk, self.admin, {**base, "estado": EstadoUsuario.objects.get(pk=ESTADO_ACTIVO)})
        otro.refresh_from_db()
        self.assertTrue(otro.is_active)

    def test_cambio_de_rol_de_empleado(self):
        otro = srv.crear_empleado(
            correo="rol@example.com", nombres="Rol", apellidos="Cambio", telefono="", rol=GRUPO_OPERADOR,
            password="Clave-Segura-789", codigo_empleado="EMP-030", cargo="Operador",
        )
        srv.actualizar_usuario(otro.pk, self.admin, {
            "nombres": "Rol", "apellidos": "Cambio", "telefono": "", "rol": GRUPO_ADMINISTRADOR,
            "codigo_empleado": "EMP-030", "cargo": "Jefe", "fecha_contratacion": None, "empleado_activo": True,
            "estado": EstadoUsuario.objects.get(pk=ESTADO_ACTIVO),
        })
        self.assertEqual([g.name for g in otro.groups.all()], [GRUPO_ADMINISTRADOR])

    def test_contrasena_debil_en_servicio(self):
        with self.assertRaises(ValidationError):
            srv.crear_empleado(
                correo="d@example.com", nombres="D", apellidos="Debil", telefono="", rol=GRUPO_OPERADOR,
                password="123", codigo_empleado="EMP-040", cargo="x",
            )
