import io
import shutil
import tempfile
from decimal import Decimal

from unittest.mock import patch

from django.core import mail
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from apps.catalogo.models import Producto
from apps.core.models import ConfiguracionNegocio
from apps.cotizaciones.services import cotizaciones as servicios_cot
from apps.cotizaciones.tests.utiles import AlmacenTemporalMixin, crear_cliente, crear_personal, crear_servicio
from apps.encargos.services import compras, encargos
from apps.facturacion.models import Factura
from apps.notificaciones import correo as modulo_correo
from apps.notificaciones.correo import CID_MARCA, COLOR_MARCA, construir_correo, icono_cubo
from apps.notificaciones.services.notificaciones import notificar
from apps.pagos.models import EstadoPago, MetodoPago, Pago
from apps.usuarios.constants import GRUPO_ADMINISTRADOR, GRUPO_OPERADOR
from apps.usuarios.tests.utiles import crear_usuario, iniciar_sesion

SITIO = "https://taller.test"


def html_de(correo):
    return correo.alternatives[0][0]


def logo_adjunto(correo):
    """Bytes del logo incrustado (Content-ID) en el mensaje ya armado, o None."""
    for parte in correo.message().walk():
        if parte.get("Content-ID") == f"<{CID_MARCA}>":
            return parte.get_payload(decode=True)
    return None


def tiene_parte_related(correo):
    return any(parte.get_content_type() == "multipart/related" for parte in correo.message().walk())


class MarcaEnCorreosTests(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        ConfiguracionNegocio.objects.all().delete()
        self._media = tempfile.mkdtemp()
        contexto = override_settings(MEDIA_ROOT=self._media)
        contexto.enable()
        self.addCleanup(contexto.disable)
        self.addCleanup(shutil.rmtree, self._media, ignore_errors=True)

    def correo(self):
        return construir_correo(
            "ana@example.com", "Asunto de prueba", "Titulo de prueba", nombre="Ana",
            parrafos=["Primer párrafo.", "Segundo párrafo."], detalles=[("Total", "$10.00")],
            boton={"texto": "Ver mi cotización", "url": f"{SITIO}/cliente/cotizaciones/1/"},
        )

    def test_encabezado_con_el_color_el_nombre_y_el_icono_por_defecto(self):
        correo = self.correo()
        html = html_de(correo)
        for texto in (COLOR_MARCA, "3DForge Studio", f"cid:{CID_MARCA}", "Titulo de prueba", "Hola Ana", "Primer párrafo.", "Total", "$10.00", "Ver mi cotización"):
            self.assertIn(texto, html)
        self.assertNotIn("background:#ffffff;border-radius:8px;padding:5px 8px", html)
        self.assertTrue(tiene_parte_related(correo))
        icono = Image.open(io.BytesIO(logo_adjunto(correo)))
        self.assertEqual(icono.size, (96, 96))
        self.assertIsNotNone(icono.getchannel("A").getbbox())
        self.assertIn("Ver mi cotización: " + f"{SITIO}/cliente/cotizaciones/1/", correo.body)
        self.assertIn("Total: $10.00", correo.body)
        self.assertNotIn("&amp;", correo.body)

    def test_con_logo_configurado_se_usa_el_logo_y_el_nombre_del_negocio(self):
        buffer = io.BytesIO()
        Image.new("RGB", (300, 100), (20, 120, 200)).save(buffer, format="WEBP")
        ruta = default_storage.save("negocio/logo.webp", ContentFile(buffer.getvalue()))
        ConfiguracionNegocio.objects.all().delete()
        ConfiguracionNegocio.objects.create(
            nombre_negocio="Taller Prueba", correo="info@taller.test", telefono="+503 2200-0000", logo=ruta
        )
        cache.clear()
        correo = self.correo()
        html = html_de(correo)
        self.assertIn("Taller Prueba", html)
        self.assertIn("background:#ffffff;border-radius:8px;padding:5px 8px", html)
        self.assertIn("info@taller.test", html)
        logo = Image.open(io.BytesIO(logo_adjunto(correo)))
        self.assertEqual(logo.format, "PNG")
        self.assertEqual(logo.size[1], 96)
        self.assertGreater(logo.size[0], logo.size[1])

    def test_si_el_logo_esta_roto_se_vuelve_al_icono(self):
        ConfiguracionNegocio.objects.all().delete()
        ConfiguracionNegocio.objects.create(nombre_negocio="Taller Prueba", logo="negocio/no-existe.png")
        correo = self.correo()
        self.assertEqual(Image.open(io.BytesIO(logo_adjunto(correo))).size, (96, 96))
        self.assertNotIn("padding:5px 8px", html_de(correo))

    def test_sin_imagen_el_correo_no_referencia_el_logo(self):
        correo = construir_correo("ana@example.com", "Asunto", "Titulo", con_imagen=False)
        self.assertNotIn("cid:", html_de(correo))
        self.assertIsNone(logo_adjunto(correo))

    def test_el_mensaje_se_arma_con_la_api_moderna_de_django(self):
        correo = self.correo()
        mensaje = correo.message()
        tipos = [parte.get_content_type() for parte in mensaje.walk()]
        for esperado in ("multipart/alternative", "text/plain", "multipart/related", "text/html", "image/png"):
            self.assertIn(esperado, tipos)
        self.assertFalse(hasattr(correo, "mixed_subtype"))
        imagenes = [parte for parte in mensaje.walk() if parte.get_content_type() == "image/png"]
        self.assertEqual(len(imagenes), 1)
        self.assertEqual(imagenes[0].get_content_disposition(), "inline")
        self.assertEqual(imagenes[0]["Content-ID"], f"<{CID_MARCA}>")

    def test_el_icono_por_defecto_es_blanco_sobre_transparente(self):
        icono = icono_cubo(96)
        self.assertEqual(icono.mode, "RGBA")
        self.assertEqual(icono.getpixel((0, 0))[3], 0)


@override_settings(SITIO_URL=SITIO)
class CorreosDeEventosTests(AlmacenTemporalMixin, TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.usuario, self.cliente = crear_cliente("ana@example.com")
        self.operador = crear_personal("operador@example.com")

    def test_cotizacion_enviada_detalla_importes_y_enlaza_a_la_cotizacion(self):
        servicio = crear_servicio()
        cotizacion = servicios_cot.solicitar_cotizacion(
            self.cliente, self.usuario, servicio, Decimal("2"), "Pieza especial", "Necesito una pieza especial."
        )
        lineas = [{"id": d.pk, "cantidad": Decimal("2"), "precio_unitario": Decimal("15.00"), "descuento": Decimal("0")} for d in cotizacion.detalles.all()]
        servicios_cot.revisar_cotizacion(cotizacion.pk, self.operador, lineas, observaciones="Entrega en 5 días", plazo_entrega_dias=5)
        with self.captureOnCommitCallbacks(execute=True):
            servicios_cot.enviar_cotizacion(cotizacion.pk, self.operador)
        cliente = [c for c in mail.outbox if c.to == ["ana@example.com"]]
        self.assertEqual(len(cliente), 1)
        correo = cliente[0]
        self.assertEqual(correo.subject, f"Cotización {cotizacion.codigo} disponible")
        html = html_de(correo)
        for texto in ("Ver mi cotización", f"{SITIO}{reverse('customer:cotizacion', args=[cotizacion.pk])}", "Pieza especial", "2 × $15.00 = $30.00", "$33.90", "Plazo de entrega", "5 días", "Válida hasta", "Entrega en 5 días", COLOR_MARCA, "Soporte"):
            self.assertIn(texto, html)
        self.assertIn("Total: $33.90", correo.body)
        self.assertIn(f"{SITIO}{reverse('customer:cotizacion', args=[cotizacion.pk])}", correo.body)
        self.assertTrue(tiene_parte_related(correo))
        self.assertIsNotNone(logo_adjunto(correo))

    def test_pedido_cancelado_explica_que_paso(self):
        producto = Producto.objects.create(sku="MAIL-001", nombre="Producto correo", precio=Decimal("10.00"), stock=5, stock_minimo=1)
        with self.captureOnCommitCallbacks(execute=True):
            pedido = compras.confirmar_compra_api(self.cliente, self.usuario, [{"producto_id": producto.pk, "cantidad": 1}], "token-correo-0001")
        registrado = [c for c in mail.outbox if c.subject.startswith("Pedido") and "registrado" in c.subject]
        self.assertEqual(len(registrado), 1)
        self.assertIn("Compra en la tienda", html_de(registrado[0]))
        self.assertIn(f"{SITIO}{reverse('customer:pedido', args=[pedido.pk])}", html_de(registrado[0]))
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            encargos.cancelar_por_cliente(pedido.pk, self.usuario)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Su pedido fue cancelado", html_de(mail.outbox[0]))
        self.assertIn("Cancelado", html_de(mail.outbox[0]))

    def test_pago_registrado_informa_monto_metodo_y_saldo(self):
        factura = Factura.objects.create(
            cliente=self.cliente, numero_factura="FAC-MAIL-1", nombre_facturacion="Ana",
            subtotal=Decimal("50.00"), total=Decimal("50.00"), saldo_pendiente=Decimal("50.00"),
        )
        metodo, _ = MetodoPago.objects.get_or_create(nombre="Efectivo")
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            Pago.objects.create(factura=factura, metodo_pago=metodo, monto=Decimal("20.00"), estado=EstadoPago.CONFIRMADO)
        pagos = [c for c in mail.outbox if c.subject.startswith("Pago #")]
        self.assertEqual(len(pagos), 1)
        html = html_de(pagos[0])
        for texto in ("Monto pagado", "$20.00", "Efectivo", "Saldo pendiente", "FAC-MAIL-1", "Ver mi factura"):
            self.assertIn(texto, html)


@override_settings(SITIO_URL=SITIO)
class ReintentoSinImagenTests(TestCase):
    def test_si_falla_el_envio_con_logo_se_reintenta_sin_el(self):
        usuario, _ = crear_cliente("ana@example.com")
        original = modulo_correo.construir_correo
        llamadas = []

        def con_fallo(*args, **kwargs):
            llamadas.append(kwargs.get("con_imagen", True))
            if kwargs.get("con_imagen", True):
                raise RuntimeError("fallo simulado")
            return original(*args, **kwargs)

        with patch("apps.notificaciones.services.notificaciones.construir_correo", side_effect=con_fallo):
            with self.captureOnCommitCallbacks(execute=True):
                notificar(usuario, "Aviso con correo", "Mensaje", "cotizacion", 1, correo=True)
        self.assertEqual(llamadas, [True, False])
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn("cid:", html_de(mail.outbox[0]))


class LoginConScriptTests(TestCase):
    def test_el_login_con_error_carga_el_script_de_acceso(self):
        crear_cliente("ana@example.com")
        respuesta = self.client.post(reverse("account_login"), {"login": "ana@example.com", "password": "clave-mala-1"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "js/vistas/guest/acceso.js")
        self.assertContains(respuesta, "toggle-password")

    def test_el_script_de_acceso_no_se_carga_dos_veces(self):
        contenido = self.client.get(reverse("guest:acceso")).content.decode()
        self.assertEqual(contenido.count("js/vistas/guest/acceso.js"), 1)


@override_settings(SITIO_URL=SITIO)
class CorreosDeCuentaTests(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def test_el_correo_de_confirmacion_lleva_la_marca_y_el_enlace(self):
        import json

        datos = {"nombres": "Luis", "apellidos": "Pérez", "correo": "luis.correo@example.com", "password": "Clave-Segura-123"}
        self.client.post(reverse("api:registro"), json.dumps(datos), content_type="application/json")
        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        html = html_de(correo)
        prefijo = reverse("account_confirm_email", args=["CLAVEX"]).split("CLAVEX")[0]
        for texto in ("Confirmar mi correo", prefijo, "Hola Luis", COLOR_MARCA, f"cid:{CID_MARCA}"):
            self.assertIn(texto, html)
        self.assertIn(prefijo, correo.body)
        self.assertIn("Hola Luis", correo.body)
        self.assertTrue(tiene_parte_related(correo))
        self.assertIsNotNone(logo_adjunto(correo))

    def test_el_correo_de_restablecer_contrasena_lleva_la_marca_y_el_enlace(self):
        import json

        crear_cliente("ana@example.com")
        self.client.post(reverse("api:recuperar"), json.dumps({"correo": "ana@example.com"}), content_type="application/json")
        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        html = html_de(correo)
        prefijo = reverse("account_reset_password_from_key", kwargs={"uidb36": "UIDX", "key": "KEYX"}).split("UIDX")[0]
        for texto in ("Elegir una contraseña nueva", prefijo, COLOR_MARCA):
            self.assertIn(texto, html)
        self.assertIn(prefijo, correo.body)


class BarraAdministradorTests(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        iniciar_sesion(self.client, crear_usuario("admin@example.com", GRUPO_ADMINISTRADOR, is_staff=True))

    def test_los_catalogos_y_la_gestion_viven_en_menus_desplegables(self):
        html = self.client.get(reverse("administrator:configuracion")).content.decode()
        self.assertIn("Catálogos", html)
        self.assertIn("Gestión", html)
        self.assertGreaterEqual(html.count('data-bs-toggle="dropdown"'), 3)
        inicio_catalogos = html.index("Catálogos")
        for nombre in ("administrator:inventario", "administrator:servicios", "administrator:cotizador"):
            self.assertIn(f'href="{reverse(nombre)}"', html[inicio_catalogos:])
        for nombre in ("administrator:usuarios", "administrator:configuracion", "administrator:ventas", "operator:panel", "administrator:dashboard"):
            self.assertIn(f'href="{reverse(nombre)}"', html)

    def test_el_grupo_se_marca_activo_en_sus_paginas(self):
        self.assertIn("dropdown-toggle active", self.client.get(reverse("administrator:inventario")).content.decode())
        self.assertIn("dropdown-toggle active", self.client.get(reverse("administrator:cotizador")).content.decode())
        self.assertIn("dropdown-toggle active", self.client.get(reverse("administrator:usuarios")).content.decode())

    def test_el_operador_no_ve_los_menus_de_administracion(self):
        self.client.logout()
        iniciar_sesion(self.client, crear_usuario("op@example.com", GRUPO_OPERADOR, is_staff=True))
        html = self.client.get(reverse("operator:clientes")).content.decode()
        self.assertNotIn("Catálogos", html)
        self.assertNotIn(f'href="{reverse("administrator:inventario")}"', html)
