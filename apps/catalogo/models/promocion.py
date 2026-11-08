from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.constraints import en_lista, restriccion
from apps.core.models.base import ModeloValidado


class TipoDescuento(models.TextChoices):
    PORCENTAJE = "PORCENTAJE", "Porcentaje"
    MONTO_FIJO = "MONTO_FIJO", "Monto fijo"


class Promocion(ModeloValidado):
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField(null=True, blank=True)
    tipo_descuento = models.CharField(max_length=20, choices=TipoDescuento.choices)
    valor_descuento = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField()
    activo = models.BooleanField(default=True)

    campos_texto_opcional = ("descripcion",)

    class Meta:
        db_table = "promociones"
        verbose_name = "promoción"
        verbose_name_plural = "promociones"
        constraints = [
            en_lista("ck_promociones_tipo", "tipo_descuento", TipoDescuento.values),
            restriccion("ck_promociones_valor", Q(valor_descuento__gt=0)),
            restriccion("ck_promociones_fechas", Q(fecha_fin__gte=models.F("fecha_inicio"))),
            restriccion(
                "ck_promociones_porcentaje",
                ~Q(tipo_descuento="PORCENTAJE") | Q(valor_descuento__lte=100),
            ),
        ]
        indexes = [models.Index(fields=["activo", "fecha_inicio", "fecha_fin"], name="idx_promociones_vigencia")]

    def __str__(self):
        return self.nombre

    @property
    def vigente(self):
        return self.activo and self.fecha_inicio <= timezone.now() <= self.fecha_fin

    def clean(self):
        super().clean()
        errores = {}
        if self.fecha_inicio and self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            errores["fecha_fin"] = "La fecha final no puede ser anterior a la inicial."
        if (
            self.tipo_descuento == TipoDescuento.PORCENTAJE
            and self.valor_descuento is not None
            and self.valor_descuento > 100
        ):
            errores["valor_descuento"] = "El porcentaje no puede superar 100."
        if errores:
            raise ValidationError(errores)
