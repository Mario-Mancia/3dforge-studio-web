from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from apps.usuarios.models import Usuario


class UsuarioCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = ("correo", "nombres", "apellidos", "telefono", "estado")
        field_classes = {}


class UsuarioChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = Usuario
        fields = "__all__"
        field_classes = {}
