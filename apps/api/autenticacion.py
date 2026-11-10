import logging
from functools import wraps
from importlib import import_module

from django.conf import settings
from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.http import Http404
from django.utils.crypto import constant_time_compare
from django.views.decorators.csrf import csrf_exempt

from apps.api.respuestas import ErrorAPI, fallo
from apps.clientes.services.clientes import asegurar_cliente
from apps.usuarios.constants import ESTADO_ACTIVO, GRUPO_CLIENTE
from apps.usuarios.models import Usuario

registro = logging.getLogger("apps.api")
CANAL = "api"
BACKEND_POR_DEFECTO = "django.contrib.auth.backends.ModelBackend"


def _almacen():
    return import_module(settings.SESSION_ENGINE).SessionStore


def emitir_token(usuario, backend=None):
    """Crea una sesion de canal "api" y devuelve su clave como token Bearer."""
    sesion = _almacen()()
    sesion[SESSION_KEY] = str(usuario.pk)
    sesion[BACKEND_SESSION_KEY] = backend or BACKEND_POR_DEFECTO
    sesion[HASH_SESSION_KEY] = usuario.get_session_auth_hash()
    sesion["canal"] = CANAL
    sesion.set_expiry(settings.API_TOKEN_DIAS * 86400)
    sesion.create()
    return sesion.session_key


def cerrar_token(token):
    if token:
        _almacen()(session_key=token).delete()


def usuario_de_token(request):
    partes = request.META.get("HTTP_AUTHORIZATION", "").split(" ", 1)
    if len(partes) != 2 or partes[0].lower() != "bearer":
        return None
    token = partes[1].strip()
    if not 16 <= len(token) <= 64 or not token.isalnum():
        return None
    datos = _almacen()(session_key=token).load()
    if datos.get("canal") != CANAL or SESSION_KEY not in datos:
        return None
    try:
        usuario = Usuario.objects.get(pk=datos[SESSION_KEY])
    except (Usuario.DoesNotExist, ValueError, TypeError):
        return None
    if not usuario.is_active or usuario.estado_id != ESTADO_ACTIVO:
        return None
    if not constant_time_compare(datos.get(HASH_SESSION_KEY, ""), usuario.get_session_auth_hash()):
        return None
    request.token_api = token
    return usuario


def api(metodos=("GET",), requiere_sesion=True):
    """Decorador de vistas de la API: metodo permitido, token, rol Customer y errores JSON."""

    def decorador(vista):
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            try:
                if request.method not in metodos:
                    respuesta = fallo("Método no permitido.", "metodo_no_permitido", 405)
                    respuesta["Allow"] = ", ".join(metodos)
                    return respuesta
                if requiere_sesion:
                    usuario = usuario_de_token(request)
                    if usuario is None:
                        respuesta = fallo("Sesión no válida o expirada.", "no_autenticado", 401)
                        respuesta["WWW-Authenticate"] = "Bearer"
                        return respuesta
                    if not usuario.tiene_algun_rol((GRUPO_CLIENTE,)):
                        return fallo("Esta cuenta no tiene acceso a la app de clientes.", "sin_permiso", 403)
                    request.user = usuario
                    request.usuario = usuario
                    request.cliente = asegurar_cliente(usuario)
                return vista(request, *args, **kwargs)
            except ErrorAPI as error:
                return fallo(error.mensaje, error.codigo, error.estado, error.campos)
            except Http404:
                return fallo("El recurso solicitado no existe.", "no_encontrado", 404)
            except PermissionDenied as error:
                return fallo(str(error) or "No tiene permiso para esta acción.", "sin_permiso", 403)
            except Exception:
                registro.exception("Error no controlado en %s", request.path)
                if connection.in_atomic_block:
                    transaction.set_rollback(True)
                return fallo("Ocurrió un error interno. Intente nuevamente.", "error_interno", 500)

        return csrf_exempt(envoltura)

    return decorador
