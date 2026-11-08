from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.constraints import en_lista, no_negativos, restriccion
from apps.core.models.documentos import DocumentoImportes
from apps.core.validators import validar_codigo


class EstadoCotizacion(models.TextChoices):
    BORRADOR = "BORRADOR", "Borrador"
    ENVIADA = "ENVIADA", "Enviada"
    ACEPTADA = "ACEPTADA", "Aceptada"
    RECHAZADA = "RECHAZADA", "Rechazada"
    VENCIDA = "VENCIDA", "Vencida"
    CANCELADA = "CANCELADA", "Cancelada"


class Cotizacion(DocumentoImportes):
    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.PROTECT,
        db_column="id_cliente",
        related_name="cotizaciones",
    )
    usuario_responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column="id_usuario_responsable",
        related_name="cotizaciones_a_cargo",
    )
    codigo = models.CharField(max_length=30, unique=True, validators=[validar_codigo])
    fecha_emision = models.DateTimeField(default=timezone.now)
    fecha_vencimiento = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(max_length=20, choices=EstadoCotizacion.choices, default=EstadoCotizacion.BORRADOR)
    observaciones = models.TextField(null=True, blank=True)

    campos_texto_opcional = ("observaciones",)

    class Meta:
        db_table = "cotizaciones"
        verbose_name = "cotización"
        verbose_name_plural = "cotizaciones"
        constraints = [
            en_lista("ck_cotizaciones_estado", "estado", EstadoCotizacion.values),
            restriccion("ck_cotizaciones_importes", no_negativos("subtotal", "descuento", "impuesto", "total")),
        ]
        indexes = [models.Index(fields=["estado"], name="idx_cotizaciones_estado")]

    def __str__(self):
        return self.codigo

    def clean(self):
        super().clean()
        if self.codigo:
            self.codigo = self.codigo.strip().upper()
        if self.fecha_vencimiento and self.fecha_emision and self.fecha_vencimiento < self.fecha_emision:
            raise ValidationError({"fecha_vencimiento": "El vencimiento no puede ser anterior a la emisión."})
