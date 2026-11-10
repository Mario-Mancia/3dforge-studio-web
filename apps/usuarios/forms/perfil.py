from django import forms

from apps.usuarios.models import Usuario


class PerfilPersonalForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ["nombres", "apellidos", "telefono"]
        labels = {"nombres": "Nombres", "apellidos": "Apellidos", "telefono": "Teléfono"}
