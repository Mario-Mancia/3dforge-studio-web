from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.cotizaciones.models import ConfiguracionCotizador, Filamento

FILAMENTOS = (
    ("PLA", "Negro", "1.240", "20.00"),
    ("PLA", "Blanco", "1.240", "20.00"),
    ("PLA", "Gris", "1.240", "20.00"),
    ("PETG", "Negro", "1.270", "24.00"),
    ("PETG", "Transparente", "1.270", "24.00"),
    ("ABS", "Negro", "1.040", "22.00"),
    ("TPU", "Negro", "1.210", "35.00"),
)


class Command(BaseCommand):
    help = "Crea los parametros por defecto del cotizador 3D y un catalogo inicial de filamentos (no pisa lo existente)."

    def handle(self, *args, **opciones):
        ConfiguracionCotizador.obtener()
        creados = 0
        for material, color, densidad, precio in FILAMENTOS:
            _, nuevo = Filamento.objects.get_or_create(
                material=material, color=color, defaults={"densidad": Decimal(densidad), "precio_kg": Decimal(precio)}
            )
            creados += int(nuevo)
        self.stdout.write(self.style.SUCCESS(f"Cotizador listo: {creados} filamento(s) nuevo(s)."))
