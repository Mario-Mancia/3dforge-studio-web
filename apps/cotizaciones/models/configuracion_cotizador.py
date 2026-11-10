from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.fields import dinero
from apps.core.models.base import ModeloValidado


def _porcentaje(defecto, minimo=0, maximo=100):
    return models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal(str(defecto)),
        validators=[MinValueValidator(Decimal(str(minimo))), MaxValueValidator(Decimal(str(maximo)))],
    )


def _decimal(defecto, minimo, maximo, digitos=6):
    return models.DecimalField(
        max_digits=digitos,
        decimal_places=2,
        default=Decimal(str(defecto)),
        validators=[MinValueValidator(Decimal(str(minimo))), MaxValueValidator(Decimal(str(maximo)))],
    )


def _entero(defecto, minimo, maximo):
    return models.PositiveIntegerField(
        default=defecto, validators=[MinValueValidator(minimo), MaxValueValidator(maximo)]
    )


class ConfiguracionCotizador(ModeloValidado):
    """Parametros de la formula del cotizador automatico de impresion 3D (un solo registro)."""

    grosor_pared_mm = _decimal("1.20", "0.2", "10")
    caudal_mm3_s = _decimal("5.00", "0.5", "40")
    seg_por_capa = _decimal("5.00", "0", "120")
    desperdicio_pct = _porcentaje(8)
    soporte_extra_pct = _porcentaje(15)
    umbral_voladizo_pct = _porcentaje(8)
    factor_caja_pct = _porcentaje(25, 1, 100)
    tarifa_hora = dinero(default=Decimal("2.50"))
    cargo_fijo = dinero(default=Decimal("2.00"))
    minimo = dinero(default=Decimal("3.00"))
    margen_pct = _porcentaje(20, 0, 500)
    cama_x_mm = _entero(220, 20, 2000)
    cama_y_mm = _entero(220, 20, 2000)
    cama_z_mm = _entero(250, 20, 2000)
    max_triangulos = _entero(1500000, 1000, 5000000)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "configuracion_cotizador"
        verbose_name = "configuración del cotizador"
        verbose_name_plural = "configuración del cotizador"

    def __str__(self):
        return "Parámetros del cotizador 3D"

    def clean(self):
        super().clean()
        if self._state.adding and ConfiguracionCotizador.objects.exists():
            raise ValidationError("Solo puede existir un registro de parámetros del cotizador.")

    @classmethod
    def obtener(cls):
        return cls.objects.first() or cls.objects.create()
