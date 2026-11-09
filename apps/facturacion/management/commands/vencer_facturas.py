from django.core.management.base import BaseCommand

from apps.facturacion.services.facturacion import marcar_vencidas


class Command(BaseCommand):
    help = "Marca como VENCIDA toda factura con saldo cuyo vencimiento ya pasó."

    def handle(self, *args, **opciones):
        self.stdout.write(self.style.SUCCESS(f"Facturas vencidas: {marcar_vencidas()}"))
