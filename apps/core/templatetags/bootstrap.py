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

# >>> fase-9b
PROGRESO_ENCARGO = {
    "PENDIENTE": 25,
    "EN_REVISION": 25,
    "APROBADO": 50,
    "EN_ESPERA": 50,
    "EN_PRODUCCION": 75,
    "FINALIZADO": 100,
    "ENTREGADO": 100,
}


@register.filter
def progreso_valor(estado):
    return PROGRESO_ENCARGO.get(str(estado), 0)


@register.filter
def progreso_clase(estado):
    return f"w-{PROGRESO_ENCARGO.get(str(estado), 25)}"
# <<< fase-9b

# >>> ui-1
ICONOS_TOAST = {"success": "check_circle", "error": "error", "warning": "warning", "info": "info"}


@register.simple_tag(takes_context=True)
def activo(context, *nombres):
    coincidencia = getattr(context.get("request"), "resolver_match", None)
    return "active" if coincidencia and coincidencia.view_name in nombres else ""


@register.filter
def tipo_toast(etiqueta):
    etiqueta = str(etiqueta)
    return etiqueta if etiqueta in ICONOS_TOAST else "info"


@register.filter
def icono_toast(etiqueta):
    return ICONOS_TOAST[tipo_toast(etiqueta)]
# <<< ui-1

# >>> ui-2
ICONOS_KPI = (
    ("vencida", "event_busy"),
    ("stock", "inventory"),
    ("ticket", "confirmation_number"),
    ("saldo", "savings"),
    ("por cobrar", "pending_actions"),
    ("cobrado", "account_balance_wallet"),
    ("ventas", "payments"),
    ("facturad", "request_quote"),
    ("factura", "receipt_long"),
    ("cliente", "group_add"),
    ("conversi", "percent"),
    ("cotizaci", "request_quote"),
    ("pedido", "package_2"),
    ("encargo", "package_2"),
    ("soporte", "support_agent"),
    ("anulada", "block"),
)


@register.filter
def icono_kpi(titulo):
    minuscula = str(titulo).lower()
    for clave, icono in ICONOS_KPI:
        if clave in minuscula:
            return icono
    return "analytics"
# <<< ui-2

# >>> fase-9c
from django.conf import settings as _ajustes


@register.simple_tag(takes_context=True)
def panel_actual(context):
    """Panel cuya barra se muestra: el del espacio de nombres, o el del rol en paginas de cuenta."""
    request = context.get("request")
    usuario = getattr(request, "user", None)
    coincidencia = getattr(request, "resolver_match", None)
    espacio = coincidencia.namespace if coincidencia else ""
    if espacio in ("customer", "operator", "administrator"):
        return espacio
    if espacio == "guest" or usuario is None or not usuario.is_authenticated:
        return "guest"
    from apps.usuarios.selectors.usuarios import destino_por_rol

    destino = destino_por_rol(usuario)
    return destino.split(":")[0] if destino else "guest"


@register.simple_tag(takes_context=True)
def es_rol(context, *roles):
    usuario = getattr(context.get("request"), "user", None)
    return bool(usuario is not None and usuario.is_authenticated and usuario.tiene_algun_rol(roles))


@register.simple_tag
def imagen_max_bytes():
    return getattr(_ajustes, "IMAGEN_MAX_BYTES", 2097152)


@register.simple_tag
def imagen_max_mb():
    return f"{getattr(_ajustes, 'IMAGEN_MAX_BYTES', 2097152) / 1048576:g}"
# <<< fase-9c
