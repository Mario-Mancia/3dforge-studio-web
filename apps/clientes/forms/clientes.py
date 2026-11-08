from django import forms

from apps.clientes.models import Cliente


class PerfilClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = [
            "tipo_cliente",
            "nombres",
            "apellidos",
            "nombre_empresa",
            "telefono",
            "identificacion_fiscal",
            "direccion",
        ]
        labels = {
            "tipo_cliente": "Tipo de cliente",
            "nombre_empresa": "Nombre de la empresa",
            "identificacion_fiscal": "Identificación fiscal",
            "direccion": "Dirección",
            "telefono": "Teléfono",
        }
