from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.constraints import en_lista, restriccion
from apps.core.models.base import ModeloValidado
from apps.facturacion.models import EstadoFactura


class EstadoPago(models.TextChoices):
    PENDIENTE = "PENDIENTE", "Pendiente"
    CONFIRMADO = "CONFIRMADO", "Confirmado"
    RECHAZADO = "RECHAZADO", "Rechazado"
    REEMBOLSADO = "REEMBOLSADO", "Reembolsado"
    CANCELADO = "CANCELADO", "Cancelado"


class Pago(ModeloValidado):
    factura = models.ForeignKey(
        "facturacion.Factura",
        on_delete=models.PROTECT,
        db_column="id_factura",
        related_name="pagos",
    )
    metodo_pago = models.ForeignKey(
        "pagos.MetodoPago",
        on_delete=models.PROTECT,
        db_column="id_metodo_pago",
        related_name="pagos",
    )
    referencia = models.CharField(max_length=120, null=True, blank=True)
    monto = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    fecha_pago = models.DateTimeField(default=timezone.now)
    estado = models.CharField(max_length=20, choices=EstadoPago.choices, default=EstadoPago.PENDIENTE)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="registrado_por",
        related_name="pagos_registrados",
    )
    observaciones = models.TextField(null=True, blank=True)

    campos_texto_opcional = ("referencia", "observaciones")

    class Meta:
        db_table = "pagos"
        verbose_name = "pago"
        verbose_name_plural = "pagos"
        constraints = [
            restriccion("ck_pagos_monto", Q(monto__gt=0)),
            en_lista("ck_pagos_estado", "estado", EstadoPago.values),
        ]
        indexes = [
            models.Index(fields=["estado"], name="idx_pagos_estado"),
            models.Index(fields=["fecha_pago"], name="idx_pagos_fecha"),
        ]

    def __str__(self):
        return f"Pago {self.pk} - {self.monto}"

    def clean(self):
        super().clean()
        if self._state.adding and self.factura_id:
            factura = self.factura
            if factura.estado == EstadoFactura.ANULADA:
                raise ValidationError({"factura": "No se pueden registrar pagos sobre una factura anulada."})
            if self.monto is not None and self.monto > factura.total:
                raise ValidationError({"monto": "El monto no puede superar el total de la factura."})
