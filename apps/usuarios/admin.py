from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from apps.core.admin_utils import registrar
from apps.usuarios.forms.admin import UsuarioChangeForm, UsuarioCreationForm
from apps.usuarios.models import Empleado, EstadoUsuario, Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    form = UsuarioChangeForm
    add_form = UsuarioCreationForm
    model = Usuario
    ordering = ("correo",)
    list_display = ("correo", "nombres", "apellidos", "estado", "is_staff", "is_active")
    list_filter = ("estado", "is_staff", "is_active", "groups")
    search_fields = ("correo", "nombres", "apellidos")
    filter_horizontal = ("groups", "user_permissions")
    readonly_fields = ("last_login", "date_joined")
    fieldsets = (
        (None, {"fields": ("correo", "password")}),
        ("Datos personales", {"fields": ("nombres", "apellidos", "telefono", "estado")}),
        ("Permisos", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Fechas", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("correo", "nombres", "apellidos", "telefono", "estado", "password1", "password2"),
            },
        ),
    )


registrar(EstadoUsuario, Empleado)
