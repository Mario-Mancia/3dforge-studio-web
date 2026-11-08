from allauth.account.forms import SignupForm
from django import forms

from apps.core.validators import validar_nombre_persona, validar_telefono


class RegistroForm(SignupForm):
    nombres = forms.CharField(max_length=100, label="Nombres", validators=[validar_nombre_persona])
    apellidos = forms.CharField(max_length=100, label="Apellidos", validators=[validar_nombre_persona])
    telefono = forms.CharField(max_length=25, required=False, label="Teléfono", validators=[validar_telefono])

    field_order = ["nombres", "apellidos", "email", "telefono", "password1", "password2"]
