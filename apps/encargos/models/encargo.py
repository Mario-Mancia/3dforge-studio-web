from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.constraints import en_lista, no_negativos, restriccion
from apps.core.models.documentos import DocumentoImportes
from apps.core.validators import validar_codigo


class EstadoEncargo(models.TextChoices):
    PENDIENTE = "PENDIENTE", "Pendiente"
    EN_REVISION = "EN_REVISION", "En revisión"
    APROBADO = "APROBADO", "Aprobado"
    EN_PRODUCCION = "EN_PRODUCCION", "En producción"
    EN_ESPERA = "EN_ESPERA", "En espera"
    FINALIZADO = "FINALIZADO", "Finalizado"
    ENTREGADO = "ENTREGADO", "Entregado"
    CANCELADO = "CANCELADO", "Cancelado"


class Encargo(DocumentoImportes):
    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.PROTECT,
        db_column="id_cliente",
        related_name="encargos",
    )
    cotizacion = models.OneToOneField(
        "cotizaciones.Cotizacion",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="id_cotizacion",
        related_name="encargo",
    )
    empleado_responsable = models.ForeignKey(
        "usuarios.Empleado",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="id_empleado_responsable",
        related_name="encargos",
    )
    codigo = models.CharField(max_length=30, unique=True, validators=[validar_codigo])
    fecha_solicitud = models.DateTimeField(default=timezone.now)
    fecha_entrega_estimada = models.DateTimeField(null=True, blank=True)
    fecha_entrega_real = models.DateTimeField(null=True, blank=True)
    descripcion = models.TextField()
    estado = models.CharField(max_length=25, choices=EstadoEncargo.choices, default=EstadoEncargo.PENDIENTE)
    observaciones = models.TextField(null=True, blank=True)

    campos_texto_opcional = ("observaciones",)

    class Meta:
        db_table = "encargos"
        verbose_name = "encargo"
        verbose_name_plural = "encargos"
        constraints = [
            en_lista("ck_encargos_estado", "estado", EstadoEncargo.values),
            restriccion("ck_encargos_importes", no_negativos("subtotal", "descuento", "impuesto", "total")),
        ]
        indexes = [models.Index(fields=["estado"], name="idx_encargos_estado")]

    def __str__(self):
        return self.codigo

    def clean(self):
        super().clean()
        errores = {}
        if self.codigo:
            self.codigo = self.codigo.strip().upper()
        for campo in ("fecha_entrega_estimada", "fecha_entrega_real"):
            valor = getattr(self, campo)
            if valor and self.fecha_solicitud and valor < self.fecha_solicitud:
                errores[campo] = "No puede ser anterior a la fecha de solicitud."
        if self.cotizacion_id and self.cotizacion.cliente_id != self.cliente_id:
            errores["cotizacion"] = "La cotización pertenece a otro cliente."
        if errores:
            raise ValidationError(errores)
