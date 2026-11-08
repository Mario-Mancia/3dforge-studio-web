from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.core.constraints import no_negativos, restriccion
from apps.core.models.documentos import DetalleImportes


class FacturaDetalle(DetalleImportes):
    factura = models.ForeignKey(
        "facturacion.Factura",
        on_delete=models.PROTECT,
        db_column="id_factura",
        related_name="detalles",
    )
    servicio = models.ForeignKey(
        "catalogo.Servicio",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="id_servicio",
        related_name="detalles_factura",
    )
    producto = models.ForeignKey(
        "catalogo.Producto",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="id_producto",
        related_name="detalles_factura",
    )
    descripcion = models.CharField(max_length=250)

    class Meta:
        db_table = "facturas_detalles"
        verbose_name = "detalle de factura"
        verbose_name_plural = "detalles de facturas"
        constraints = [
            restriccion("ck_fact_det_cantidad", Q(cantidad__gt=0)),
            restriccion(
                "ck_fact_det_importes",
                no_negativos("precio_unitario", "descuento", "impuesto", "subtotal"),
            ),
            restriccion(
                "ck_fact_det_tipo_referencia",
                Q(servicio__isnull=True) | Q(producto__isnull=True),
            ),
        ]

    def __str__(self):
        return f"{self.factura_id} - {self.descripcion}"

    def clean(self):
        super().clean()
        if self.servicio_id and self.producto_id:
            raise ValidationError("Un detalle no puede referirse a un servicio y a un producto a la vez.")
