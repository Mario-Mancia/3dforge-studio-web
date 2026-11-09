from allauth.account.models import EmailAddress
from django.contrib.auth import password_validation
from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import Q

from apps.usuarios.constants import ESTADO_ACTIVO, GRUPO_ADMINISTRADOR, GRUPO_OPERADOR
from apps.usuarios.models import Empleado, Usuario

ROLES_EMPLEADO = (GRUPO_OPERADOR, GRUPO_ADMINISTRADOR)


class ErrorUsuarios(Exception):
    pass


def _otros_administradores(usuario):
    return (
        Usuario.objects.filter(is_active=True, estado_id=ESTADO_ACTIVO)
        .filter(Q(is_superuser=True) | Q(groups__name=GRUPO_ADMINISTRADOR))
        .exclude(pk=usuario.pk)
        .distinct()
    )


def _es_administrador_activo(usuario):
    if not (usuario.is_active and usuario.estado_id == ESTADO_ACTIVO):
        return False
    return usuario.is_superuser or usuario.groups.filter(name=GRUPO_ADMINISTRADOR).exists()


@transaction.atomic
def crear_empleado(*, correo, nombres, apellidos, telefono, rol, password, codigo_empleado, cargo, fecha_contratacion=None):
    if rol not in ROLES_EMPLEADO:
        raise ErrorUsuarios("El rol indicado no es válido.")
    password_validation.validate_password(password)
    usuario = Usuario.objects.create_user(
        correo=correo,
        password=password,
        nombres=nombres,
        apellidos=apellidos,
        telefono=telefono or None,
        is_staff=True,
    )
    usuario.groups.add(Group.objects.get(name=rol))
    Empleado.objects.create(
        usuario=usuario, codigo_empleado=codigo_empleado, cargo=cargo, fecha_contratacion=fecha_contratacion
    )
    EmailAddress.objects.create(user=usuario, email=usuario.correo, verified=True, primary=True)
    return usuario


@transaction.atomic
def actualizar_usuario(usuario_id, actor, datos):
    usuario = Usuario.objects.select_for_update().get(pk=usuario_id)
    empleado = Empleado.objects.filter(usuario=usuario).first()
    nuevo_estado = datos["estado"].pk
    nuevo_rol = datos.get("rol") if empleado else None

    if usuario.pk == actor.pk and nuevo_estado != ESTADO_ACTIVO:
        raise ErrorUsuarios("No puede desactivar su propia cuenta.")
    if usuario.pk == actor.pk and empleado and nuevo_rol != GRUPO_ADMINISTRADOR and not usuario.is_superuser:
        raise ErrorUsuarios("No puede quitarse a sí mismo el rol de administrador.")
    if empleado:
        sera_admin = usuario.is_superuser or nuevo_rol == GRUPO_ADMINISTRADOR
    else:
        sera_admin = usuario.is_superuser or usuario.groups.filter(name=GRUPO_ADMINISTRADOR).exists()
    sera_admin = sera_admin and nuevo_estado == ESTADO_ACTIVO
    if _es_administrador_activo(usuario) and not sera_admin and not _otros_administradores(usuario).exists():
        raise ErrorUsuarios("Debe quedar al menos un administrador activo.")

    if usuario.pk == actor.pk and empleado and not datos.get("empleado_activo"):
        raise ErrorUsuarios("No puede desactivar su propio perfil de empleado.")
    usuario.nombres = datos["nombres"]
    usuario.apellidos = datos["apellidos"]
    usuario.telefono = datos.get("telefono") or None
    usuario.estado_id = nuevo_estado
    usuario.save()

    if empleado:
        if nuevo_rol not in ROLES_EMPLEADO:
            raise ErrorUsuarios("El rol indicado no es válido.")
        usuario.groups.remove(*Group.objects.filter(name__in=ROLES_EMPLEADO))
        usuario.groups.add(Group.objects.get(name=nuevo_rol))
        empleado.codigo_empleado = datos["codigo_empleado"]
        empleado.cargo = datos["cargo"]
        empleado.fecha_contratacion = datos.get("fecha_contratacion")
        empleado.activo = bool(datos.get("empleado_activo"))
        empleado.save()
    return usuario
