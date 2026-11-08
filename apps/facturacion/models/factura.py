from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.core.constraints import en_lista, no_negativos, restriccion
from apps.core.fields import dinero
from apps.core.models.documentos import DocumentoImportes
from apps.core.validators import validar_codigo, validar_identificacion_fiscal


class EstadoFactura(models.TextChoices):
    PENDIENTE = "PENDIENTE", "Pendiente"
    PARCIALMENTE_PAGADA = "PARCIALMENTE_PAGADA", "Parcialmente pagada"
    PAGADA = "PAGADA", "Pagada"
    ANULADA = "ANULADA", "Anulada"
    VENCIDA = "VENCIDA", "Vencida"


class Factura(DocumentoImportes):
    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.PROTECT,
        db_column="id_cliente",
        related_name="facturas",
    )
    encargo = models.OneToOneField(
        "encargos.Encargo",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="id_encargo",
        related_name="factura",
    )
    numero_factura = models.CharField(max_length=40, unique=True, validators=[validar_codigo])
    fecha_emision = models.DateTimeField(default=timezone.now)
    fecha_vencimiento = models.DateTimeField(null=True, blank=True)
    nombre_facturacion = models.CharField(max_length=150)
    identificacion_fiscal = models.CharField(
        max_length=30, null=True, blank=True, validators=[validar_identificacion_fiscal]
    )
    direccion_facturacion = models.CharField(max_length=250, null=True, blank=True)
    saldo_pendiente = dinero(default=Decimal("0.00"))
    estado = models.CharField(max_length=25, choices=EstadoFactura.choices, default=EstadoFactura.PENDIENTE)
    observaciones = models.TextField(null=True, blank=True)

    campos_texto_opcional = ("identificacion_fiscal", "direccion_facturacion", "observaciones")

    class Meta:
        db_table = "facturas"
        verbose_name = "factura"
        verbose_name_plural = "facturas"
        constraints = [
            en_lista("ck_facturas_estado", "estado", EstadoFactura.values),
            restriccion(
                "ck_facturas_importes",
                no_negativos("subtotal", "descuento", "impuesto", "total", "saldo_pendiente")
                & Q(saldo_pendiente__lte=F("total")),
            ),
        ]
        indexes = [models.Index(fields=["estado"], name="idx_facturas_estado")]

    def __str__(self):
        return self.numero_factura

    def clean(self):
        super().clean()
        errores = {}
        if self.numero_factura:
            self.numero_factura = self.numero_factura.strip().upper()
        if self.fecha_vencimiento and self.fecha_emision and self.fecha_vencimiento < self.fecha_emision:
            errores["fecha_vencimiento"] = "El vencimiento no puede ser anterior a la emisión."
        if self.saldo_pendiente is not None and self.total is not None and self.saldo_pendiente > self.total:
            errores["saldo_pendiente"] = "El saldo pendiente no puede superar el total."
        if self.estado == EstadoFactura.PAGADA and self.saldo_pendiente:
            errores["estado"] = "Una factura pagada no puede tener saldo pendiente."
        if errores:
            raise ValidationError(errores)
