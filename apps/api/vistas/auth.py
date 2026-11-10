import logging
from datetime import timedelta

from allauth.account.forms import ResetPasswordForm
from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

from apps.api import serializadores as ser
from apps.api.autenticacion import CANAL, api, cerrar_token, emitir_token, _almacen
from apps.api.limites import limitar
from apps.api.respuestas import ErrorAPI, cadena, exito, leer_json
from apps.clientes.services.clientes import asegurar_cliente
from apps.core.validators import validar_nombre_persona, validar_telefono
from apps.usuarios.constants import ESTADO_ACTIVO, ESTADO_PENDIENTE, GRUPO_CLIENTE
from apps.usuarios.models import Usuario
from apps.usuarios.sesiones import cerrar_otras_sesiones

registro = logging.getLogger("apps.api")
MENSAJE_REGISTRO = (
    "Si el correo no estaba registrado, recibirá un mensaje para confirmarlo. "
    "Si ya tiene cuenta, inicie sesión."
)


def _mensajes(validador, valor):
    try:
        validador(valor)
    except ValidationError as error:
        return list(error.messages)
    return []


def _enviar_confirmacion(request, direccion):
    try:
        direccion.send_confirmation(request, signup=True)
    except Exception:
        registro.exception("No se pudo enviar el correo de confirmación a %s", direccion.email)


@api(("POST",), requiere_sesion=False)
def registro_cuenta(request):
    limitar(request, "registro", 10, 3600)
    datos = leer_json(request)
    nombres, apellidos = cadena(datos, "nombres"), cadena(datos, "apellidos")
    correo, telefono = cadena(datos, "correo").lower(), cadena(datos, "telefono")
    password = datos.get("password") if isinstance(datos.get("password"), str) else ""
    errores = {}
    for campo, valor in (("nombres", nombres), ("apellidos", apellidos)):
        if not valor:
            errores[campo] = ["Este campo es obligatorio."]
        elif len(valor) > 100:
            errores[campo] = ["Máximo 100 caracteres."]
        elif _mensajes(validar_nombre_persona, valor):
            errores[campo] = _mensajes(validar_nombre_persona, valor)
    if telefono and _mensajes(validar_telefono, telefono):
        errores["telefono"] = _mensajes(validar_telefono, telefono)
    try:
        validate_email(correo)
        if len(correo) > 150:
            raise ValidationError("demasiado largo")
    except ValidationError:
        errores["correo"] = ["Ingrese un correo válido (máximo 150 caracteres)."]
    if not password:
        errores["password"] = ["Este campo es obligatorio."]
    elif datos.get("password2") is not None and datos.get("password2") != password:
        errores["password2"] = ["Las contraseñas no coinciden."]
    if errores:
        raise ErrorAPI("Revise los datos indicados.", "datos_invalidos", 400, errores)
    try:
        validate_password(password, user=Usuario(correo=correo, nombres=nombres, apellidos=apellidos))
    except ValidationError as error:
        raise ErrorAPI("La contraseña no es suficientemente segura.", "datos_invalidos", 400, {"password": list(error.messages)})

    if Usuario.objects.filter(correo__iexact=correo).exists():
        return exito({"mensaje": MENSAJE_REGISTRO}, 201)
    try:
        with transaction.atomic():
            usuario = Usuario.objects.create_user(
                correo=correo,
                password=password,
                nombres=nombres,
                apellidos=apellidos,
                telefono=telefono or None,
                estado_id=ESTADO_PENDIENTE,
            )
            usuario.groups.add(Group.objects.get_or_create(name=GRUPO_CLIENTE)[0])
            asegurar_cliente(usuario)
            direccion = EmailAddress.objects.create(user=usuario, email=correo, primary=True, verified=False)
    except ValidationError as error:
        raise ErrorAPI("Revise los datos indicados.", "datos_invalidos", 400, {"general": list(error.messages)})
    _enviar_confirmacion(request, direccion)
    return exito({"mensaje": MENSAJE_REGISTRO}, 201)


@api(("POST",), requiere_sesion=False)
def reenviar_confirmacion(request):
    limitar(request, "reenviar", 5, 3600)
    correo = cadena(leer_json(request), "correo").lower()
    direccion = EmailAddress.objects.filter(
        email__iexact=correo, verified=False, user__estado_id=ESTADO_PENDIENTE
    ).first()
    if direccion is not None:
        _enviar_confirmacion(request, direccion)
    return exito({"mensaje": "Si existe una cuenta pendiente de confirmación, se envió un nuevo correo."})


def _respuesta_sesion(usuario, cliente, token):
    expira = timezone.now() + timedelta(days=settings.API_TOKEN_DIAS)
    return {
        "token": token,
        "tipo": "Bearer",
        "expira_en": ser.fecha(expira),
        "usuario": ser.usuario(usuario),
        "cliente": ser.cliente(cliente),
    }


@api(("POST",), requiere_sesion=False)
def login(request):
    datos = leer_json(request)
    correo = cadena(datos, "correo").lower()
    password = datos.get("password") if isinstance(datos.get("password"), str) else ""
    if not correo or not password:
        raise ErrorAPI("Indique su correo y su contraseña.", "datos_invalidos", 400)
    try:
        usuario = authenticate(request, username=correo, password=password)
    except PermissionDenied:
        raise ErrorAPI("Demasiados intentos fallidos. Intente de nuevo más tarde.", "bloqueado", 429)
    if usuario is None:
        raise ErrorAPI("Correo o contraseña incorrectos.", "credenciales_invalidas", 401)
    if usuario.estado_id == ESTADO_PENDIENTE:
        raise ErrorAPI("Confirme su correo para poder ingresar.", "correo_no_confirmado", 403)
    if usuario.estado_id != ESTADO_ACTIVO or not usuario.is_active:
        raise ErrorAPI("Su cuenta no está habilitada. Contacte al equipo.", "cuenta_inactiva", 403)
    if not usuario.tiene_algun_rol((GRUPO_CLIENTE,)):
        raise ErrorAPI("Esta cuenta no tiene acceso a la app de clientes.", "sin_permiso", 403)
    cliente = asegurar_cliente(usuario)
    token = emitir_token(usuario, getattr(usuario, "backend", None))
    Usuario.objects.filter(pk=usuario.pk).update(last_login=timezone.now())
    if settings.API_SESION_UNICA:
        cerrar_otras_sesiones(usuario, token, canal=CANAL)
    return exito(_respuesta_sesion(usuario, cliente, token))


@api(("POST",))
def refrescar(request):
    nuevo = emitir_token(request.usuario, None)
    cerrar_token(request.token_api)
    return exito(_respuesta_sesion(request.usuario, request.cliente, nuevo))


@api(("POST",))
def cerrar_sesion(request):
    cerrar_token(request.token_api)
    return exito()


@api(("POST",), requiere_sesion=False)
def recuperar_password(request):
    limitar(request, "recuperar", 5, 3600)
    correo = cadena(leer_json(request), "correo").lower()
    if correo:
        try:
            formulario = ResetPasswordForm({"email": correo})
            if formulario.is_valid():
                formulario.save(request)
        except Exception:
            registro.exception("No se pudo iniciar la recuperación de contraseña")
    return exito({"mensaje": "Si el correo está registrado, recibirá instrucciones para restablecer su contraseña."})


@api(("POST",))
def cambiar_password(request):
    datos = leer_json(request)
    actual = datos.get("password_actual") if isinstance(datos.get("password_actual"), str) else ""
    nueva = datos.get("password_nueva") if isinstance(datos.get("password_nueva"), str) else ""
    usuario = request.usuario
    if not usuario.check_password(actual):
        raise ErrorAPI("La contraseña actual no es correcta.", "datos_invalidos", 400, {"password_actual": ["No es correcta."]})
    try:
        validate_password(nueva, user=usuario)
    except ValidationError as error:
        raise ErrorAPI("La contraseña nueva no es suficientemente segura.", "datos_invalidos", 400, {"password_nueva": list(error.messages)})
    usuario.set_password(nueva)
    usuario.save(update_fields=["password"])
    sesion = _almacen()(session_key=request.token_api)
    sesion["_auth_user_hash"] = usuario.get_session_auth_hash()
    sesion.save()
    return exito({"mensaje": "Contraseña actualizada. Las demás sesiones se cerraron."})
