from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from apps.core.constraints import restriccion
from apps.core.fields import dinero
from apps.core.models.base import ModeloValidado


class TipoMaterial(models.TextChoices):
    PLA = "PLA", "PLA"
    PETG = "PETG", "PETG"
    ABS = "ABS", "ABS"
    ASA = "ASA", "ASA"
    TPU = "TPU", "TPU (flexible)"
    NYLON = "NYLON", "Nylon"


class Filamento(ModeloValidado):
    material = models.CharField(max_length=20, choices=TipoMaterial.choices)
    color = models.CharField(max_length=40)
    densidad = models.DecimalField(
        max_digits=5,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.5")), MaxValueValidator(Decimal("3"))],
    )
    precio_kg = dinero()
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "filamentos"
        verbose_name = "filamento"
        verbose_name_plural = "filamentos"
        ordering = ["material", "color"]
        constraints = [
            models.UniqueConstraint(fields=["material", "color"], name="uq_filamentos_material_color"),
            restriccion("ck_filamentos_valores", Q(densidad__gt=0, precio_kg__gte=0)),
        ]

    def __str__(self):
        return f"{self.material} {self.color}"
