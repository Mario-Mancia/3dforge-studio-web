import json
import os
import tempfile
from decimal import Decimal
from types import SimpleNamespace
from unittest import skipUnless
from unittest.mock import patch

from django.core import management
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.forms.models import model_to_dict
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.catalogo.selectors.catalogo import servicios_publicos
from apps.cotizaciones.modelos3d import analisis as modulo_analisis
from apps.cotizaciones.modelos3d import proceso
from apps.cotizaciones.modelos3d.errores import ErrorAnalisis
from apps.cotizaciones.modelos3d.estimacion import estimar, texto_tiempo
from apps.cotizaciones.models import ConfiguracionCotizador, Cotizacion, Filamento
from apps.cotizaciones.services import cotizaciones as servicios
from apps.cotizaciones.tests.utiles import AlmacenTemporalMixin, crear_cliente, crear_personal, crear_servicio
from apps.usuarios.constants import GRUPO_ADMINISTRADOR
from apps.usuarios.tests.utiles import crear_usuario, iniciar_sesion

try:
    import trimesh

    HAY_TRIMESH = True
except ImportError:
    HAY_TRIMESH = False

requiere_trimesh = skipUnless(HAY_TRIMESH, "trimesh no está instalado")

PARAMETROS = SimpleNamespace(
    grosor_pared_mm=Decimal("1.2"), caudal_mm3_s=Decimal("5"), seg_por_capa=Decimal("5"),
    desperdicio_pct=Decimal("0"), soporte_extra_pct=Decimal("0"), umbral_voladizo_pct=Decimal("8"),
    factor_caja_pct=Decimal("25"), tarifa_hora=Decimal("3"), cargo_fijo=Decimal("0"), minimo=Decimal("0"),
    margen_pct=Decimal("0"), cama_x_mm=220, cama_y_mm=220, cama_z_mm=250,
)
FILAMENTO = SimpleNamespace(material="PLA", color="Negro", densidad=Decimal("1.25"), precio_kg=Decimal("20"))
CUBO = {
    "volumen_mm3": 8000.0, "area_mm2": 2400.0, "extents_mm": [20.0, 20.0, 20.0], "triangulos": 12,
    "hermetica": True, "reparada": False, "voladizo_ratio": 0.0,
}
OPCIONES = {"escala": 100, "unidades": "mm", "relleno": 20, "calidad": "estandar", "soportes": "no", "cantidad": 1}


def con(**cambios):
    return {**OPCIONES, **cambios}


def parametros(**cambios):
    datos = dict(vars(PARAMETROS))
    datos.update(cambios)
    return SimpleNamespace(**datos)


def cubo_stl(lado=20, nombre="cubo.stl"):
    malla = trimesh.creation.box(extents=(lado, lado, lado))
    return SimpleUploadedFile(nombre, malla.export(file_type="stl"), content_type="application/octet-stream")


def crear_filamento(material="PLA", color="Negro"):
    return Filamento.objects.get_or_create(
        material=material, color=color, defaults={"densidad": Decimal("1.24"), "precio_kg": Decimal("20.00")}
    )[0]


class EstimacionTests(SimpleTestCase):
    def test_formula_con_valores_conocidos(self):
        resultado = estimar(CUBO, FILAMENTO, OPCIONES, PARAMETROS)
        self.assertTrue(resultado["cabe"])
        self.assertEqual(resultado["gramos"], 4.9)
        self.assertEqual(resultado["capas"], 100)
        self.assertEqual(resultado["tiempo_texto"], "21 min")
        self.assertEqual(resultado["precio_unitario"], Decimal("1.16"))
        self.assertEqual(resultado["total"], resultado["subtotal"] + resultado["impuesto"])
        self.assertEqual(resultado["confianza"], "alta")

    def test_mas_relleno_usa_mas_material_y_cuesta_mas(self):
        poco = estimar(CUBO, FILAMENTO, con(relleno=10), PARAMETROS)
        mucho = estimar(CUBO, FILAMENTO, con(relleno=100), PARAMETROS)
        self.assertGreater(mucho["gramos"], poco["gramos"])
        self.assertGreater(mucho["precio_unitario"], poco["precio_unitario"])

    def test_calidad_fina_tarda_mas(self):
        fina = estimar(CUBO, FILAMENTO, con(calidad="fina"), PARAMETROS)
        borrador = estimar(CUBO, FILAMENTO, con(calidad="borrador"), PARAMETROS)
        self.assertGreater(fina["horas"], borrador["horas"])

    def test_escala_y_unidades_cambian_el_tamano(self):
        doble = estimar(CUBO, FILAMENTO, con(escala=200), PARAMETROS)
        base = estimar(CUBO, FILAMENTO, OPCIONES, PARAMETROS)
        self.assertEqual(doble["dimensiones"], [40.0, 40.0, 40.0])
        self.assertGreater(doble["gramos"], base["gramos"] * 4)
        centimetros = estimar(CUBO, FILAMENTO, con(unidades="cm"), PARAMETROS)
        self.assertEqual(centimetros["dimensiones"], [200.0, 200.0, 200.0])
        self.assertTrue(centimetros["cabe"])
        pulgadas = estimar(CUBO, FILAMENTO, con(unidades="in"), PARAMETROS)
        self.assertFalse(pulgadas["cabe"])
        self.assertIn("no cabe", pulgadas["mensaje_cabida"])

    def test_minimo_cargo_fijo_y_cantidad(self):
        con_minimo = estimar(CUBO, FILAMENTO, OPCIONES, parametros(minimo=Decimal("10")))
        self.assertEqual(con_minimo["precio_unitario"], Decimal("10.00"))
        dos = estimar(CUBO, FILAMENTO, con(cantidad=2), parametros(minimo=Decimal("10")))
        self.assertEqual(dos["precio_unitario"], Decimal("5.00"))
        fijo = estimar(CUBO, FILAMENTO, con(cantidad=4), parametros(cargo_fijo=Decimal("4")))
        self.assertGreater(fijo["precio_unitario"], Decimal("1.16"))

    def test_malla_con_huecos_usa_la_caja_y_baja_la_confianza(self):
        malla_rota = {**CUBO, "hermetica": False, "volumen_mm3": 0.0}
        resultado = estimar(malla_rota, FILAMENTO, OPCIONES, PARAMETROS)
        self.assertEqual(resultado["confianza"], "baja")
        self.assertTrue(resultado["advertencias"])
        reparada = estimar({**CUBO, "reparada": True}, FILAMENTO, OPCIONES, PARAMETROS)
        self.assertEqual(reparada["confianza"], "media")

    def test_soportes_automaticos_segun_voladizo(self):
        con_voladizo = {**CUBO, "voladizo_ratio": 0.2}
        self.assertTrue(estimar(con_voladizo, FILAMENTO, con(soportes="auto"), PARAMETROS)["soportes"])
        self.assertFalse(estimar(con_voladizo, FILAMENTO, con(soportes="no"), PARAMETROS)["soportes"])
        self.assertFalse(estimar(CUBO, FILAMENTO, con(soportes="auto"), PARAMETROS)["soportes"])
        sin = estimar(con_voladizo, FILAMENTO, con(soportes="no"), PARAMETROS)
        con_soporte = estimar(con_voladizo, FILAMENTO, con(soportes="si"), PARAMETROS)
        self.assertGreater(con_soporte["gramos"], sin["gramos"])

    def test_piezas_diminutas_advierten_de_las_unidades(self):
        diminuta = {**CUBO, "extents_mm": [2.0, 2.0, 2.0], "volumen_mm3": 8.0, "area_mm2": 24.0}
        resultado = estimar(diminuta, FILAMENTO, OPCIONES, PARAMETROS)
        self.assertEqual(resultado["confianza"], "baja")

    def test_texto_de_tiempo(self):
        self.assertEqual(texto_tiempo(0.0), "1 min")
        self.assertEqual(texto_tiempo(0.75), "45 min")
        self.assertEqual(texto_tiempo(2.0), "2 h")
        self.assertEqual(texto_tiempo(3.34), "3 h 20 min")


@requiere_trimesh
class AnalisisTests(TestCase):
    def test_cubo_en_el_proceso_de_analisis(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = os.path.join(carpeta, "cubo.stl")
            with open(ruta, "wb") as archivo:
                archivo.write(cubo_stl().read())
            resultado = proceso.analizar_seguro(ruta, "stl", 100000)
        self.assertAlmostEqual(resultado["volumen_mm3"], 8000.0, delta=1)
        self.assertAlmostEqual(resultado["area_mm2"], 2400.0, delta=1)
        self.assertEqual([round(v) for v in resultado["extents_mm"]], [20, 20, 20])
        self.assertTrue(resultado["hermetica"])
        self.assertEqual(resultado["triangulos"], 12)
        self.assertEqual(resultado["voladizo_ratio"], 0.0)

    def test_analisis_en_proceso_aparte(self):
        resultado = modulo_analisis.analizar_archivo(cubo_stl(30), 100000, aislado=True)
        self.assertAlmostEqual(resultado["volumen_mm3"], 27000.0, delta=1)

    def test_una_esfera_tiene_voladizo(self):
        esfera = trimesh.creation.icosphere(subdivisions=2, radius=10)
        archivo = SimpleUploadedFile("esfera.stl", esfera.export(file_type="stl"))
        resultado = modulo_analisis.analizar_archivo(archivo, 100000, aislado=False)
        self.assertGreater(resultado["voladizo_ratio"], 0.1)

    def test_errores_controlados(self):
        with self.assertRaises(ErrorAnalisis):
            modulo_analisis.analizar_archivo(SimpleUploadedFile("foto.png", b"x"), 1000, aislado=False)
        with self.assertRaises(ErrorAnalisis):
            modulo_analisis.analizar_archivo(SimpleUploadedFile("roto.stl", b"esto no es un modelo"), 1000, aislado=False)
        with self.assertRaises(ErrorAnalisis) as contexto:
            modulo_analisis.analizar_archivo(cubo_stl(), 5, aislado=False)
        self.assertIn("triángulos", str(contexto.exception))

    def test_analisis_reenviado_por_el_navegador_se_valida(self):
        valido = modulo_analisis.analizar_archivo(cubo_stl(), 1000, aislado=False)
        self.assertEqual(modulo_analisis.analisis_desde_json(json.dumps(valido))["triangulos"], 12)
        for malo in ("", "no es json", "[]", json.dumps({**valido, "extents_mm": [1, 2]}), json.dumps({**valido, "volumen_mm3": -1}), json.dumps({**valido, "voladizo_ratio": 5})):
            with self.assertRaises(ErrorAnalisis):
                modulo_analisis.analisis_desde_json(malo)


@requiere_trimesh
@override_settings(COTIZADOR_AISLADO=False)
class CotizadorClienteTests(AlmacenTemporalMixin, TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.usuario, self.cliente = crear_cliente("ana@example.com")
        iniciar_sesion(self.client, self.usuario)
        self.filamento = crear_filamento()

    def opciones(self, **cambios):
        datos = {
            "filamento": self.filamento.pk, "relleno": 20, "calidad": "estandar", "escala": 100,
            "unidades": "mm", "soportes": "auto", "cantidad": 1,
        }
        datos.update(cambios)
        return datos

    def enviar_3d(self, archivo=None, **cambios):
        datos = {"tipo_cotizacion": "3d", "archivo": archivo or cubo_stl(), **self.opciones(**cambios)}
        return self.client.post(reverse("customer:cotizar"), datos)

    def test_la_pantalla_ofrece_las_dos_formas_de_cotizar(self):
        respuesta = self.client.get(reverse("customer:cotizar"))
        for texto in ('id="form-3d"', "Impresión 3D automática", "Otros servicios", 'id="panel-manual"', "aproximadas"):
            self.assertContains(respuesta, texto)
        self.assertEqual(respuesta.context["pestana"], "3d")
        self.assertEqual(self.client.get(reverse("customer:cotizar"), {"tipo": "manual"}).context["pestana"], "manual")

    def test_sin_filamentos_solo_queda_el_formulario(self):
        Filamento.objects.update(activo=False)
        respuesta = self.client.get(reverse("customer:cotizar"))
        self.assertNotContains(respuesta, 'id="form-3d"')
        self.assertContains(respuesta, "aún no tiene filamentos")
        self.assertEqual(respuesta.context["pestana"], "manual")

    def test_estimacion_en_vivo_con_archivo_y_luego_solo_con_el_analisis(self):
        primera = self.client.post(reverse("customer:cotizar_estimar"), {**self.opciones(), "archivo": cubo_stl()})
        self.assertEqual(primera.status_code, 200, primera.content)
        cuerpo = primera.json()
        self.assertTrue(cuerpo["ok"])
        self.assertEqual(cuerpo["estimacion"]["dimensiones"], [20.0, 20.0, 20.0])
        self.assertIn("aproximadas", cuerpo["estimacion"]["aviso"])
        segunda = self.client.post(
            reverse("customer:cotizar_estimar"), {**self.opciones(escala=200), "analisis": json.dumps(cuerpo["analisis"])}
        )
        self.assertEqual(segunda.status_code, 200)
        self.assertEqual(segunda.json()["estimacion"]["dimensiones"], [40.0, 40.0, 40.0])
        self.assertGreater(Decimal(segunda.json()["estimacion"]["total"]), Decimal(cuerpo["estimacion"]["total"]))

    def test_estimacion_rechaza_archivos_y_datos_invalidos(self):
        imagen = SimpleUploadedFile("foto.png", b"\x89PNG\r\n\x1a\n" + b"0" * 20)
        respuesta = self.client.post(reverse("customer:cotizar_estimar"), {**self.opciones(), "archivo": imagen})
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(respuesta.json()["ok"])
        sin_nada = self.client.post(reverse("customer:cotizar_estimar"), self.opciones())
        self.assertEqual(sin_nada.status_code, 400)
        mala_opcion = self.client.post(reverse("customer:cotizar_estimar"), {**self.opciones(relleno=77), "archivo": cubo_stl()})
        self.assertEqual(mala_opcion.status_code, 400)
        self.assertIn("relleno", mala_opcion.json()["errores"])

    def test_la_estimacion_tiene_limite_por_minuto(self):
        reloj_fijo = SimpleNamespace(time=lambda: 12345.0)
        with patch("apps.portal.customer.views.cotizar.LIMITE_ANALISIS_POR_MINUTO", 2), patch(
            "apps.portal.customer.views.cotizar.time", reloj_fijo
        ):
            estados = [
                self.client.post(reverse("customer:cotizar_estimar"), {**self.opciones(), "archivo": cubo_stl()}).status_code
                for _ in range(3)
            ]
        self.assertEqual(estados, [200, 200, 429])

    def test_solo_clientes_estiman(self):
        self.client.logout()
        self.assertEqual(self.client.post(reverse("customer:cotizar_estimar"), self.opciones()).status_code, 302)
        iniciar_sesion(self.client, crear_personal("op@example.com"))
        self.assertEqual(self.client.post(reverse("customer:cotizar_estimar"), self.opciones()).status_code, 403)

    def test_la_solicitud_automatica_crea_una_cotizacion_normal_con_importes_preliminares(self):
        respuesta = self.enviar_3d(descripcion="Soporte de prueba", comentarios="Lo necesito pronto", cantidad=2)
        cotizacion = Cotizacion.objects.get()
        self.assertRedirects(respuesta, reverse("customer:cotizacion", args=[cotizacion.pk]))
        self.assertEqual(cotizacion.estado, "SOLICITADA")
        self.assertTrue(cotizacion.codigo.startswith("COT-"))
        detalle = cotizacion.detalles.get()
        self.assertEqual(detalle.cantidad, 2)
        self.assertTrue(detalle.descripcion.startswith("Impresión 3D: Soporte de prueba"))
        self.assertGreater(detalle.precio_unitario, 0)
        self.assertEqual(cotizacion.total, cotizacion.subtotal + cotizacion.impuesto)
        self.assertEqual(detalle.especificaciones["Tipo"], "Cotización automática 3D")
        self.assertEqual(detalle.especificaciones["Filamento"], "PLA Negro")
        self.assertIn("Lo necesito pronto", cotizacion.solicitud)
        self.assertEqual(cotizacion.archivos.count(), 1)
        self.assertEqual(cotizacion.archivos.get().formato, "STL")
        self.assertNotIn(detalle.servicio, servicios_publicos())

    def test_el_cliente_y_el_operador_ven_el_aviso_y_el_flujo_normal_continua(self):
        self.enviar_3d()
        cotizacion = Cotizacion.objects.get()
        self.assertContains(self.client.get(reverse("customer:cotizacion", args=[cotizacion.pk])), "aproximadas")
        operador = crear_personal("operador@example.com")
        self.client.logout()
        iniciar_sesion(self.client, operador)
        self.assertContains(self.client.get(reverse("operator:cotizacion", args=[cotizacion.pk])), "Cotización automática 3D")
        detalle = cotizacion.detalles.get()
        lineas = [{"id": detalle.pk, "cantidad": detalle.cantidad, "precio_unitario": Decimal("9.50"), "descuento": Decimal("0")}]
        servicios.revisar_cotizacion(cotizacion.pk, operador, lineas)
        servicios.enviar_cotizacion(cotizacion.pk, operador)
        cotizacion.refresh_from_db()
        self.assertEqual(cotizacion.estado, "ENVIADA")
        self.client.logout()
        iniciar_sesion(self.client, self.usuario)
        self.assertNotContains(self.client.get(reverse("customer:cotizacion", args=[cotizacion.pk])), "data-estimacion-automatica")
        servicios.aceptar_cotizacion(cotizacion.pk, self.usuario)

    def test_formatos_y_tamanos_no_validos_se_rechazan(self):
        imagen = SimpleUploadedFile("foto.png", b"\x89PNG\r\n\x1a\n" + b"0" * 20)
        respuesta = self.enviar_3d(imagen)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "STL, OBJ o 3MF")
        falso = SimpleUploadedFile("roto.stl", b"esto no es un modelo 3d de verdad")
        self.assertEqual(self.enviar_3d(falso).status_code, 200)
        enorme = self.enviar_3d(cubo_stl(150), escala=200)
        self.assertEqual(enorme.status_code, 200)
        self.assertContains(enorme, "no cabe")
        self.assertEqual(Cotizacion.objects.count(), 0)

    def test_un_filamento_inactivo_no_se_puede_elegir(self):
        inactivo = crear_filamento("ABS", "Rojo")
        inactivo.activo = False
        inactivo.save()
        respuesta = self.enviar_3d(filamento=inactivo.pk)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Cotizacion.objects.count(), 0)

    def test_la_cotizacion_manual_sigue_funcionando(self):
        servicio = crear_servicio()
        datos = {"tipo_cotizacion": "manual", "servicio": servicio.pk, "cantidad": "1", "descripcion": "Modelado", "solicitud": "Necesito un modelado a medida."}
        respuesta = self.client.post(reverse("customer:cotizar"), datos)
        cotizacion = Cotizacion.objects.get()
        self.assertRedirects(respuesta, reverse("customer:cotizacion", args=[cotizacion.pk]))
        self.assertEqual(cotizacion.detalles.get().servicio, servicio)
        malo = self.client.post(reverse("customer:cotizar"), {"tipo_cotizacion": "manual", "cantidad": "1"})
        self.assertEqual(malo.status_code, 200)
        self.assertEqual(malo.context["pestana"], "manual")


class CotizadorAdministradorTests(TestCase):
    def setUp(self):
        super().setUp()
        self.admin = crear_usuario("admin@example.com", GRUPO_ADMINISTRADOR, is_staff=True)
        iniciar_sesion(self.client, self.admin)

    def test_solo_el_administrador_accede(self):
        self.client.logout()
        iniciar_sesion(self.client, crear_personal("op@example.com"))
        self.assertEqual(self.client.get(reverse("administrator:cotizador")).status_code, 403)

    def test_la_barra_del_administrador_enlaza_al_cotizador(self):
        respuesta = self.client.get(reverse("administrator:configuracion"))
        self.assertContains(respuesta, f'href="{reverse("administrator:cotizador")}"')

    def test_parametros_se_ven_y_se_guardan(self):
        self.assertContains(self.client.get(reverse("administrator:cotizador")), "Cómo se calcula")
        datos = {c: str(v) for c, v in model_to_dict(ConfiguracionCotizador.obtener(), exclude=["id"]).items()}
        datos["margen_pct"] = "35"
        self.assertRedirects(self.client.post(reverse("administrator:cotizador"), datos), reverse("administrator:cotizador"))
        self.assertEqual(ConfiguracionCotizador.obtener().margen_pct, Decimal("35.00"))
        datos["cama_x_mm"] = "5"
        self.assertEqual(self.client.post(reverse("administrator:cotizador"), datos).status_code, 200)
        self.assertEqual(ConfiguracionCotizador.obtener().cama_x_mm, 220)

    def test_filamentos_crear_editar_y_activar(self):
        url = reverse("administrator:filamento_crear")
        datos = {"material": "PETG", "color": "Verde", "densidad": "1.27", "precio_kg": "25.00", "activo": "on"}
        self.assertRedirects(self.client.post(url, datos), reverse("administrator:cotizador"))
        filamento = Filamento.objects.get(material="PETG", color="Verde")
        self.assertEqual(self.client.post(url, datos).status_code, 200)
        self.assertEqual(Filamento.objects.filter(material="PETG", color="Verde").count(), 1)
        malo = self.client.post(url, {**datos, "color": "Azul", "densidad": "9"})
        self.assertEqual(malo.status_code, 200)
        editar = reverse("administrator:filamento_editar", args=[filamento.pk])
        self.client.post(editar, {**datos, "precio_kg": "30.00"})
        filamento.refresh_from_db()
        self.assertEqual(filamento.precio_kg, Decimal("30.00"))
        self.client.post(reverse("administrator:filamento_activo", args=[filamento.pk]))
        filamento.refresh_from_db()
        self.assertFalse(filamento.activo)
        self.assertContains(self.client.get(reverse("administrator:cotizador")), "PETG Verde")

    def test_comando_de_siembra_es_idempotente(self):
        management.call_command("sembrar_cotizador", verbosity=0)
        total = Filamento.objects.count()
        self.assertGreaterEqual(total, 5)
        management.call_command("sembrar_cotizador", verbosity=0)
        self.assertEqual(Filamento.objects.count(), total)
        self.assertEqual(ConfiguracionCotizador.objects.count(), 1)
