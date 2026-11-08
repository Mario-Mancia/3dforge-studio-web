from django.contrib.auth.models import Group

from apps.usuarios.models import Usuario

CLAVE = "Clave-Segura-123"
BACKEND = "django.contrib.auth.backends.ModelBackend"


def crear_usuario(correo, grupo=None, **extra):
    usuario = Usuario.objects.create_user(
        correo=correo, password=CLAVE, nombres="Ana", apellidos="Prueba", **extra
    )
    if grupo:
        usuario.groups.add(Group.objects.get_or_create(name=grupo)[0])
    return usuario


def iniciar_sesion(cliente_http, usuario):
    cliente_http.force_login(usuario, backend=BACKEND)
