from django.db import models

from apps.core.models.base import ModeloValidado


class MetodoPago(ModeloValidado):
    id = models.SmallAutoField(primary_key=True)
    nombre = models.CharField(max_length=40, unique=True)
    descripcion = models.CharField(max_length=150, null=True, blank=True)
    activo = models.BooleanField(default=True)

    campos_texto_opcional = ("descripcion",)

    class Meta:
        db_table = "metodos_pago"
        verbose_name = "método de pago"
        verbose_name_plural = "métodos de pago"

    def __str__(self):
        return self.nombre
