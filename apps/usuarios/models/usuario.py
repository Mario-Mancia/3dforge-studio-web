from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.core.models.base import ModeloValidado
from apps.core.validators import validar_nombre_persona, validar_telefono
from apps.usuarios.constants import (
    ESTADO_ACTIVO,
    ESTADO_INACTIVO,
    ESTADOS_BLOQUEADOS,
    GRUPO_ADMINISTRADOR,
    GRUPO_OPERADOR,
)
from apps.usuarios.managers import UsuarioManager

ROLES_PERSONAL = (GRUPO_OPERADOR, GRUPO_ADMINISTRADOR)


class Usuario(ModeloValidado, AbstractBaseUser, PermissionsMixin):
    nombres = models.CharField(max_length=100, validators=[validar_nombre_persona])
    apellidos = models.CharField(max_length=100, validators=[validar_nombre_persona])
    correo = models.EmailField(max_length=150, unique=True)
    telefono = models.CharField(max_length=25, null=True, blank=True, validators=[validar_telefono])
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)
    estado = models.ForeignKey(
        "usuarios.EstadoUsuario",
        on_delete=models.PROTECT,
        db_column="id_estado",
        related_name="usuarios",
        default=ESTADO_ACTIVO,
    )

    objects = UsuarioManager()

    USERNAME_FIELD = "correo"
    EMAIL_FIELD = "correo"
    REQUIRED_FIELDS = ["nombres", "apellidos"]
    campos_texto_opcional = ("telefono",)

    class Meta:
        db_table = "usuarios"
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._estado_inicial = self.__dict__.get("estado_id")

    def __str__(self):
        return self.correo

    @property
    def nombre_completo(self):
        return f"{self.nombres} {self.apellidos}".strip()

    def get_full_name(self):
        return self.nombre_completo

    def get_short_name(self):
        return self.nombres

    def clean(self):
        super().clean()
        if self.correo:
            self.correo = self.correo.strip().lower()
        if self.estado_id in ESTADOS_BLOQUEADOS:
            self.is_active = False
        elif self.estado_id == ESTADO_ACTIVO:
            if self._estado_inicial in ESTADOS_BLOQUEADOS:
                self.is_active = True
            elif not self.is_active:
                self.estado_id = ESTADO_INACTIVO

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._estado_inicial = self.estado_id

    def tiene_empleado_inactivo(self):
        from apps.usuarios.models.empleado import Empleado

        return Empleado.objects.filter(usuario_id=self.pk, activo=False).exists()

    def tiene_algun_rol(self, roles):
        if not (self.is_active and self.estado_id == ESTADO_ACTIVO):
            return False
        if any(rol in ROLES_PERSONAL for rol in roles) and self.tiene_empleado_inactivo():
            roles = tuple(rol for rol in roles if rol not in ROLES_PERSONAL)
            if not roles:
                return False
        if self.is_superuser:
            return True
        return self.groups.filter(name__in=roles).exists()
