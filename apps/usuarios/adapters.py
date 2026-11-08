from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.core.exceptions import ValidationError

from apps.core.validators import validar_nombre_persona
from apps.usuarios.constants import ESTADO_ACTIVO, ESTADO_PENDIENTE


def _nombre_o_defecto(valor, defecto):
    valor = (valor or "").strip()
    try:
        validar_nombre_persona(valor)
    except ValidationError:
        return defecto
    return valor


class CuentaAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return True

    def save_user(self, request, user, form, commit=True):
        datos = form.cleaned_data
        correo = datos.get("email")
        if correo:
            user.correo = correo.strip().lower()
        if datos.get("nombres"):
            user.nombres = datos["nombres"].strip()
        if datos.get("apellidos"):
            user.apellidos = datos["apellidos"].strip()
        if "telefono" in datos:
            user.telefono = datos["telefono"] or None
        user.is_staff = False
        user.is_superuser = False
        if getattr(form, "sociallogin", None) is None:
            user.estado_id = ESTADO_PENDIENTE
        password = datos.get("password1")
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        if commit:
            user.save()
        return user


class SocialAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request, sociallogin):
        return True

    def populate_user(self, request, sociallogin, data):
        usuario = sociallogin.user
        usuario.correo = (data.get("email") or "").strip().lower()
        usuario.nombres = _nombre_o_defecto(data.get("first_name"), "Cliente")
        usuario.apellidos = _nombre_o_defecto(data.get("last_name"), "Sin apellido")
        usuario.is_staff = False
        usuario.is_superuser = False
        usuario.estado_id = ESTADO_ACTIVO
        usuario.set_unusable_password()
        return usuario
