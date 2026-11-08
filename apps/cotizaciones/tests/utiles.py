import shutil
import tempfile
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from apps.catalogo.models import CategoriaServicio, Servicio
from apps.clientes.services.clientes import asegurar_cliente
from apps.usuarios.constants import GRUPO_CLIENTE, GRUPO_OPERADOR
from apps.usuarios.tests.utiles import crear_usuario

STL = (
    b"solid pieza\nfacet normal 0 0 0\nouter loop\nvertex 0 0 0\nvertex 1 0 0\n"
    b"vertex 0 1 0\nendloop\nendfacet\nendsolid pieza\n"
)


def crear_servicio(nombre="Impresión de prueba", precio="10.00", requiere_archivo=False, activo=True):
    categoria, _ = CategoriaServicio.objects.get_or_create(nombre="Categoría de prueba")
    return Servicio.objects.create(
        categoria=categoria,
        nombre=nombre,
        descripcion="Servicio de prueba",
        precio_base=Decimal(precio),
        requiere_archivo=requiere_archivo,
        activo=activo,
    )


def crear_cliente(correo):
    usuario = crear_usuario(correo, GRUPO_CLIENTE)
    return usuario, asegurar_cliente(usuario)


def crear_personal(correo, grupo=GRUPO_OPERADOR):
    return crear_usuario(correo, grupo, is_staff=True)


def archivo_stl(nombre="pieza.stl"):
    return SimpleUploadedFile(nombre, STL, content_type="application/octet-stream")


class AlmacenTemporalMixin:
    def setUp(self):
        super().setUp()
        self._tmp = tempfile.mkdtemp()
        contexto = override_settings(PRIVATE_MEDIA_ROOT=self._tmp)
        contexto.enable()
        self.addCleanup(contexto.disable)
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)
