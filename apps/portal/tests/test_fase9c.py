import io
import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from apps.core.models import ConfiguracionNegocio
from apps.cotizaciones.tests.utiles import crear_cliente
from apps.usuarios.constants import GRUPO_ADMINISTRADOR, GRUPO_CLIENTE, GRUPO_OPERADOR
from apps.usuarios.models.empleado import Empleado
from apps.usuarios.tests.utiles import CLAVE, crear_usuario, iniciar_sesion


def imagen(nombre="foto.png", tamano=(300, 200), formato="PNG"):
    buffer = io.BytesIO()
    Image.new("RGB", tamano, (200, 40, 40)).save(buffer, format=formato)
    return SimpleUploadedFile(nombre, buffer.getvalue(), content_type="image/png")


class MediaTemporalMixin:
    def setUp(self):
        super().setUp()
        cache.clear()
        self._media = tempfile.mkdtemp()
        contexto = override_settings(MEDIA_ROOT=self._media)
        contexto.enable()
        self.addCleanup(contexto.disable)
        self.addCleanup(shutil.rmtree, self._media, ignore_errors=True)


class ScriptsDeVistaTests(TestCase):
    def test_las_vistas_nuevas_tienen_su_script(self):
        base = Path(settings.BASE_DIR) / "static" / "js"
        for ruta in (
            "vistas/operator/cuenta.js",
            "vistas/administrator/cuenta.js",
            "vistas/administrator/configuracion.js",
            "vistas/customer/cuenta.js",
            "components/foto.js",
        ):
            self.assertTrue((base / ruta).exists(), ruta)


class EstilosYAccesoTests(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def test_login_incorrecto_conserva_los_estilos(self):
        crear_usuario("ana@example.com", GRUPO_CLIENTE)
        respuesta = self.client.post(reverse("account_login"), {"login": "ana@example.com", "password": "clave-mala-1"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "css/app.css")
        self.assertContains(respuesta, 'id="form-ingreso"')

    def test_paginas_de_cuenta_usan_los_estilos(self):
        self.assertContains(self.client.get(reverse("account_reset_password")), "css/app.css")
        operador = crear_usuario("op@example.com", GRUPO_OPERADOR, is_staff=True)
        iniciar_sesion(self.client, operador)
        respuesta = self.client.get(reverse("account_change_password"))
        self.assertContains(respuesta, "css/app.css")
        self.assertContains(respuesta, reverse("operator:panel"))

    def test_enlace_para_saltar_al_contenido(self):
        respuesta = self.client.get(reverse("guest:inicio"))
        self.assertContains(respuesta, 'href="#contenido-principal"')
        self.assertContains(respuesta, 'id="contenido-principal"')


class BarraNavegacionTests(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def test_administrador_puede_volver_desde_la_vista_de_operador(self):
        admin = crear_usuario("admin@example.com", GRUPO_ADMINISTRADOR, is_staff=True)
        iniciar_sesion(self.client, admin)
        enlace = f'href="{reverse("administrator:dashboard")}"'
        self.assertContains(self.client.get(reverse("operator:clientes")), enlace)

    def test_operador_no_ve_enlaces_de_administracion(self):
        operador = crear_usuario("op@example.com", GRUPO_OPERADOR, is_staff=True)
        iniciar_sesion(self.client, operador)
        self.assertNotContains(self.client.get(reverse("operator:clientes")), f'href="{reverse("administrator:dashboard")}"')

    def test_administrador_ve_operacion_y_su_perfil_en_el_panel_admin(self):
        admin = crear_usuario("admin@example.com", GRUPO_ADMINISTRADOR, is_staff=True)
        iniciar_sesion(self.client, admin)
        respuesta = self.client.get(reverse("administrator:configuracion"))
        self.assertContains(respuesta, f'href="{reverse("operator:panel")}"')
        self.assertContains(respuesta, f'href="{reverse("administrator:cuenta")}"')

    def test_cliente_en_paginas_de_cuenta_ve_su_barra(self):
        usuario, _ = crear_cliente("ana@example.com")
        iniciar_sesion(self.client, usuario)
        respuesta = self.client.get(reverse("account_change_password"))
        self.assertContains(respuesta, reverse("customer:panel"))
        self.assertNotContains(respuesta, f'href="{reverse("operator:panel")}"')


class ConfiguracionNegocioTests(MediaTemporalMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.admin = crear_usuario("admin@example.com", GRUPO_ADMINISTRADOR, is_staff=True)
        iniciar_sesion(self.client, self.admin)
        self.url = reverse("administrator:configuracion")

    def datos(self, **extra):
        base = {
            "nombre_negocio": "Mi Taller 3D",
            "correo": "info@taller.test",
            "telefono": "+503 2200-0000",
            "sitio_web": "https://taller.test",
            "identificacion_fiscal": "",
            "direccion": "",
        }
        base.update(extra)
        return base

    def test_solo_el_administrador_entra(self):
        self.client.logout()
        operador = crear_usuario("op@example.com", GRUPO_OPERADOR, is_staff=True)
        iniciar_sesion(self.client, operador)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_muestra_formulario_y_parametros(self):
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, "Parámetros del sistema")
        self.assertContains(respuesta, "TASA_IMPUESTO")
        self.assertContains(respuesta, "13 %")

    def test_guarda_datos_y_crea_el_registro_si_no_existe(self):
        ConfiguracionNegocio.objects.all().delete()
        respuesta = self.client.post(self.url, self.datos())
        self.assertRedirects(respuesta, self.url)
        self.assertEqual(ConfiguracionNegocio.objects.count(), 1)
        self.assertContains(self.client.get(self.url), "Mi Taller 3D")
        self.client.post(self.url, self.datos(nombre_negocio="Taller Nuevo"))
        self.assertEqual(ConfiguracionNegocio.objects.count(), 1)
        self.assertEqual(ConfiguracionNegocio.objects.get().nombre_negocio, "Taller Nuevo")

    def test_datos_invalidos_no_se_guardan(self):
        ConfiguracionNegocio.objects.all().delete()
        respuesta = self.client.post(self.url, self.datos(nombre_negocio="", telefono="abc"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(ConfiguracionNegocio.objects.count(), 0)

    def test_logo_se_sube_se_reemplaza_y_se_quita(self):
        self.client.post(self.url, self.datos(logo_archivo=imagen(tamano=(1200, 400))))
        primero = ConfiguracionNegocio.objects.get().logo
        self.assertTrue(primero.startswith("negocio/"))
        with Image.open(default_storage.path(primero)) as logo:
            self.assertLessEqual(max(logo.size), 600)
        self.assertContains(self.client.get(self.url), ConfiguracionNegocio.objects.get().logo_url)
        self.client.post(self.url, self.datos(logo_archivo=imagen("otro.png")))
        segundo = ConfiguracionNegocio.objects.get().logo
        self.assertNotEqual(primero, segundo)
        self.assertFalse(default_storage.exists(primero))
        self.client.post(self.url, self.datos(quitar_logo="on"))
        self.assertIsNone(ConfiguracionNegocio.objects.get().logo)
        self.assertFalse(default_storage.exists(segundo))

    def test_logo_invalido_se_rechaza(self):
        ConfiguracionNegocio.objects.all().delete()
        configuracion = ConfiguracionNegocio.objects.create(nombre_negocio="Base")
        falso = SimpleUploadedFile("logo.png", b"esto no es una imagen", content_type="image/png")
        respuesta = self.client.post(self.url, self.datos(logo_archivo=falso))
        self.assertEqual(respuesta.status_code, 200)
        extension_no_permitida = self.client.post(self.url, self.datos(logo_archivo=imagen("a.gif")))
        self.assertEqual(extension_no_permitida.status_code, 200)
        configuracion.refresh_from_db()
        self.assertIsNone(configuracion.logo)
        self.assertEqual(configuracion.nombre_negocio, "Base")


class FotoDePerfilTests(MediaTemporalMixin, TestCase):
    def test_cliente_sube_reemplaza_y_quita_su_foto(self):
        usuario, _ = crear_cliente("ana@example.com")
        iniciar_sesion(self.client, usuario)
        destino = reverse("customer:cuenta")
        self.assertRedirects(self.client.post(reverse("customer:cuenta_foto"), {"foto": imagen(tamano=(640, 480))}), destino)
        usuario.refresh_from_db()
        primera = usuario.foto
        self.assertTrue(primera.startswith("perfiles/"))
        with Image.open(default_storage.path(primera)) as foto:
            self.assertEqual(foto.size, (256, 256))
        self.assertContains(self.client.get(destino), usuario.foto_url)
        self.client.post(reverse("customer:cuenta_foto"), {"foto": imagen("otra.png")})
        usuario.refresh_from_db()
        self.assertNotEqual(usuario.foto, primera)
        self.assertFalse(default_storage.exists(primera))
        self.client.post(reverse("customer:cuenta_foto"), {"quitar": "1"})
        usuario.refresh_from_db()
        self.assertIsNone(usuario.foto)

    def test_archivos_que_no_son_imagen_o_muy_grandes_se_rechazan(self):
        usuario, _ = crear_cliente("ana@example.com")
        iniciar_sesion(self.client, usuario)
        falso = SimpleUploadedFile("foto.png", b"no soy una imagen", content_type="image/png")
        self.client.post(reverse("customer:cuenta_foto"), {"foto": falso})
        usuario.refresh_from_db()
        self.assertIsNone(usuario.foto)
        with override_settings(IMAGEN_MAX_BYTES=100):
            self.client.post(reverse("customer:cuenta_foto"), {"foto": imagen(tamano=(400, 400))})
        usuario.refresh_from_db()
        self.assertIsNone(usuario.foto)
        self.client.post(reverse("customer:cuenta_foto"), {})
        usuario.refresh_from_db()
        self.assertIsNone(usuario.foto)

    def test_la_foto_aparece_en_la_barra(self):
        usuario, _ = crear_cliente("ana@example.com")
        iniciar_sesion(self.client, usuario)
        self.client.post(reverse("customer:cuenta_foto"), {"foto": imagen()})
        usuario.refresh_from_db()
        self.assertContains(self.client.get(reverse("customer:panel")), usuario.foto_url)

    def test_el_personal_sube_su_foto_y_los_roles_no_se_cruzan(self):
        operador = crear_usuario("op@example.com", GRUPO_OPERADOR, is_staff=True)
        iniciar_sesion(self.client, operador)
        self.assertRedirects(self.client.post(reverse("operator:cuenta_foto"), {"foto": imagen()}), reverse("operator:cuenta"))
        operador.refresh_from_db()
        self.assertTrue(operador.foto.startswith("perfiles/"))
        self.assertEqual(self.client.post(reverse("customer:cuenta_foto"), {"foto": imagen()}).status_code, 403)
        cliente, _ = crear_cliente("ana@example.com")
        self.client.logout()
        iniciar_sesion(self.client, cliente)
        self.assertEqual(self.client.post(reverse("operator:cuenta_foto"), {"foto": imagen()}).status_code, 403)


class CuentaPersonalTests(MediaTemporalMixin, TestCase):
    def test_el_cliente_no_entra_al_perfil_del_personal(self):
        usuario, _ = crear_cliente("ana@example.com")
        iniciar_sesion(self.client, usuario)
        self.assertEqual(self.client.get(reverse("operator:cuenta")).status_code, 403)

    def test_operador_ve_y_edita_sus_datos(self):
        operador = crear_usuario("op@example.com", GRUPO_OPERADOR, is_staff=True)
        Empleado.objects.create(usuario=operador, codigo_empleado="EMP-001", cargo="Operador de impresión")
        iniciar_sesion(self.client, operador)
        url = reverse("operator:cuenta")
        pagina = self.client.get(url)
        self.assertContains(pagina, "EMP-001")
        self.assertContains(pagina, "Operador de impresión")
        self.assertRedirects(
            self.client.post(url, {"nombres": "Carlos", "apellidos": "Ramírez", "telefono": "+503 7000-9999"}), url
        )
        operador.refresh_from_db()
        self.assertEqual((operador.nombres, operador.apellidos, operador.telefono), ("Carlos", "Ramírez", "+503 7000-9999"))

    def test_datos_invalidos_no_se_guardan(self):
        operador = crear_usuario("op@example.com", GRUPO_OPERADOR, is_staff=True)
        iniciar_sesion(self.client, operador)
        respuesta = self.client.post(reverse("operator:cuenta"), {"nombres": "Carlos9", "apellidos": "Ramírez", "telefono": "abc"})
        self.assertEqual(respuesta.status_code, 200)
        operador.refresh_from_db()
        self.assertEqual(operador.nombres, "Ana")

    def test_administrador_edita_su_perfil_sin_salir_del_panel_admin(self):
        admin = crear_usuario("admin@example.com", GRUPO_ADMINISTRADOR, is_staff=True)
        iniciar_sesion(self.client, admin)
        url = reverse("administrator:cuenta")
        self.assertContains(self.client.get(url), reverse("administrator:cuenta_foto"))
        self.assertRedirects(self.client.post(url, {"nombres": "Rosa", "apellidos": "Díaz", "telefono": ""}), url)
        admin.refresh_from_db()
        self.assertEqual((admin.nombres, admin.telefono), ("Rosa", None))
        self.assertRedirects(self.client.post(reverse("administrator:cuenta_foto"), {"foto": imagen()}), url)
