from allauth.account.signals import email_confirmed, user_signed_up
from django.contrib.auth.models import Group
from django.dispatch import receiver

from apps.clientes.services.clientes import asegurar_cliente
from apps.usuarios.constants import ESTADO_ACTIVO, ESTADO_PENDIENTE, GRUPO_CLIENTE


@receiver(user_signed_up, dispatch_uid="usuarios.registrar_cliente")
def registrar_cliente(sender, request, user, **kwargs):
    if user.is_staff or user.is_superuser:
        return
    grupo, _ = Group.objects.get_or_create(name=GRUPO_CLIENTE)
    user.groups.add(grupo)
    asegurar_cliente(user)


@receiver(email_confirmed, dispatch_uid="usuarios.activar_usuario")
def activar_usuario(sender, request, email_address, **kwargs):
    usuario = email_address.user
    if usuario.estado_id == ESTADO_PENDIENTE:
        usuario.estado_id = ESTADO_ACTIVO
        usuario.save(update_fields=["estado"])

# >>> sesion-unica
from django.conf import settings
from django.contrib.auth.signals import user_logged_in

from apps.usuarios.sesiones import cerrar_otras_sesiones


@receiver(user_logged_in, dispatch_uid="usuarios.sesion_unica")
def aplicar_sesion_unica(sender, request, user, **kwargs):
    if getattr(settings, "SESION_UNICA", True) and request is not None:
        cerrar_otras_sesiones(user, request.session.session_key)
# <<< sesion-unica
