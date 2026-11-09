from django import forms

from apps.crm.models import EstadoSoporte, TipoInteraccion


class NotaForm(forms.Form):
    contenido = forms.CharField(max_length=3000, widget=forms.Textarea(attrs={"rows": 3}), label="Nota")


class InteraccionForm(forms.Form):
    tipo = forms.ChoiceField(choices=TipoInteraccion.choices, label="Tipo")
    asunto = forms.CharField(max_length=150, label="Asunto")
    descripcion = forms.CharField(required=False, max_length=3000, widget=forms.Textarea(attrs={"rows": 3}), label="Detalle")


class SolicitudSoporteForm(forms.Form):
    asunto = forms.CharField(max_length=150, label="Asunto")
    descripcion = forms.CharField(min_length=10, max_length=3000, widget=forms.Textarea(attrs={"rows": 4}), label="Describa su solicitud")
    prioridad = forms.ChoiceField(choices=[("BAJA", "Baja"), ("MEDIA", "Media"), ("ALTA", "Alta")], initial="MEDIA", label="Prioridad")


class CambioEstadoSoporteForm(forms.Form):
    estado = forms.ChoiceField(choices=EstadoSoporte.choices, label="Nuevo estado")

    def __init__(self, *args, permitidos=None, **kwargs):
        super().__init__(*args, **kwargs)
        if permitidos is not None:
            self.fields["estado"].choices = [(v, e) for v, e in EstadoSoporte.choices if v in permitidos]
