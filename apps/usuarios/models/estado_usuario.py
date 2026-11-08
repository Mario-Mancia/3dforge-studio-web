from django.db import models

from apps.core.models.base import ModeloValidado


class EstadoUsuario(ModeloValidado):
    id = models.SmallAutoField(primary_key=True)
    nombre = models.CharField(max_length=40, unique=True)
    descripcion = models.CharField(max_length=150, null=True, blank=True)

    campos_texto_opcional = ("descripcion",)

    class Meta:
        db_table = "estados_usuarios"
        verbose_name = "estado de usuario"
        verbose_name_plural = "estados de usuarios"

    def __str__(self):
        return self.nombre
