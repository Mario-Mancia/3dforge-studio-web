from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.constraints import restriccion
from apps.core.models.base import ModeloValidado


class Resena(ModeloValidado):
    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.PROTECT,
        db_column="id_cliente",
        related_name="resenas",
    )
    servicio = models.ForeignKey(
        "catalogo.Servicio",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="id_servicio",
        related_name="resenas",
    )
    encargo = models.ForeignKey(
        "encargos.Encargo",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="id_encargo",
        related_name="resenas",
    )
    puntuacion = models.SmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comentario = models.TextField(null=True, blank=True)
    fecha_creacion = models.DateTimeField(default=timezone.now)

    campos_texto_opcional = ("comentario",)

    class Meta:
        db_table = "resenas"
        verbose_name = "reseña"
        verbose_name_plural = "reseñas"
        constraints = [
            restriccion("ck_resenas_puntuacion", Q(puntuacion__gte=1, puntuacion__lte=5)),
            restriccion(
                "ck_resenas_referencia",
                Q(servicio__isnull=False) | Q(encargo__isnull=False),
            ),
        ]

    def __str__(self):
        return f"Reseña {self.pk} ({self.puntuacion}/5)"

    def clean(self):
        super().clean()
        if not self.servicio_id and not self.encargo_id:
            raise ValidationError("La reseña debe referirse a un servicio o a un encargo.")
        if self.encargo_id and self.encargo.cliente_id != self.cliente_id:
            raise ValidationError({"encargo": "El encargo pertenece a otro cliente."})
