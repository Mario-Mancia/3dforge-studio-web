from django.conf import settings
from django.db import models

from apps.core.constraints import en_lista
from apps.core.models.base import ModeloValidado


class PrioridadSoporte(models.TextChoices):
    BAJA = "BAJA", "Baja"
    MEDIA = "MEDIA", "Media"
    ALTA = "ALTA", "Alta"
    URGENTE = "URGENTE", "Urgente"


class EstadoSoporte(models.TextChoices):
    ABIERTA = "ABIERTA", "Abierta"
    EN_PROCESO = "EN_PROCESO", "En proceso"
    RESUELTA = "RESUELTA", "Resuelta"
    CERRADA = "CERRADA", "Cerrada"


class SolicitudSoporte(ModeloValidado):
    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.PROTECT,
        db_column="id_cliente",
        related_name="solicitudes_soporte",
    )
    usuario_responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="id_usuario_responsable",
        related_name="solicitudes_soporte_a_cargo",
    )
    asunto = models.CharField(max_length=150)
    descripcion = models.TextField()
    prioridad = models.CharField(max_length=20, choices=PrioridadSoporte.choices, default=PrioridadSoporte.MEDIA)
    estado = models.CharField(max_length=20, choices=EstadoSoporte.choices, default=EstadoSoporte.ABIERTA)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "solicitudes_soporte"
        verbose_name = "solicitud de soporte"
        verbose_name_plural = "solicitudes de soporte"
        constraints = [
            en_lista("ck_soporte_prioridad", "prioridad", PrioridadSoporte.values),
            en_lista("ck_soporte_estado", "estado", EstadoSoporte.values),
        ]
        indexes = [models.Index(fields=["estado", "prioridad"], name="idx_soporte_estado_prioridad")]

    def __str__(self):
        return self.asunto
