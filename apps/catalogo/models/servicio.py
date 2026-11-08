from django.db import models
from django.db.models import Q

from apps.core.constraints import restriccion
from apps.core.fields import dinero
from apps.core.models.base import ModeloValidado


class Servicio(ModeloValidado):
    categoria = models.ForeignKey(
        "catalogo.CategoriaServicio",
        on_delete=models.PROTECT,
        db_column="id_categoria",
        related_name="servicios",
    )
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField()
    precio_base = dinero()
    requiere_archivo = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "servicios"
        verbose_name = "servicio"
        verbose_name_plural = "servicios"
        constraints = [restriccion("ck_servicios_precio", Q(precio_base__gte=0))]
        indexes = [models.Index(fields=["activo"], name="idx_servicios_activo")]

    def __str__(self):
        return self.nombre
