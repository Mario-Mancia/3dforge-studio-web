import hashlib
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request

from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.api.autenticacion import api, emitir_token
from apps.api.limites import limitar
from apps.api.respuestas import ErrorAPI, cadena, exito, leer_json
from apps.api.vistas.auth import _respuesta_sesion
from apps.clientes.services.clientes import asegurar_cliente
from apps.usuarios.adapters import _nombre_o_defecto
from apps.usuarios.constants import ESTADO_ACTIVO, ESTADO_PENDIENTE, GRUPO_CLIENTE
from apps.usuarios.models import Usuario

registro = logging.getLogger("apps.api")
EMISORES_GOOGLE = ("accounts.google.com", "https://accounts.google.com")
URL_TOKENINFO = "https://oauth2.googleapis.com/tokeninfo"


def _cliente_id_google():
    try:
        return settings.SOCIALACCOUNT_PROVIDERS["google"]["APP"]["client_id"] or ""
    except (AttributeError, KeyError, TypeError):
        return ""


def _consultar_google(id_token):
    """Valida el id_token con Google (endpoint tokeninfo) y devuelve sus datos."""
    url = f"{URL_TOKENINFO}?{urllib.parse.urlencode({'id_token': id_token})}"
    try:
        with urllib.request.urlopen(url, timeout=8) as respuesta:
            return json.loads(respuesta.read().decode("utf-8"))
    except urllib.error.HTTPError:
        raise ErrorAPI("Google rechazó el inicio de sesión. Intente de nuevo.", "token_invalido", 401)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        raise ErrorAPI("No se pudo contactar a Google. Intente más tarde.", "google_no_disponible", 503)


def _invalido(mensaje="No se pudo validar la cuenta de Google."):
    return ErrorAPI(mensaje, "token_invalido", 401)


def _validar_datos(datos, cliente_id, nonce_crudo):
    if not cliente_id:
        raise ErrorAPI("El inicio de sesión con Google no está configurado en el servidor.", "google_no_configurado", 503)
    if not isinstance(datos, dict) or datos.get("aud") != cliente_id:
        raise _invalido()
    if datos.get("iss") not in EMISORES_GOOGLE:
        raise _invalido()
    try:
        if int(datos.get("exp", 0)) < time.time():
            raise _invalido("La sesión de Google expiró. Intente de nuevo.")
    except (TypeError, ValueError):
        raise _invalido()
    if str(datos.get("email_verified", "")).lower() != "true":
        raise _invalido("Su correo de Google no está verificado.")
    if nonce_crudo and datos.get("nonce") != hashlib.sha256(nonce_crudo.encode("utf-8")).hexdigest():
        raise _invalido()
    correo = (datos.get("email") or "").strip().lower()
    if not correo or len(correo) > 150:
        raise _invalido()
    return correo


def _verificar_correo(usuario, correo):
    direccion = EmailAddress.objects.filter(user=usuario, email__iexact=correo).first()
    if direccion is None:
        EmailAddress.objects.create(user=usuario, email=correo, primary=True, verified=True)
    elif not direccion.verified:
        direccion.verified = True
        direccion.save(update_fields=["verified"])


def _resolver_usuario(correo, datos):
    usuario = Usuario.objects.filter(correo__iexact=correo).first()
    if usuario is None:
        usuario = Usuario.objects.create_user(
            correo=correo,
            password=None,
            nombres=_nombre_o_defecto(datos.get("given_name"), "Cliente"),
            apellidos=_nombre_o_defecto(datos.get("family_name"), "Sin apellido"),
            estado_id=ESTADO_ACTIVO,
        )
        usuario.groups.add(Group.objects.get_or_create(name=GRUPO_CLIENTE)[0])
    else:
        if not usuario.tiene_algun_rol((GRUPO_CLIENTE,)) and usuario.estado_id == ESTADO_ACTIVO:
            raise ErrorAPI("Esta cuenta no tiene acceso a la app de clientes.", "sin_permiso", 403)
        if not usuario.is_active or usuario.estado_id not in (ESTADO_ACTIVO, ESTADO_PENDIENTE):
            raise ErrorAPI("Su cuenta no está habilitada. Contacte al equipo.", "cuenta_inactiva", 403)
        if usuario.estado_id == ESTADO_PENDIENTE:
            Usuario.objects.filter(pk=usuario.pk).update(estado_id=ESTADO_ACTIVO)
            usuario.refresh_from_db()
        if not usuario.tiene_algun_rol((GRUPO_CLIENTE,)):
            raise ErrorAPI("Esta cuenta no tiene acceso a la app de clientes.", "sin_permiso", 403)
    _verificar_correo(usuario, correo)
    return usuario


@api(("POST",), requiere_sesion=False)
def login_google(request):
    limitar(request, "google", 30, 3600)
    datos_pedido = leer_json(request)
    id_token = cadena(datos_pedido, "id_token")
    if not id_token or len(id_token) > 4096:
        raise ErrorAPI("Falta la credencial de Google.", "datos_invalidos", 400)
    datos_google = _consultar_google(id_token)
    correo = _validar_datos(datos_google, _cliente_id_google(), cadena(datos_pedido, "nonce"))
    try:
        with transaction.atomic():
            usuario = _resolver_usuario(correo, datos_google)
            cliente = asegurar_cliente(usuario)
    except ValidationError as error:
        raise ErrorAPI("No se pudo crear la cuenta con los datos de Google.", "datos_invalidos", 400, {"general": list(error.messages)})
    token = emitir_token(usuario, "django.contrib.auth.backends.ModelBackend")
    Usuario.objects.filter(pk=usuario.pk).update(last_login=timezone.now())
    return exito(_respuesta_sesion(usuario, cliente, token))
