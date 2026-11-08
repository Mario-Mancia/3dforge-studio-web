from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models.base import ModeloValidado
from apps.encargos.models.encargo import EstadoEncargo


class HistorialEncargo(ModeloValidado):
    encargo = models.ForeignKey(
        "encargos.Encargo",
        on_delete=models.CASCADE,
        db_column="id_encargo",
        related_name="historial",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column="id_usuario",
        related_name="historial_encargos",
    )
    estado_anterior = models.CharField(max_length=25, choices=EstadoEncargo.choices, null=True, blank=True)
    estado_nuevo = models.CharField(max_length=25, choices=EstadoEncargo.choices)
    comentario = models.TextField(null=True, blank=True)
    fecha_cambio = models.DateTimeField(default=timezone.now)

    campos_texto_opcional = ("estado_anterior", "comentario")

    class Meta:
        db_table = "historial_encargos"
        verbose_name = "historial de encargo"
        verbose_name_plural = "historial de encargos"
        indexes = [models.Index(fields=["encargo", "fecha_cambio"], name="idx_historial_encargo_fecha")]

    def __str__(self):
        return f"{self.encargo_id}: {self.estado_anterior} -> {self.estado_nuevo}"

    def clean(self):
        super().clean()
        if self.estado_anterior and self.estado_anterior == self.estado_nuevo:
            raise ValidationError({"estado_nuevo": "El estado nuevo debe ser distinto del anterior."})

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("El historial de encargos no se puede modificar.")
        super().save(*args, **kwargs)
