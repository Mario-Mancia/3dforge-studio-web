from django import forms

from apps.core.archivos import validar_archivo
from apps.encargos.models import EncargoDetalle, EstadoEncargo
from apps.encargos.selectors.encargos import empleados_activos
from apps.usuarios.models import Empleado


class CambioEstadoForm(forms.Form):
    estado = forms.ChoiceField(choices=EstadoEncargo.choices, label="Nuevo estado")
    comentario = forms.CharField(required=False, max_length=1000, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, permitidos=None, **kwargs):
        super().__init__(*args, **kwargs)
        if permitidos is not None:
            self.fields["estado"].choices = [(v, e) for v, e in EstadoEncargo.choices if v in permitidos]


class AsignacionForm(forms.Form):
    empleado = forms.ModelChoiceField(queryset=Empleado.objects.none(), label="Responsable")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        campo = self.fields["empleado"]
        campo.queryset = empleados_activos()
        campo.label_from_instance = lambda e: f"{e.codigo_empleado} - {e.usuario.nombre_completo}"


class SubirArchivoForm(forms.Form):
    detalle = forms.ModelChoiceField(queryset=EncargoDetalle.objects.none(), label="Línea del encargo")
    archivo = forms.FileField(label="Archivo")

    def __init__(self, *args, encargo=None, **kwargs):
        super().__init__(*args, **kwargs)
        if encargo is not None:
            self.fields["detalle"].queryset = encargo.detalles.all()
            self.fields["detalle"].label_from_instance = lambda d: d.descripcion[:60]

    def clean_archivo(self):
        archivo = self.cleaned_data["archivo"]
        validar_archivo(archivo)
        return archivo
