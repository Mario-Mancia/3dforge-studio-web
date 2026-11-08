from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.core.constraints import no_negativos, restriccion
from apps.core.models.documentos import DetalleImportes
from apps.core.validators import validar_objeto_json


class EncargoDetalle(DetalleImportes):
    encargo = models.ForeignKey(
        "encargos.Encargo",
        on_delete=models.CASCADE,
        db_column="id_encargo",
        related_name="detalles",
    )
    servicio = models.ForeignKey(
        "catalogo.Servicio",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="id_servicio",
        related_name="detalles_encargo",
    )
    producto = models.ForeignKey(
        "catalogo.Producto",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="id_producto",
        related_name="detalles_encargo",
    )
    descripcion = models.TextField()
    especificaciones = models.JSONField(null=True, blank=True, validators=[validar_objeto_json])

    class Meta:
        db_table = "encargos_detalles"
        verbose_name = "detalle de encargo"
        verbose_name_plural = "detalles de encargos"
        constraints = [
            restriccion("ck_enc_det_cantidad", Q(cantidad__gt=0)),
            restriccion(
                "ck_enc_det_importes",
                no_negativos("precio_unitario", "descuento", "impuesto", "subtotal"),
            ),
            restriccion(
                "ck_enc_det_tipo_referencia",
                Q(servicio__isnull=True) | Q(producto__isnull=True),
            ),
        ]

    def __str__(self):
        return f"{self.encargo_id} - {self.descripcion[:40]}"

    def clean(self):
        super().clean()
        if self.servicio_id and self.producto_id:
            raise ValidationError("Un detalle no puede referirse a un servicio y a un producto a la vez.")
