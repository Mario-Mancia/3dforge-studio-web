from django.core.management.base import BaseCommand

from apps.cotizaciones.services.cotizaciones import vencer_cotizaciones_vencidas


class Command(BaseCommand):
    help = "Marca como VENCIDA toda cotización enviada cuya vigencia ya terminó."

    def handle(self, *args, **opciones):
        total = vencer_cotizaciones_vencidas()
        self.stdout.write(self.style.SUCCESS(f"Cotizaciones vencidas: {total}"))
