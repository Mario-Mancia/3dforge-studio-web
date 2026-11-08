from django.db import models
from django.db.models import Q

from apps.core.constraints import no_negativos, restriccion
from apps.core.models.documentos import DetalleImportes
from apps.core.validators import validar_objeto_json


class CotizacionDetalle(DetalleImportes):
    cotizacion = models.ForeignKey(
        "cotizaciones.Cotizacion",
        on_delete=models.CASCADE,
        db_column="id_cotizacion",
        related_name="detalles",
    )
    servicio = models.ForeignKey(
        "catalogo.Servicio",
        on_delete=models.PROTECT,
        db_column="id_servicio",
        related_name="detalles_cotizacion",
    )
    descripcion = models.CharField(max_length=250)
    especificaciones = models.JSONField(null=True, blank=True, validators=[validar_objeto_json])

    class Meta:
        db_table = "cotizaciones_detalles"
        verbose_name = "detalle de cotización"
        verbose_name_plural = "detalles de cotizaciones"
        constraints = [
            restriccion("ck_cot_det_cantidad", Q(cantidad__gt=0)),
            restriccion(
                "ck_cot_det_importes",
                no_negativos("precio_unitario", "descuento", "impuesto", "subtotal"),
            ),
        ]

    def __str__(self):
        return f"{self.cotizacion_id} - {self.descripcion}"
