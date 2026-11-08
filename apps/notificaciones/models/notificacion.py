from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models.base import ModeloValidado


class Notificacion(ModeloValidado):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column="id_usuario",
        related_name="notificaciones",
    )
    titulo = models.CharField(max_length=120)
    mensaje = models.TextField()
    tipo = models.CharField(max_length=40)
    referencia_id = models.BigIntegerField(null=True, blank=True)
    leida = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "notificaciones"
        verbose_name = "notificación"
        verbose_name_plural = "notificaciones"
        indexes = [
            models.Index(fields=["usuario", "leida", "-fecha_creacion"], name="idx_notif_usuario_leida_fecha")
        ]

    def __str__(self):
        return self.titulo
