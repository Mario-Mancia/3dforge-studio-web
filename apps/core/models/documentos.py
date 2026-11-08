from decimal import Decimal

from django.core.exceptions import ValidationError

from apps.core.calculos import importes_coherentes, linea_coherente
from apps.core.fields import cantidad_decimal, dinero
from apps.core.models.base import ModeloValidado


class DocumentoImportes(ModeloValidado):
    subtotal = dinero(default=Decimal("0.00"))
    descuento = dinero(default=Decimal("0.00"))
    impuesto = dinero(default=Decimal("0.00"))
    total = dinero(default=Decimal("0.00"))

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        if not importes_coherentes(self.subtotal, self.descuento, self.impuesto, self.total):
            raise ValidationError({"total": "El total debe ser igual a subtotal - descuento + impuesto."})


class DetalleImportes(ModeloValidado):
    cantidad = cantidad_decimal()
    precio_unitario = dinero()
    descuento = dinero(default=Decimal("0.00"))
    impuesto = dinero(default=Decimal("0.00"))
    subtotal = dinero()

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        if not linea_coherente(self.cantidad, self.precio_unitario, self.descuento, self.subtotal):
            raise ValidationError({"subtotal": "El subtotal debe ser cantidad x precio unitario - descuento."})
