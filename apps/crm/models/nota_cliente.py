from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models.base import ModeloValidado


class NotaCliente(ModeloValidado):
    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.CASCADE,
        db_column="id_cliente",
        related_name="notas",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column="id_usuario",
        related_name="notas_clientes",
    )
    contenido = models.TextField()
    fecha_creacion = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "notas_clientes"
        verbose_name = "nota de cliente"
        verbose_name_plural = "notas de clientes"
        indexes = [models.Index(fields=["cliente", "fecha_creacion"], name="idx_notas_cliente_fecha")]

    def __str__(self):
        return f"Nota {self.pk} - cliente {self.cliente_id}"
