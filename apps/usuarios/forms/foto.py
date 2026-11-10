from django import forms

from apps.core.imagenes import validar_imagen_subida


class FotoPerfilForm(forms.Form):
    foto = forms.ImageField(required=False, label="Foto de perfil")
    quitar = forms.BooleanField(required=False)

    def clean_foto(self):
        archivo = self.cleaned_data.get("foto")
        if archivo:
            validar_imagen_subida(archivo)
        return archivo
