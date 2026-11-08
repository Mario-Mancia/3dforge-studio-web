from django.core.files.storage import default_storage
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from apps.core.constraints import restriccion
from apps.core.fields import dinero
from apps.core.models.base import ModeloValidado
from apps.core.validators import validar_ruta_relativa, validar_sku


class Producto(ModeloValidado):
    sku = models.CharField(max_length=50, unique=True, validators=[validar_sku])
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField(null=True, blank=True)
    precio = dinero()
    stock = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    stock_minimo = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    imagen = models.TextField(null=True, blank=True, validators=[validar_ruta_relativa])
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    campos_texto_opcional = ("descripcion", "imagen")

    class Meta:
        db_table = "productos"
        verbose_name = "producto"
        verbose_name_plural = "productos"
        constraints = [
            restriccion("ck_productos_precio", Q(precio__gte=0)),
            restriccion("ck_productos_stock", Q(stock__gte=0)),
            restriccion("ck_productos_stock_minimo", Q(stock_minimo__gte=0)),
        ]
        indexes = [models.Index(fields=["activo", "nombre"], name="idx_productos_activo_nombre")]

    def __str__(self):
        return f"{self.sku} - {self.nombre}"

    def clean(self):
        super().clean()
        if self.sku:
            self.sku = self.sku.strip().upper()

    @property
    def imagen_url(self):
        return default_storage.url(self.imagen) if self.imagen else ""

    @property
    def bajo_stock(self):
        return self.stock <= self.stock_minimo

    @property
    def disponibilidad_codigo(self):
        if self.stock <= 0:
            return "agotado"
        if self.stock <= self.stock_minimo:
            return "ultimas"
        return "disponible"

    @property
    def disponibilidad(self):
        return {
            "agotado": "Agotado",
            "ultimas": "Últimas unidades",
            "disponible": "Disponible",
        }[self.disponibilidad_codigo]
