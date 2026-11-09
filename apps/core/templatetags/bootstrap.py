from django import template
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()

CLASES_BADGE = {
    "PENDIENTE": "warning",
    "SOLICITADA": "warning",
    "BORRADOR": "secondary",
    "ENVIADA": "info",
    "ACEPTADA": "success",
    "RECHAZADA": "danger",
    "VENCIDA": "danger",
    "CANCELADA": "danger",
    "ANULADA": "danger",
    "EN_REVISION": "info",
    "APROBADO": "primary",
    "EN_PRODUCCION": "primary",
    "EN_ESPERA": "secondary",
    "FINALIZADO": "success",
    "ENTREGADO": "success",
    "PARCIALMENTE_PAGADA": "info",
    "PAGADA": "success",
    "CONFIRMADO": "success",
    "RECHAZADO": "danger",
    "REEMBOLSADO": "secondary",
}

CLASES_TOAST = {
    "success": "text-bg-success",
    "error": "text-bg-danger",
    "warning": "text-bg-warning",
    "info": "text-bg-info",
    "debug": "text-bg-secondary",
}

TITULOS_TOAST = {"success": "Listo", "error": "Error", "warning": "Atención", "info": "Información"}

VALIDACIONES = {
    ("customer", "cuenta"): "perfil",
    ("customer", "cotizar"): "cotizar",
    ("administrator", "producto_crear"): "producto",
    ("administrator", "producto_editar"): "producto",
    ("administrator", "servicio_crear"): "servicio",
    ("administrator", "servicio_editar"): "servicio",
    ("administrator", "categoria_crear"): "categoria",
    ("administrator", "categoria_editar"): "categoria",
    ("administrator", "usuario_crear"): "empleado",
    ("administrator", "usuario_editar"): "usuario",
}
CON_PK = ("producto", "servicio", "categoria", "usuario")


@register.filter
def badge(valor, texto=None):
    return format_html('<span class="badge text-bg-{}">{}</span>', CLASES_BADGE.get(str(valor), "secondary"), texto or valor)


@register.filter
def clase_toast(etiqueta):
    return CLASES_TOAST.get(str(etiqueta), "text-bg-info")


@register.filter
def titulo_toast(etiqueta):
    return TITULOS_TOAST.get(str(etiqueta), "Información")


@register.filter
def bs(campo):
    widget = campo.field.widget
    tipo = getattr(widget, "input_type", "")
    if tipo == "checkbox":
        clase = "form-check-input"
    elif tipo == "select":
        clase = "form-select"
    else:
        clase = "form-control"
    clases = " ".join(filter(None, [widget.attrs.get("class", ""), clase, "is-invalid" if campo.errors else ""]))
    return campo.as_widget(attrs={"class": clases})


@register.inclusion_tag("components/formulario.html")
def formulario_bs(form):
    return {"form": form}


@register.simple_tag(takes_context=True)
def atributos_validacion(context):
    request = context.get("request")
    coincidencia = getattr(request, "resolver_match", None)
    clave = VALIDACIONES.get((coincidencia.namespace, coincidencia.url_name)) if coincidencia else None
    if not clave:
        return ""
    partes = [format_html('data-validar="{}" data-validar-url="{}"', clave, reverse("validar_campo", args=[clave]))]
    pk = coincidencia.kwargs.get("pk")
    if pk and clave in CON_PK:
        partes.append(format_html('data-validar-pk="{}"', pk))
    return mark_safe(" ".join(partes))
