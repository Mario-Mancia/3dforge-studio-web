from django.db import models

from apps.core.validators import cantidad_minima, importe_no_negativo


def dinero(**kwargs):
    return models.DecimalField(max_digits=12, decimal_places=2, validators=[importe_no_negativo], **kwargs)


def cantidad_decimal(**kwargs):
    return models.DecimalField(max_digits=10, decimal_places=2, validators=[cantidad_minima], **kwargs)
