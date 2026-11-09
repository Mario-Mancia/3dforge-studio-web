from django import forms
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError

from apps.core.validators import validar_codigo, validar_nombre_persona, validar_telefono
from apps.usuarios.models import Empleado, EstadoUsuario, Usuario
from apps.usuarios.services.usuarios import ROLES_EMPLEADO

ESTILO_FECHA = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class EmpleadoCrearForm(forms.Form):
    correo = forms.EmailField(max_length=150, label="Correo")
    nombres = forms.CharField(max_length=100, validators=[validar_nombre_persona], label="Nombres")
    apellidos = forms.CharField(max_length=100, validators=[validar_nombre_persona], label="Apellidos")
    telefono = forms.CharField(max_length=25, required=False, validators=[validar_telefono], label="Teléfono")
    rol = forms.ChoiceField(choices=[(rol, rol) for rol in ROLES_EMPLEADO], label="Rol")
    codigo_empleado = forms.CharField(max_length=30, validators=[validar_codigo], label="Código de empleado")
    cargo = forms.CharField(max_length=100, label="Cargo")
    fecha_contratacion = forms.DateField(required=False, widget=ESTILO_FECHA, label="Fecha de contratación")
    password1 = forms.CharField(widget=forms.PasswordInput, label="Contraseña inicial")
    password2 = forms.CharField(widget=forms.PasswordInput, label="Confirmar contraseña")

    def clean_correo(self):
        correo = self.cleaned_data["correo"].strip().lower()
        if Usuario.objects.filter(correo__iexact=correo).exists():
            raise ValidationError("Ya existe un usuario con ese correo.")
        return correo

    def clean_codigo_empleado(self):
        codigo = self.cleaned_data["codigo_empleado"].strip().upper()
        if Empleado.objects.filter(codigo_empleado__iexact=codigo).exists():
            raise ValidationError("Ya existe un empleado con ese código.")
        return codigo

    def clean(self):
        datos = super().clean()
        if datos.get("password1") and datos["password1"] != datos.get("password2"):
            self.add_error("password2", "Las contraseñas no coinciden.")
        elif datos.get("password1"):
            try:
                password_validation.validate_password(datos["password1"])
            except ValidationError as error:
                self.add_error("password1", error)
        return datos

    def datos_servicio(self):
        datos = dict(self.cleaned_data)
        datos["password"] = datos.pop("password1")
        datos.pop("password2", None)
        return datos


class UsuarioEditarForm(forms.Form):
    nombres = forms.CharField(max_length=100, validators=[validar_nombre_persona], label="Nombres")
    apellidos = forms.CharField(max_length=100, validators=[validar_nombre_persona], label="Apellidos")
    telefono = forms.CharField(max_length=25, required=False, validators=[validar_telefono], label="Teléfono")
    estado = forms.ModelChoiceField(queryset=EstadoUsuario.objects.all(), label="Estado de la cuenta")
    rol = forms.ChoiceField(choices=[(rol, rol) for rol in ROLES_EMPLEADO], required=False, label="Rol")
    codigo_empleado = forms.CharField(max_length=30, required=False, validators=[validar_codigo], label="Código de empleado")
    cargo = forms.CharField(max_length=100, required=False, label="Cargo")
    fecha_contratacion = forms.DateField(required=False, widget=ESTILO_FECHA, label="Fecha de contratación")
    empleado_activo = forms.BooleanField(required=False, label="Empleado activo")

    def __init__(self, *args, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        self.empleado = Empleado.objects.filter(usuario=usuario).first()
        self.initial.update(
            {
                "nombres": usuario.nombres,
                "apellidos": usuario.apellidos,
                "telefono": usuario.telefono,
                "estado": usuario.estado_id,
            }
        )
        if self.empleado is None:
            for campo in ("rol", "codigo_empleado", "cargo", "fecha_contratacion", "empleado_activo"):
                del self.fields[campo]
            return
        rol = usuario.groups.filter(name__in=ROLES_EMPLEADO).values_list("name", flat=True).first()
        self.initial.update(
            {
                "rol": rol,
                "codigo_empleado": self.empleado.codigo_empleado,
                "cargo": self.empleado.cargo,
                "fecha_contratacion": self.empleado.fecha_contratacion,
                "empleado_activo": self.empleado.activo,
            }
        )
        self.fields["rol"].required = True
        self.fields["codigo_empleado"].required = True
        self.fields["cargo"].required = True

    def clean_codigo_empleado(self):
        codigo = (self.cleaned_data.get("codigo_empleado") or "").strip().upper()
        existe = Empleado.objects.filter(codigo_empleado__iexact=codigo).exclude(pk=self.empleado.pk).exists()
        if codigo and existe:
            raise ValidationError("Ya existe un empleado con ese código.")
        return codigo
