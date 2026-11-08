from django import forms
from django.core.exceptions import ValidationError

from apps.catalogo.models import CategoriaServicio, Producto, Servicio
from apps.catalogo.services.catalogo import eliminar_imagen, guardar_imagen
from apps.core.constants import FORMATOS_IMAGEN, MAX_IMAGEN_BYTES

from django.conf import settings

FORMATOS_PILLOW = {"JPEG", "PNG", "WEBP"}


class ProductoForm(forms.ModelForm):
    imagen_archivo = forms.ImageField(required=False, label="Imagen")
    quitar_imagen = forms.BooleanField(required=False, label="Quitar imagen actual")

    class Meta:
        model = Producto
        fields = ["sku", "nombre", "descripcion", "precio", "stock", "stock_minimo", "activo"]
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields.pop("stock")

    def clean_imagen_archivo(self):
        archivo = self.cleaned_data.get("imagen_archivo")
        if not archivo:
            return archivo
        extension = archivo.name.rsplit(".", 1)[-1].lower() if "." in archivo.name else ""
        if extension not in FORMATOS_IMAGEN:
            raise ValidationError("Formato no permitido. Use JPG, PNG o WEBP.")
        maximo = getattr(settings, "IMAGEN_MAX_BYTES", MAX_IMAGEN_BYTES)
        if archivo.size > maximo:
            raise ValidationError("La imagen supera el tamaño máximo permitido.")
        imagen = getattr(archivo, "image", None)
        if imagen is None or imagen.format not in FORMATOS_PILLOW:
            raise ValidationError("El archivo no es una imagen válida.")
        return archivo

    def save(self, commit=True):
        producto = super().save(commit=False)
        archivo = self.cleaned_data.get("imagen_archivo")
        anterior = producto.imagen
        if archivo:
            producto.imagen = guardar_imagen(archivo)
        elif self.cleaned_data.get("quitar_imagen"):
            producto.imagen = None
        if commit:
            producto.save()
            if anterior and anterior != producto.imagen:
                eliminar_imagen(anterior)
        return producto


class AjusteStockForm(forms.Form):
    delta = forms.IntegerField(min_value=-100000, max_value=100000, label="Ajuste")

    def clean_delta(self):
        delta = self.cleaned_data["delta"]
        if delta == 0:
            raise ValidationError("El ajuste no puede ser cero.")
        return delta


class ServicioForm(forms.ModelForm):
    class Meta:
        model = Servicio
        fields = ["categoria", "nombre", "descripcion", "precio_base", "requiere_archivo", "activo"]
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 4})}


class CategoriaForm(forms.ModelForm):
    class Meta:
        model = CategoriaServicio
        fields = ["nombre", "descripcion", "activo"]
