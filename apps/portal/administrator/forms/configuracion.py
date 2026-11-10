from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

from apps.core.imagenes import (
    eliminar_imagen,
    guardar_imagen_publica,
    normalizar_imagen,
    validar_imagen_subida,
)
from apps.core.models import ConfiguracionNegocio

LADO_MAXIMO_LOGO = 600


class ConfiguracionNegocioForm(forms.ModelForm):
    logo_archivo = forms.ImageField(
        required=False,
        label="Logo",
        widget=forms.FileInput(
            attrs={
                "accept": "image/jpeg,image/png,image/webp",
                "data-foto-entrada": "",
                "data-max-bytes": str(getattr(settings, "IMAGEN_MAX_BYTES", 2097152)),
            }
        ),
        help_text="JPG, PNG o WEBP. Se ajusta automáticamente.",
    )
    quitar_logo = forms.BooleanField(required=False, label="Quitar el logo actual")

    class Meta:
        model = ConfiguracionNegocio
        fields = ["nombre_negocio", "identificacion_fiscal", "correo", "telefono", "direccion", "sitio_web"]
        labels = {
            "nombre_negocio": "Nombre del negocio",
            "identificacion_fiscal": "Identificación fiscal",
            "correo": "Correo de contacto",
            "telefono": "Teléfono",
            "direccion": "Dirección",
            "sitio_web": "Sitio web",
        }

    def clean_logo_archivo(self):
        archivo = self.cleaned_data.get("logo_archivo")
        self._logo_nuevo = None
        if not archivo:
            return archivo
        validar_imagen_subida(archivo)
        self._logo_nuevo = normalizar_imagen(archivo, maximo=LADO_MAXIMO_LOGO)
        return archivo

    def save(self, commit=True):
        configuracion = super().save(commit=False)
        anterior = configuracion.logo
        nueva = None
        if getattr(self, "_logo_nuevo", None):
            contenido, extension = self._logo_nuevo
            nueva = guardar_imagen_publica("negocio", contenido, extension)
            configuracion.logo = nueva
        elif self.cleaned_data.get("quitar_logo"):
            configuracion.logo = None
        if commit:
            try:
                configuracion.save()
            except Exception:
                if nueva:
                    eliminar_imagen(nueva)
                raise
            if anterior and anterior != configuracion.logo:
                eliminar_imagen(anterior)
        return configuracion
