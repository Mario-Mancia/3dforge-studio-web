from django.db import models

from apps.core.models.base import ModeloValidado
from apps.core.validators import validar_objeto_json


class TransaccionPasarela(ModeloValidado):
    pago = models.OneToOneField(
        "pagos.Pago",
        on_delete=models.PROTECT,
        db_column="id_pago",
        related_name="transaccion",
    )
    proveedor = models.CharField(max_length=50)
    referencia_externa = models.CharField(max_length=150, unique=True, null=True, blank=True)
    estado_respuesta = models.CharField(max_length=40, null=True, blank=True)
    respuesta = models.JSONField(null=True, blank=True, validators=[validar_objeto_json])
    fecha_respuesta = models.DateTimeField(null=True, blank=True)

    campos_texto_opcional = ("referencia_externa", "estado_respuesta")

    class Meta:
        db_table = "transacciones_pasarela"
        verbose_name = "transacción de pasarela"
        verbose_name_plural = "transacciones de pasarela"

    def __str__(self):
        return f"{self.proveedor} - {self.referencia_externa or self.pk}"
