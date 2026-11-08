from decimal import Decimal

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.forms import formset_factory

from apps.catalogo.models import Servicio
from apps.catalogo.selectors.catalogo import servicios_publicos
from apps.core.archivos import validar_archivo


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={"multiple": True}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        limpiar = super().clean
        if isinstance(data, (list, tuple)):
            return [limpiar(archivo, initial) for archivo in data if archivo]
        return [limpiar(data, initial)] if data else []


class SolicitudCotizacionForm(forms.Form):
    servicio = forms.ModelChoiceField(queryset=Servicio.objects.none(), label="Servicio")
    cantidad = forms.DecimalField(
        min_value=Decimal("0.01"), max_digits=10, decimal_places=2, initial=1, label="Cantidad"
    )
    descripcion = forms.CharField(max_length=250, label="Título de su solicitud")
    solicitud = forms.CharField(
        min_length=10,
        max_length=5000,
        widget=forms.Textarea(attrs={"rows": 6}),
        label="Describa el trabajo que necesita",
    )
    material = forms.CharField(max_length=60, required=False, label="Material (opcional)")
    color = forms.CharField(max_length=60, required=False, label="Color (opcional)")
    dimensiones = forms.CharField(max_length=100, required=False, label="Dimensiones (opcional)")
    archivos = MultipleFileField(
        required=False,
        label="Archivos adjuntos",
        help_text="Formatos: STL, OBJ, 3MF, STEP, PNG, JPG o PDF.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["servicio"].queryset = servicios_publicos()

    def clean_archivos(self):
        archivos = self.cleaned_data.get("archivos") or []
        maximo = getattr(settings, "COTIZACION_MAX_ARCHIVOS", 5)
        if len(archivos) > maximo:
            raise ValidationError(f"Puede adjuntar hasta {maximo} archivos.")
        for archivo in archivos:
            validar_archivo(archivo)
        return archivos

    def clean(self):
        datos = super().clean()
        servicio = datos.get("servicio")
        if servicio and servicio.requiere_archivo and not datos.get("archivos") and "archivos" not in self.errors:
            self.add_error("archivos", "Este servicio requiere que adjunte al menos un archivo.")
        return datos

    def especificaciones(self):
        campos = {clave: (self.cleaned_data.get(clave) or "").strip() for clave in ("material", "color", "dimensiones")}
        return {clave: valor for clave, valor in campos.items() if valor}


class RevisionCotizacionForm(forms.Form):
    observaciones = forms.CharField(
        required=False,
        max_length=3000,
        widget=forms.Textarea(attrs={"rows": 4}),
        label="Observaciones para el cliente",
    )
    plazo_entrega_dias = forms.IntegerField(
        required=False, min_value=1, max_value=365, label="Plazo estimado de entrega (días)"
    )


class LineaCotizacionForm(forms.Form):
    id = forms.IntegerField(widget=forms.HiddenInput)
    descripcion = forms.CharField(required=False, disabled=True, label="Descripción")
    cantidad = forms.DecimalField(min_value=Decimal("0.01"), max_digits=10, decimal_places=2, label="Cantidad")
    precio_unitario = forms.DecimalField(
        min_value=Decimal("0"), max_digits=12, decimal_places=2, label="Precio unitario"
    )
    descuento = forms.DecimalField(
        min_value=Decimal("0"), max_digits=12, decimal_places=2, required=False, label="Descuento"
    )

    def clean(self):
        datos = super().clean()
        cantidad, precio = datos.get("cantidad"), datos.get("precio_unitario")
        datos["descuento"] = datos.get("descuento") or Decimal("0")
        if cantidad is not None and precio is not None and datos["descuento"] > cantidad * precio:
            raise ValidationError("El descuento no puede superar el importe de la línea.")
        return datos


LineasFormSet = formset_factory(LineaCotizacionForm, extra=0)
