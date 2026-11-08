from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.constraints import en_lista
from apps.core.models.base import ModeloValidado
from apps.core.validators import validar_identificacion_fiscal, validar_nombre_persona, validar_telefono


class TipoCliente(models.TextChoices):
    PERSONA = "PERSONA", "Persona"
    EMPRESA = "EMPRESA", "Empresa"


class Cliente(ModeloValidado):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="id_usuario",
        related_name="cliente",
    )
    tipo_cliente = models.CharField(max_length=20, choices=TipoCliente.choices)
    nombres = models.CharField(max_length=100, null=True, blank=True, validators=[validar_nombre_persona])
    apellidos = models.CharField(max_length=100, null=True, blank=True, validators=[validar_nombre_persona])
    nombre_empresa = models.CharField(max_length=150, null=True, blank=True)
    correo = models.EmailField(max_length=150)
    telefono = models.CharField(max_length=25, null=True, blank=True, validators=[validar_telefono])
    identificacion_fiscal = models.CharField(
        max_length=30, null=True, blank=True, validators=[validar_identificacion_fiscal]
    )
    direccion = models.CharField(max_length=250, null=True, blank=True)
    observaciones = models.TextField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    campos_texto_opcional = (
        "nombres",
        "apellidos",
        "nombre_empresa",
        "telefono",
        "identificacion_fiscal",
        "direccion",
        "observaciones",
    )

    class Meta:
        db_table = "clientes"
        verbose_name = "cliente"
        verbose_name_plural = "clientes"
        constraints = [en_lista("ck_clientes_tipo", "tipo_cliente", TipoCliente.values)]
        indexes = [
            models.Index(fields=["correo"], name="idx_clientes_correo"),
            models.Index(fields=["tipo_cliente"], name="idx_clientes_tipo"),
        ]

    def __str__(self):
        return self.nombre_visible

    @property
    def nombre_visible(self):
        if self.tipo_cliente == TipoCliente.EMPRESA:
            return self.nombre_empresa or self.correo
        return f"{self.nombres or ''} {self.apellidos or ''}".strip() or self.correo

    def clean(self):
        super().clean()
        errores = {}
        if self.correo:
            self.correo = self.correo.strip().lower()
        if self.tipo_cliente == TipoCliente.PERSONA:
            if not self.nombres:
                errores["nombres"] = "Los nombres son obligatorios para una persona."
            if not self.apellidos:
                errores["apellidos"] = "Los apellidos son obligatorios para una persona."
            if self.nombre_empresa:
                errores["nombre_empresa"] = "Una persona no puede tener nombre de empresa."
        elif self.tipo_cliente == TipoCliente.EMPRESA and not self.nombre_empresa:
            errores["nombre_empresa"] = "El nombre de la empresa es obligatorio."
        if errores:
            raise ValidationError(errores)
