from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.archivos import EXTENSIONES
from apps.core.constants import FORMATOS_ARCHIVO
from apps.core.constraints import en_lista, restriccion
from apps.core.models.base import ModeloValidado
from apps.core.validators import validar_nombre_archivo, validar_ruta_relativa, validar_tamano_archivo


class ArchivoCotizacion(ModeloValidado):
    cotizacion = models.ForeignKey(
        "cotizaciones.Cotizacion",
        on_delete=models.CASCADE,
        db_column="id_cotizacion",
        related_name="archivos",
    )
    nombre_archivo = models.CharField(max_length=150, validators=[validar_nombre_archivo])
    ruta_archivo = models.TextField(validators=[validar_ruta_relativa])
    formato = models.CharField(max_length=15, choices=[(formato, formato) for formato in FORMATOS_ARCHIVO])
    tamano_bytes = models.BigIntegerField(validators=[MinValueValidator(0), validar_tamano_archivo])
    usuario_subida = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column="id_usuario_subida",
        related_name="archivos_cotizacion_subidos",
    )
    fecha_subida = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "archivos_cotizaciones"
        verbose_name = "archivo de cotización"
        verbose_name_plural = "archivos de cotizaciones"
        constraints = [
            restriccion("ck_arch_cot_tamano", Q(tamano_bytes__gte=0)),
            en_lista("ck_arch_cot_formato", "formato", FORMATOS_ARCHIVO),
        ]

    def __str__(self):
        return self.nombre_archivo

    def clean(self):
        super().clean()
        if self.formato:
            self.formato = self.formato.strip().upper()
        if self.nombre_archivo and self.formato:
            extension = self.nombre_archivo.rsplit(".", 1)[-1].lower() if "." in self.nombre_archivo else ""
            if EXTENSIONES.get(extension) != self.formato:
                raise ValidationError({"nombre_archivo": "La extensión no coincide con el formato indicado."})
