from django.db import models

from apps.core.models.base import ModeloValidado


class CategoriaServicio(ModeloValidado):
    nombre = models.CharField(max_length=80, unique=True)
    descripcion = models.CharField(max_length=200, null=True, blank=True)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    campos_texto_opcional = ("descripcion",)

    class Meta:
        db_table = "categorias_servicios"
        verbose_name = "categoría de servicio"
        verbose_name_plural = "categorías de servicios"

    def __str__(self):
        return self.nombre
