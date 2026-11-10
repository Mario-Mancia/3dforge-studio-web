from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models.base import ModeloValidado
from apps.core.validators import validar_identificacion_fiscal, validar_ruta_relativa, validar_telefono

CLAVE_CACHE = "configuracion_negocio"


class ConfiguracionNegocio(ModeloValidado):
    nombre_negocio = models.CharField(max_length=150)
    identificacion_fiscal = models.CharField(
        max_length=30, null=True, blank=True, validators=[validar_identificacion_fiscal]
    )
    correo = models.EmailField(max_length=150, null=True, blank=True)
    telefono = models.CharField(max_length=25, null=True, blank=True, validators=[validar_telefono])
    direccion = models.CharField(max_length=250, null=True, blank=True)
    sitio_web = models.URLField(max_length=200, null=True, blank=True)
    logo = models.TextField(null=True, blank=True, validators=[validar_ruta_relativa])
    actualizado_en = models.DateTimeField(auto_now=True)

    campos_texto_opcional = ("identificacion_fiscal", "correo", "telefono", "direccion", "sitio_web", "logo")

    class Meta:
        db_table = "configuracion_negocio"
        verbose_name = "configuración del negocio"
        verbose_name_plural = "configuración del negocio"

    def __str__(self):
        return self.nombre_negocio

    @property
    def logo_url(self):
        if not self.logo:
            return None
        from django.core.files.storage import default_storage

        return default_storage.url(self.logo)
    def clean(self):
        super().clean()
        if self._state.adding and ConfiguracionNegocio.objects.exists():
            raise ValidationError("Solo puede existir un registro de configuración del negocio.")

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cache.delete(CLAVE_CACHE)

    def delete(self, *args, **kwargs):
        resultado = super().delete(*args, **kwargs)
        cache.delete(CLAVE_CACHE)
        return resultado
