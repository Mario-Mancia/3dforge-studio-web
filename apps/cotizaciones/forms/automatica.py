from pathlib import Path

from django import forms
from django.core.exceptions import ValidationError

from apps.core.archivos import validar_archivo
from apps.cotizaciones.models import ConfiguracionCotizador, Filamento
from apps.cotizaciones.modelos3d.estimacion import (
    CALIDADES,
    ESCALAS,
    ETIQUETAS_UNIDADES,
    RELLENOS,
    SOPORTES,
)

EXTENSIONES_3D = ("stl", "obj", "3mf")
CLAVES_OPCIONES = ("filamento", "relleno", "calidad", "escala", "unidades", "soportes", "cantidad")


def validar_modelo_3d(archivo):
    """Extension, tamano y contenido de un modelo 3D (STL, OBJ o 3MF)."""
    extension = Path(archivo.name or "").suffix.lower().lstrip(".")
    if extension not in EXTENSIONES_3D:
        raise ValidationError("Use un archivo STL, OBJ o 3MF.")
    validar_archivo(archivo)
    return archivo


class OpcionesEstimacionForm(forms.Form):
    filamento = forms.ModelChoiceField(queryset=Filamento.objects.none(), label="Filamento", empty_label=None)
    relleno = forms.TypedChoiceField(
        choices=[(valor, f"{valor} %" + (" (ligero)" if valor == 10 else " (sólido)" if valor == 100 else "")) for valor in RELLENOS],
        coerce=int,
        initial=20,
        label="Relleno",
    )
    calidad = forms.ChoiceField(
        choices=[(clave, datos["texto"]) for clave, datos in CALIDADES.items()], initial="estandar", label="Calidad"
    )
    escala = forms.TypedChoiceField(
        choices=[(valor, f"{valor} %") for valor in ESCALAS], coerce=int, initial=100, label="Escala"
    )
    unidades = forms.ChoiceField(choices=list(ETIQUETAS_UNIDADES.items()), initial="mm", label="Unidades del archivo")
    soportes = forms.ChoiceField(choices=list(SOPORTES.items()), initial="auto", label="Soportes")
    cantidad = forms.IntegerField(min_value=1, max_value=50, initial=1, label="Cantidad")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["filamento"].queryset = Filamento.objects.filter(activo=True).order_by("material", "color")

    def opciones(self):
        return {clave: self.cleaned_data[clave] for clave in CLAVES_OPCIONES}


class Cotizacion3DForm(OpcionesEstimacionForm):
    archivo = forms.FileField(
        label="Modelo 3D",
        help_text="STL, OBJ o 3MF. Máximo 50 MB.",
        widget=forms.FileInput(attrs={"accept": ".stl,.obj,.3mf"}),
    )
    descripcion = forms.CharField(max_length=200, required=False, label="Nombre de la pieza (opcional)")
    comentarios = forms.CharField(
        max_length=2000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Comentarios para el equipo (opcional)",
    )
    field_order = [
        "archivo", "unidades", "filamento", "relleno", "calidad", "escala", "soportes", "cantidad",
        "descripcion", "comentarios",
    ]

    def clean_archivo(self):
        archivo = self.cleaned_data["archivo"]
        return validar_modelo_3d(archivo)


class ConfiguracionCotizadorForm(forms.ModelForm):
    class Meta:
        model = ConfiguracionCotizador
        exclude = ["actualizado_en"]
        labels = {
            "grosor_pared_mm": "Grosor de paredes y tapas (mm)",
            "caudal_mm3_s": "Caudal efectivo (mm³/s)",
            "seg_por_capa": "Tiempo fijo por capa (s)",
            "desperdicio_pct": "Desperdicio de material (%)",
            "soporte_extra_pct": "Material extra por soportes (%)",
            "umbral_voladizo_pct": "Voladizo que activa soportes automáticos (%)",
            "factor_caja_pct": "Factor de respaldo (% de la caja envolvente)",
            "tarifa_hora": "Tarifa de máquina por hora ($)",
            "cargo_fijo": "Cargo fijo por pedido ($)",
            "minimo": "Precio mínimo por pedido ($)",
            "margen_pct": "Margen (%)",
            "cama_x_mm": "Cama de impresión X (mm)",
            "cama_y_mm": "Cama de impresión Y (mm)",
            "cama_z_mm": "Altura máxima Z (mm)",
            "max_triangulos": "Máximo de triángulos por modelo",
        }
        help_texts = {
            "caudal_mm3_s": "Velocidad media real de extrusión. Calíbrela comparando 3 o 4 piezas con su laminador.",
            "seg_por_capa": "Cambios de capa, desplazamientos y retracciones.",
            "factor_caja_pct": "Se usa solo si la malla tiene huecos: volumen ≈ ancho × largo × alto × este factor.",
        }


class FilamentoForm(forms.ModelForm):
    class Meta:
        model = Filamento
        fields = ["material", "color", "densidad", "precio_kg", "activo"]
        labels = {
            "material": "Material",
            "color": "Color",
            "densidad": "Densidad (g/cm³)",
            "precio_kg": "Precio por kilo ($)",
            "activo": "Disponible para cotizar",
        }
        help_texts = {"densidad": "PLA ≈ 1.24 · PETG ≈ 1.27 · ABS ≈ 1.04 · ASA ≈ 1.07 · TPU ≈ 1.21 · Nylon ≈ 1.14"}
