from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.catalogo.models import CategoriaServicio, Producto, Servicio

PRODUCTOS = (
    ("DEMO-001", "Soporte articulado para celular", "Soporte impreso en PLA, ajustable.", "6.50", 25, 5),
    ("DEMO-002", "Organizador de escritorio", "Organizador modular para lápices y notas.", "9.90", 12, 4),
    ("DEMO-003", "Maceta geométrica", "Maceta decorativa con diseño low-poly.", "7.25", 4, 5),
    ("DEMO-004", "Llavero personalizable", "Llavero con iniciales en relieve.", "2.50", 60, 10),
    ("DEMO-005", "Figura articulada", "Figura coleccionable con partes móviles.", "14.00", 0, 3),
    ("DEMO-006", "Porta audífonos", "Soporte de escritorio para audífonos.", "8.75", 18, 5),
)

SERVICIOS = (
    ("Impresión 3D", "Impresión por pieza", "Impresión de su modelo en el material elegido.", "12.00", True),
    ("Diseño 3D", "Diseño de pieza a medida", "Diseño de una pieza a partir de sus medidas.", "35.00", False),
    ("Modelado 3D", "Modelado desde boceto", "Modelado tridimensional a partir de un boceto.", "28.00", True),
    ("Asesorías", "Asesoría técnica", "Asesoría para preparar su proyecto de impresión.", "20.00", False),
    ("Prototipado", "Prototipo funcional", "Prototipo para validar un diseño antes de producir.", "45.00", True),
)


class Command(BaseCommand):
    help = "Crea productos y servicios de ejemplo (idempotente)."

    def add_arguments(self, parser):
        parser.add_argument("--forzar", action="store_true", help="Permite ejecutarlo con DEBUG=False.")

    @transaction.atomic
    def handle(self, *args, **opciones):
        if not settings.DEBUG and not opciones["forzar"]:
            raise CommandError("Solo se ejecuta con DEBUG=True (o use --forzar).")
        for sku, nombre, descripcion, precio, stock, minimo in PRODUCTOS:
            Producto.objects.get_or_create(
                sku=sku,
                defaults={
                    "nombre": nombre,
                    "descripcion": descripcion,
                    "precio": Decimal(precio),
                    "stock": stock,
                    "stock_minimo": minimo,
                },
            )
        for categoria, nombre, descripcion, precio, requiere in SERVICIOS:
            categoria_obj, _ = CategoriaServicio.objects.get_or_create(nombre=categoria)
            Servicio.objects.get_or_create(
                categoria=categoria_obj,
                nombre=nombre,
                defaults={
                    "descripcion": descripcion,
                    "precio_base": Decimal(precio),
                    "requiere_archivo": requiere,
                },
            )
        self.stdout.write(self.style.SUCCESS("Datos de ejemplo listos."))
