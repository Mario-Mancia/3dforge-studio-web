from allauth.account.models import EmailAddress
from django.core.management.base import BaseCommand, CommandError

from apps.usuarios.models import Usuario


class Command(BaseCommand):
    help = "Marca como verificado el correo de un usuario (para cuentas creadas fuera del registro)."

    def add_arguments(self, parser):
        parser.add_argument("correo")

    def handle(self, *args, **opciones):
        usuario = Usuario.objects.filter(correo__iexact=opciones["correo"]).first()
        if usuario is None:
            raise CommandError("No existe un usuario con ese correo.")
        EmailAddress.objects.filter(user=usuario, primary=True).exclude(email__iexact=usuario.correo).update(primary=False)
        direccion, _ = EmailAddress.objects.get_or_create(
            user=usuario, email=usuario.correo, defaults={"primary": True, "verified": True}
        )
        if not direccion.verified or not direccion.primary:
            direccion.verified = True
            direccion.primary = True
            direccion.save()
        self.stdout.write(self.style.SUCCESS(f"Correo verificado: {usuario.correo}"))
