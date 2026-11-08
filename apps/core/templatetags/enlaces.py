import re
from urllib.parse import quote

from django import template

register = template.Library()


@register.simple_tag
def whatsapp_url(telefono, mensaje=""):
    digitos = re.sub(r"\D", "", str(telefono or ""))
    if not digitos:
        return ""
    enlace = f"https://wa.me/{digitos}"
    return f"{enlace}?text={quote(str(mensaje))}" if mensaje else enlace
