from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.constraints import en_lista
from apps.core.models.base import ModeloValidado


class TipoInteraccion(models.TextChoices):
    LLAMADA = "LLAMADA", "Llamada"
    CORREO = "CORREO", "Correo"
    ASESORIA = "ASESORIA", "Asesoría"
    REUNION = "REUNION", "Reunión"
    SEGUIMIENTO = "SEGUIMIENTO", "Seguimiento"
    RECLAMO = "RECLAMO", "Reclamo"


class InteraccionCliente(ModeloValidado):
    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.PROTECT,
        db_column="id_cliente",
        related_name="interacciones",
    )
    usuario_responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column="id_usuario_responsable",
        related_name="interacciones_registradas",
    )
    tipo_interaccion = models.CharField(max_length=40, choices=TipoInteraccion.choices)
    asunto = models.CharField(max_length=150)
    descripcion = models.TextField(null=True, blank=True)
    fecha_interaccion = models.DateTimeField(default=timezone.now)

    campos_texto_opcional = ("descripcion",)

    class Meta:
        db_table = "interacciones_clientes"
        verbose_name = "interacción con cliente"
        verbose_name_plural = "interacciones con clientes"
        constraints = [en_lista("ck_interacciones_tipo", "tipo_interaccion", TipoInteraccion.values)]
        indexes = [models.Index(fields=["cliente", "fecha_interaccion"], name="idx_interacc_cliente_fecha")]

    def __str__(self):
        return f"{self.tipo_interaccion}: {self.asunto}"
