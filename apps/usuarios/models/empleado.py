from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models.base import ModeloValidado
from apps.core.validators import validar_codigo


class Empleado(ModeloValidado):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column="id_usuario",
        related_name="empleado",
    )
    codigo_empleado = models.CharField(max_length=30, unique=True, validators=[validar_codigo])
    cargo = models.CharField(max_length=100)
    fecha_contratacion = models.DateField(null=True, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "empleados"
        verbose_name = "empleado"
        verbose_name_plural = "empleados"

    def __str__(self):
        return f"{self.codigo_empleado} - {self.cargo}"

    def clean(self):
        super().clean()
        if self.codigo_empleado:
            self.codigo_empleado = self.codigo_empleado.strip().upper()
        if self.fecha_contratacion and self.fecha_contratacion > timezone.localdate():
            raise ValidationError({"fecha_contratacion": "La fecha de contratación no puede ser futura."})
