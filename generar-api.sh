#!/usr/bin/env bash
set -Eeuo pipefail

readonly RAIZ_POR_DEFECTO="/home/mmancia/Projects/Web/3dforge-studio/3dforge-studio-web"

RAIZ=""
DIR_ACTUAL=""
RESPALDO=""
CREADOS=0
ACTUALIZADOS=0
SIN_CAMBIOS=0
OMITIDOS=0
AVISOS=()

info() { printf '[INFO] %s\n' "$*"; }
ok() { printf '[ OK ] %s\n' "$*"; }
advertir() { printf '[AVISO] %s\n' "$*" >&2; AVISOS+=("$*"); }
fallar() { printf '[ERROR] %s\n' "$*" >&2; exit 1; }

ayuda() {
    cat <<'__FIN__'
Uso: generar-proyecto.sh [opciones] [RAIZ_DEL_PROYECTO]

  --instalar          instala requirements.txt en el entorno activo (.venv)
  --sin-migraciones   no ejecuta makemigrations al final
  -h, --ayuda         muestra esta ayuda

Capa de datos y configuracion: se regeneran con respaldo en .respaldo/.
Vistas, plantillas, formularios, servicios y selectores: solo se crean si faltan.
__FIN__
}

validar_ruta() {
    local r="$1"
    [[ -n $r && $r != /* && $r != *..* && $r =~ ^[A-Za-z0-9_./-]+$ ]] || fallar "Ruta no permitida: '$r'"
}

rel_actual() { printf '%s' "${DIR_ACTUAL:+$DIR_ACTUAL/}$1"; }

ir_raiz() {
    DIR_ACTUAL=""
    cd -- "$RAIZ"
}

ir_a() {
    validar_ruta "$1"
    mkdir -p -- "$RAIZ/$1"
    cd -- "$RAIZ/$1"
    DIR_ACTUAL="$1"
}

leer() {
    local rel
    rel="$(rel_actual "$1")"
    validar_ruta "$rel"
    [[ -f "$RAIZ/$rel" ]] || return 1
    cat -- "$RAIZ/$rel"
}

respaldar() {
    local rel="$1"
    [[ -n $RESPALDO ]] || RESPALDO="$RAIZ/.respaldo/$(date +%Y%m%d-%H%M%S)"
    mkdir -p -- "$(dirname -- "$RESPALDO/$rel")"
    cp -p -- "$RAIZ/$rel" "$RESPALDO/$rel"
}

eliminar() {
    local rel
    rel="$(rel_actual "$1")"
    validar_ruta "$rel"
    [[ -f "$RAIZ/$rel" ]] || return 0
    respaldar "$rel"
    rm -f -- "$RAIZ/$rel"
}

escribir() {
    local rel destino tmp
    rel="$(rel_actual "$1")"
    validar_ruta "$rel"
    destino="$RAIZ/$rel"
    tmp="$(mktemp)"
    cat >"$tmp"
    mkdir -p -- "$(dirname -- "$destino")"
    if [[ -e $destino ]]; then
        if cmp -s -- "$tmp" "$destino"; then
            rm -f -- "$tmp"
            SIN_CAMBIOS=$((SIN_CAMBIOS + 1))
            return 0
        fi
        respaldar "$rel"
        rm -f -- "$destino"
        ACTUALIZADOS=$((ACTUALIZADOS + 1))
    else
        CREADOS=$((CREADOS + 1))
    fi
    mv -- "$tmp" "$destino"
    chmod 0644 -- "$destino"
}

crear_si_falta() {
    local rel destino
    rel="$(rel_actual "$1")"
    validar_ruta "$rel"
    destino="$RAIZ/$rel"
    if [[ -e $destino ]]; then
        cat >/dev/null
        OMITIDOS=$((OMITIDOS + 1))
        return 0
    fi
    escribir "$1"
}

vacio() { escribir "$1" </dev/null; }
vacio_si_falta() { crear_si_falta "$1" </dev/null; }

asegurar_lineas() {
    local archivo="$1" contenido="" linea
    shift
    [[ -f "$RAIZ/$archivo" ]] && contenido="$(<"$RAIZ/$archivo")"
    for linea in "$@"; do
        grep -qxF -- "$linea" <<<"$contenido" || contenido+=$'\n'"$linea"
    done
    printf '%s\n' "${contenido#$'\n'}" | escribir "$archivo"
}

asegurar_claves() {
    local archivo="$1" contenido="" clave
    shift
    [[ -f "$RAIZ/$archivo" ]] && contenido="$(<"$RAIZ/$archivo")"
    for clave in "$@"; do
        grep -q -- "^${clave}=" <<<"$contenido" || contenido+=$'\n'"${clave}="
    done
    printf '%s\n' "${contenido#$'\n'}" | escribir "$archivo"
}

resolver_raiz() {
    local candidato="${1:-}" aqui
    if [[ -z $candidato ]]; then
        aqui="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
        if [[ -f "$aqui/manage.py" ]]; then
            candidato="$aqui"
        elif [[ -f "$PWD/manage.py" ]]; then
            candidato="$PWD"
        else
            candidato="$RAIZ_POR_DEFECTO"
        fi
    fi
    [[ -d $candidato ]] || fallar "No existe el directorio raiz: $candidato"
    RAIZ="$(cd -- "$candidato" && pwd -P)"
    [[ -f "$RAIZ/manage.py" && -d "$RAIZ/config" ]] || fallar "No parece la raiz del proyecto Django: $RAIZ"
}


ayuda() {
    cat <<'__FIN__'
Uso: generar-api.sh [opciones] [RAIZ_DEL_PROYECTO]

  -h, --ayuda    muestra esta ayuda

API JSON para la app movil de clientes (rol Customer), montada en /api/.
  - Sin dependencias nuevas: vistas Django planas (no requiere DRF) y las mismas
    formas, servicios y selectores que usa la web, por lo que las reglas de negocio,
    notificaciones, correos y archivos se comportan igual.
  - Autenticacion por token Bearer (opaco) respaldado por la tabla de sesiones de
    Django: sin migraciones. Login con axes (bloqueo por intentos), registro con
    confirmacion por correo (allauth), recuperacion de contrasena y cambio de clave.
  - Endpoints: perfil, panel, catalogo (publico), validacion de carrito y compra
    (idempotente), cotizaciones con archivos (multipart), pedidos, facturas,
    notificaciones y soporte.
  - Pensada para probar desde el celular por Tailscale (ver seccion P de la tasklist).
Cambios en el proyecto existente (minimos): config/urls.py (+1 linea), settings (bloques
nuevos), apps/usuarios/sesiones.py (sesion unica por canal), apps/core/middleware.py (+/api/)
y apps/encargos/services/compras.py (+funciones al final). No genera migraciones.
__FIN__
}

PROPUESTAS=()

inyectar_bloque() {
    local archivo="$1" nombre="$2" ini fin contenido actual nuevo
    ini="# >>> ${nombre}"
    fin="# <<< ${nombre}"
    contenido="$(cat)"
    actual="$(leer "$archivo")" || fallar "No existe $(rel_actual "$archivo")"
    if [[ $actual == *"$ini"* ]]; then
        nuevo="${actual%%"$ini"*}${ini}"$'\n'"${contenido}"$'\n'"${fin}${actual#*"$fin"}"
    else
        nuevo="${actual}"$'\n\n'"${ini}"$'\n'"${contenido}"$'\n'"${fin}"
    fi
    printf '%s\n' "$nuevo" | escribir "$archivo"
}

insertar_antes() {
    local archivo="$1" ancla="$2" marca="$3" texto contenido
    texto="$(cat)"
    contenido="$(leer "$archivo")" || { advertir "No existe $(rel_actual "$archivo")"; return 0; }
    [[ $contenido == *"$marca"* ]] && return 0
    if [[ $contenido != *"$ancla"* ]]; then
        advertir "No se encontro el punto de insercion en $(rel_actual "$archivo"); agregue el boton de encargo a mano."
        return 0
    fi
    printf '%s\n' "${contenido/"$ancla"/"$texto"$'\n'"$ancla"}" | escribir "$archivo"
}


verificar_base() {
    [[ -f "$RAIZ/apps/portal/validacion.py" && -f "$RAIZ/apps/notificaciones/eventos.py" && -f "$RAIZ/apps/reportes/selectors/panel_cliente.py" ]] \
        || fallar "Faltan archivos de las fases 8 y 9. Ejecute primero los scripts anteriores."
}

# ============================================================
# CONFIGURACION DEL PROYECTO (cambios minimos)
# ============================================================

paso_configuracion() {
    info "Configuracion: settings, urls, sesiones por canal y middleware"

    ir_a "config/settings"
    inyectar_bloque "base.py" "api" <<'__FIN__'
API_TOKEN_DIAS = int(os.getenv("API_TOKEN_DIAS") or "30")
API_SESION_UNICA = (os.getenv("API_SESION_UNICA") or "False") == "True"
API_MAX_JSON_BYTES = 100 * 1024
AXES_LOCKOUT_CALLABLE = "apps.api.bloqueo.respuesta_bloqueo"
__FIN__
    inyectar_bloque "development.py" "api" <<'__FIN__'
# Pruebas desde el celular por Tailscale: nombres *.ts.net y los hosts de DJANGO_ALLOWED_HOSTS.
ALLOWED_HOSTS += [host for host in [".ts.net"] + lista_env("DJANGO_ALLOWED_HOSTS") if host not in ALLOWED_HOSTS]
__FIN__

    ir_a "config"
    insertar_antes "urls.py" '    path("", include("apps.portal.urls")),' "apps.api.urls" <<'__FIN__'
    path("api/", include("apps.api.urls")),
__FIN__

    ir_raiz
    asegurar_claves ".env.example" API_TOKEN_DIAS API_SESION_UNICA

    ir_a "apps/usuarios"
    escribir "sesiones.py" <<'__FIN__'
from django.contrib.auth import SESSION_KEY
from django.contrib.sessions.models import Session
from django.utils import timezone


def cerrar_otras_sesiones(usuario, sesion_actual=None, canal=None):
    """Cierra las demas sesiones del usuario DEL MISMO CANAL.

    canal=None son las sesiones web; las de la app movil llevan canal="api". Asi iniciar
    sesion en la web no expulsa al celular (ni al reves).
    """
    consulta = Session.objects.filter(expire_date__gte=timezone.now())
    if sesion_actual:
        consulta = consulta.exclude(session_key=sesion_actual)
    cerradas = 0
    for sesion in consulta.iterator():
        try:
            datos = sesion.get_decoded()
        except Exception:
            continue
        if datos.get(SESSION_KEY) == str(usuario.pk) and datos.get("canal") == canal:
            sesion.delete()
            cerradas += 1
    return cerradas
__FIN__

    ir_a "apps/core"
    escribir "middleware.py" <<'__FIN__'
from django.conf import settings
from django.utils.cache import add_never_cache_headers

PREFIJOS_PRIVADOS = ("/cliente/", "/operador/", "/administrador/", "/cuenta/", "/ir/", "/validar/", "/api/")
PREFIJOS_ESTATICOS = ("/static/", "/media/")


class SinCacheMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.prefijos = PREFIJOS_PRIVADOS + ("/" + settings.ADMIN_URL,)

    def __call__(self, request):
        respuesta = self.get_response(request)
        ruta = request.path
        if not ruta.startswith(PREFIJOS_ESTATICOS):
            usuario = getattr(request, "user", None)
            if ruta.startswith(self.prefijos) or (usuario is not None and usuario.is_authenticated):
                add_never_cache_headers(respuesta)
                respuesta["Pragma"] = "no-cache"
        if request.method == "POST" and ruta.rstrip("/").endswith("/logout"):
            respuesta["Clear-Site-Data"] = '"cache"'
        return respuesta
__FIN__

    ir_a "apps/encargos/services"
    inyectar_bloque "compras.py" "api" <<'__FIN__'
# ---- Compra sin sesion web (app movil): el carrito vive en el dispositivo -------------------


def _entero_estricto(valor):
    if isinstance(valor, bool):
        raise ValueError
    if isinstance(valor, int):
        return valor
    if isinstance(valor, str) and valor.strip().isdigit():
        return int(valor.strip())
    raise ValueError


def normalizar_items(items):
    if not isinstance(items, (list, tuple)) or not items:
        raise ErrorCompra("Su carrito está vacío.")
    resultado = {}
    for item in items:
        if not isinstance(item, dict):
            raise ErrorCompra("Los productos indicados no son válidos.")
        try:
            producto_id = _entero_estricto(item.get("producto_id"))
            cantidad = _entero_estricto(item.get("cantidad"))
        except ValueError:
            raise ErrorCompra("Los productos indicados no son válidos.")
        if not 1 <= cantidad <= MAX_POR_LINEA:
            raise ErrorCompra(f"La cantidad debe estar entre 1 y {MAX_POR_LINEA}.")
        resultado[producto_id] = resultado.get(producto_id, 0) + cantidad
        if resultado[producto_id] > MAX_POR_LINEA:
            raise ErrorCompra(f"No puede comprar más de {MAX_POR_LINEA} unidades de un mismo producto.")
    if len(resultado) > MAX_LINEAS:
        raise ErrorCompra("El carrito alcanzó el máximo de productos distintos.")
    return resultado


def lineas_de_items(items):
    normalizados = normalizar_items(items)
    productos = Producto.objects.in_bulk(list(normalizados))
    resultado = []
    for producto_id, cantidad in normalizados.items():
        producto = productos.get(producto_id)
        disponible = bool(producto and producto.activo and producto.stock >= cantidad)
        calculo = calcular_linea(cantidad, producto.precio) if disponible else None
        resultado.append(
            {"producto_id": producto_id, "producto": producto, "cantidad": cantidad, "disponible": disponible, "calculo": calculo}
        )
    return resultado


def confirmar_compra_api(cliente, usuario, items, token):
    token = str(token or "").strip()
    if not 8 <= len(token) <= 64:
        raise ErrorCompra("El identificador de la compra no es válido.")
    previo = cache.get(f"compra_resultado:{token}")
    if previo:
        raise CompraDuplicada(previo)
    if not cache.add(f"compra:{token}", 1, VIGENCIA_TOKEN):
        raise CompraDuplicada(cache.get(f"compra_resultado:{token}"))
    try:
        encargo = _crear_encargo(cliente, usuario, normalizar_items(items))
    except ErrorInventario as error:
        cache.delete(f"compra:{token}")
        raise ErrorCompra(str(error)) from error
    except Exception:
        cache.delete(f"compra:{token}")
        raise
    cache.set(f"compra_resultado:{token}", encargo.pk, VIGENCIA_TOKEN)
    return encargo
__FIN__
}

# ============================================================
# NUCLEO DE LA API
# ============================================================

paso_nucleo() {
    info "Nucleo de la API: respuestas, autenticacion, limites, bloqueo"
    ir_a "apps/api"
    vacio_si_falta "__init__.py"

    escribir "respuestas.py" <<'__FIN__'
import json

from django.conf import settings
from django.core.paginator import EmptyPage, Paginator
from django.http import JsonResponse


class ErrorAPI(Exception):
    def __init__(self, mensaje, codigo="error", estado=400, campos=None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo = codigo
        self.estado = estado
        self.campos = campos or {}


def exito(datos=None, estado=200):
    return JsonResponse(
        {"ok": True} if datos is None else datos, status=estado, safe=False, json_dumps_params={"ensure_ascii": False}
    )


def fallo(mensaje, codigo="error", estado=400, campos=None):
    cuerpo = {"error": {"codigo": codigo, "mensaje": mensaje, "campos": campos or {}}}
    return JsonResponse(cuerpo, status=estado, json_dumps_params={"ensure_ascii": False})


def fallo_formulario(formulario):
    campos = {
        ("general" if campo == "__all__" else campo): [str(error) for error in errores]
        for campo, errores in formulario.errors.items()
    }
    primero = next(iter(campos.values()))[0] if campos else "Datos no válidos."
    return fallo(primero, "datos_invalidos", 400, campos)


def leer_json(request):
    if not (request.content_type or "").startswith("application/json"):
        raise ErrorAPI("Se esperaba el tipo application/json.", "tipo_no_soportado", 415)
    if len(request.body) > settings.API_MAX_JSON_BYTES:
        raise ErrorAPI("La petición es demasiado grande.", "demasiado_grande", 413)
    try:
        datos = json.loads(request.body or b"{}")
    except ValueError:
        raise ErrorAPI("El cuerpo no es un JSON válido.", "json_invalido", 400)
    if not isinstance(datos, dict):
        raise ErrorAPI("El cuerpo debe ser un objeto JSON.", "json_invalido", 400)
    return datos


def cadena(datos, clave):
    valor = datos.get(clave)
    return valor.strip() if isinstance(valor, str) else ""


def paginar(request, consulta, serializar, por_pagina=20):
    try:
        numero = max(int(request.GET.get("pagina", 1)), 1)
        tamano = min(max(int(request.GET.get("por_pagina", por_pagina)), 1), 100)
    except (TypeError, ValueError):
        raise ErrorAPI("Los parámetros de paginación no son válidos.", "paginacion_invalida", 400)
    paginador = Paginator(consulta, tamano)
    try:
        pagina = paginador.page(numero)
    except EmptyPage:
        return {"resultados": [], "total": paginador.count, "pagina": numero, "paginas": paginador.num_pages, "hay_mas": False}
    return {
        "resultados": [serializar(objeto) for objeto in pagina.object_list],
        "total": paginador.count,
        "pagina": pagina.number,
        "paginas": paginador.num_pages,
        "hay_mas": pagina.has_next(),
    }
__FIN__

    escribir "limites.py" <<'__FIN__'
from django.core.cache import cache

from apps.api.respuestas import ErrorAPI


def limitar(request, clave, maximo, ventana):
    """Limita peticiones por IP (cache local: valido con un solo proceso)."""
    llave = f"api:limite:{clave}:{request.META.get('REMOTE_ADDR', '?')}"
    cache.add(llave, 0, ventana)
    try:
        usadas = cache.incr(llave)
    except ValueError:
        cache.set(llave, 1, ventana)
        usadas = 1
    if usadas > maximo:
        raise ErrorAPI("Demasiadas solicitudes. Intente de nuevo más tarde.", "limite_excedido", 429)
__FIN__

    escribir "bloqueo.py" <<'__FIN__'
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render


def respuesta_bloqueo(request, credentials=None):
    """Respuesta de axes al bloquear por intentos fallidos: JSON en /api/, HTML en la web."""
    if request.path.startswith("/api/"):
        cuerpo = {"error": {"codigo": "bloqueado", "mensaje": "Demasiados intentos fallidos. Intente de nuevo más tarde.", "campos": {}}}
        return JsonResponse(cuerpo, status=429, json_dumps_params={"ensure_ascii": False})
    return render(request, "errors/bloqueado.html", status=getattr(settings, "AXES_HTTP_RESPONSE_CODE", 403))
__FIN__

    escribir "autenticacion.py" <<'__FIN__'
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
__FIN__
}

# ============================================================
# SERIALIZADORES
# ============================================================

paso_serializadores() {
    info "Serializadores"
    ir_a "apps/api"
    escribir "serializadores.py" <<'__FIN__'
from decimal import Decimal

from django.core.files.storage import default_storage
from django.utils import timezone

CENTAVO = Decimal("0.01")
PROGRESO_ENCARGO = {
    "PENDIENTE": 25,
    "EN_REVISION": 25,
    "APROBADO": 50,
    "EN_ESPERA": 50,
    "EN_PRODUCCION": 75,
    "FINALIZADO": 100,
    "ENTREGADO": 100,
}


def dinero(valor):
    return None if valor is None else format(Decimal(valor).quantize(CENTAVO), "f")


def cantidad(valor):
    return None if valor is None else format(Decimal(valor).normalize(), "f")


def fecha(valor):
    return timezone.localtime(valor).isoformat() if valor else None


def _absoluta(request, ruta):
    return request.build_absolute_uri(ruta) if request is not None else ruta


def cliente(c):
    return {
        "id": c.pk,
        "tipo_cliente": c.tipo_cliente,
        "nombre_visible": c.nombre_visible,
        "nombres": c.nombres,
        "apellidos": c.apellidos,
        "nombre_empresa": c.nombre_empresa,
        "correo": c.correo,
        "telefono": c.telefono,
        "identificacion_fiscal": c.identificacion_fiscal,
        "direccion": c.direccion,
    }


def usuario(u):
    return {"id": u.pk, "correo": u.correo, "nombres": u.nombres, "apellidos": u.apellidos}


def negocio(c, request=None):
    if c is None:
        return {"nombre": "3DForge Studio", "correo": None, "telefono": None, "direccion": None, "sitio_web": None, "logo_url": None}
    logo = _absoluta(request, default_storage.url(c.logo)) if c.logo else None
    return {
        "nombre": c.nombre_negocio,
        "correo": c.correo,
        "telefono": c.telefono,
        "direccion": c.direccion,
        "sitio_web": c.sitio_web,
        "logo_url": logo,
    }


def producto(p, request=None):
    return {
        "id": p.pk,
        "sku": p.sku,
        "nombre": p.nombre,
        "descripcion": p.descripcion,
        "precio": dinero(p.precio),
        "stock": p.stock,
        "stock_minimo": p.stock_minimo,
        "disponibilidad": p.disponibilidad_codigo,
        "disponibilidad_texto": p.disponibilidad,
        "imagen_url": _absoluta(request, p.imagen_url) if p.imagen else None,
    }


def categoria(c):
    return {"id": c.pk, "nombre": c.nombre, "descripcion": c.descripcion}


def servicio(s):
    return {
        "id": s.pk,
        "categoria_id": s.categoria_id,
        "categoria": s.categoria.nombre,
        "nombre": s.nombre,
        "descripcion": s.descripcion,
        "precio_base": dinero(s.precio_base),
        "requiere_archivo": s.requiere_archivo,
    }


def archivo(a):
    return {
        "id": a.pk,
        "nombre": a.nombre_archivo,
        "formato": a.formato,
        "tamano_bytes": a.tamano_bytes,
        "fecha_subida": fecha(a.fecha_subida),
    }


def linea(d):
    return {
        "id": d.pk,
        "descripcion": d.descripcion,
        "especificaciones": getattr(d, "especificaciones", None) or {},
        "cantidad": cantidad(d.cantidad),
        "precio_unitario": dinero(d.precio_unitario),
        "descuento": dinero(d.descuento),
        "impuesto": dinero(d.impuesto),
        "subtotal": dinero(d.subtotal),
        "servicio_id": getattr(d, "servicio_id", None),
        "producto_id": getattr(d, "producto_id", None),
    }


def _importes(documento):
    return {
        "subtotal": dinero(documento.subtotal),
        "descuento": dinero(documento.descuento),
        "impuesto": dinero(documento.impuesto),
        "total": dinero(documento.total),
    }


def cotizacion_resumen(c):
    vencida = c.estado == "ENVIADA" and c.fecha_vencimiento is not None and c.fecha_vencimiento < timezone.now()
    return {
        "id": c.pk,
        "codigo": c.codigo,
        "estado": c.estado,
        "estado_texto": c.get_estado_display(),
        "fecha_emision": fecha(c.fecha_emision),
        "fecha_vencimiento": fecha(c.fecha_vencimiento),
        "plazo_entrega_dias": c.plazo_entrega_dias,
        **_importes(c),
        "vencida": vencida,
        "puede_responder": c.estado == "ENVIADA" and not vencida,
        "puede_cancelar": c.estado == "SOLICITADA",
    }


def cotizacion_detalle(c, encargo=None):
    datos = cotizacion_resumen(c)
    datos.update(
        {
            "solicitud": c.solicitud,
            "observaciones": c.observaciones,
            "lineas": [linea(d) for d in c.detalles.all()],
            "archivos": [archivo(a) for a in c.archivos.all()],
            "pedido": {"id": encargo.pk, "codigo": encargo.codigo} if encargo is not None else None,
        }
    )
    return datos


def encargo_resumen(e):
    return {
        "id": e.pk,
        "codigo": e.codigo,
        "estado": e.estado,
        "estado_texto": e.get_estado_display(),
        "progreso": PROGRESO_ENCARGO.get(e.estado),
        "fecha_solicitud": fecha(e.fecha_solicitud),
        "fecha_entrega_estimada": fecha(e.fecha_entrega_estimada),
        "fecha_entrega_real": fecha(e.fecha_entrega_real),
        "descripcion": e.descripcion,
        "cotizacion_id": e.cotizacion_id,
        **_importes(e),
        "puede_cancelar": e.estado == "PENDIENTE",
    }


def encargo_detalle(e):
    datos = encargo_resumen(e)
    responsable = e.empleado_responsable.usuario.nombre_completo if e.empleado_responsable_id else None
    datos.update(
        {
            "responsable": responsable,
            "lineas": [{**linea(d), "archivos": [archivo(a) for a in d.archivos.all()]} for d in e.detalles.all()],
            "historial": [
                {
                    "estado_anterior": h.estado_anterior,
                    "estado_nuevo": h.estado_nuevo,
                    "estado_nuevo_texto": h.get_estado_nuevo_display(),
                    "comentario": h.comentario,
                    "fecha": fecha(h.fecha_cambio),
                }
                for h in e.historial.all()
            ],
        }
    )
    return datos


def factura_resumen(f):
    return {
        "id": f.pk,
        "numero": f.numero_factura,
        "estado": f.estado,
        "estado_texto": f.get_estado_display(),
        "fecha_emision": fecha(f.fecha_emision),
        "fecha_vencimiento": fecha(f.fecha_vencimiento),
        "total": dinero(f.total),
        "saldo_pendiente": dinero(f.saldo_pendiente),
        "pedido_id": f.encargo_id,
    }


def factura_detalle(f):
    datos = factura_resumen(f)
    datos.update(
        {
            "nombre_facturacion": f.nombre_facturacion,
            "identificacion_fiscal": f.identificacion_fiscal,
            "direccion_facturacion": f.direccion_facturacion,
            **_importes(f),
            "lineas": [linea(d) for d in f.detalles.all()],
            "pagos": [
                {
                    "id": p.pk,
                    "monto": dinero(p.monto),
                    "fecha_pago": fecha(p.fecha_pago),
                    "referencia": p.referencia,
                    "metodo": p.metodo_pago.nombre,
                }
                for p in f.pagos.all()
                if p.estado == "CONFIRMADO"
            ],
            "aviso": "Los pagos en efectivo se coordinan con el equipo.",
        }
    )
    return datos


def notificacion(n):
    return {
        "id": n.pk,
        "titulo": n.titulo,
        "mensaje": n.mensaje,
        "tipo": n.tipo,
        "referencia_id": n.referencia_id,
        "leida": n.leida,
        "fecha": fecha(n.fecha_creacion),
    }


def soporte(s):
    return {
        "id": s.pk,
        "asunto": s.asunto,
        "descripcion": s.descripcion,
        "prioridad": s.prioridad,
        "prioridad_texto": s.get_prioridad_display(),
        "estado": s.estado,
        "estado_texto": s.get_estado_display(),
        "creada_en": fecha(s.creado_en),
        "actualizada_en": fecha(s.actualizado_en),
    }
__FIN__
}

# ============================================================
# VISTAS
# ============================================================

paso_vistas_cuenta() {
    info "Vistas: autenticacion, cuenta, panel y catalogo"
    ir_a "apps/api/vistas"
    vacio_si_falta "__init__.py"

    escribir "auth.py" <<'__FIN__'
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
__FIN__

    escribir "cuenta.py" <<'__FIN__'
from django.utils import timezone

from apps.api import serializadores as ser
from apps.api.autenticacion import api
from apps.api.respuestas import exito, fallo_formulario, leer_json
from apps.clientes.forms.clientes import PerfilClienteForm
from apps.clientes.services.clientes import guardar_perfil
from apps.core.models import ConfiguracionNegocio
from apps.reportes.selectors.panel_cliente import resumen_cliente

CAMPOS_PERFIL = ("tipo_cliente", "nombres", "apellidos", "nombre_empresa", "telefono", "identificacion_fiscal", "direccion")


@api(("GET",), requiere_sesion=False)
def salud(request):
    return exito({"ok": True, "servicio": "3DForge Studio API", "version": "1", "hora": ser.fecha(timezone.now())})


@api(("GET",), requiere_sesion=False)
def negocio(request):
    return exito(ser.negocio(ConfiguracionNegocio.objects.first(), request))


@api(("GET", "PUT", "PATCH"))
def perfil(request):
    if request.method == "GET":
        return exito(ser.cliente(request.cliente))
    datos = leer_json(request)
    entrada = {campo: getattr(request.cliente, campo) or "" for campo in CAMPOS_PERFIL}
    for campo in CAMPOS_PERFIL:
        if campo in datos:
            valor = datos[campo]
            entrada[campo] = "" if valor is None else str(valor)
    formulario = PerfilClienteForm(entrada, instance=request.cliente)
    if not formulario.is_valid():
        return fallo_formulario(formulario)
    return exito(ser.cliente(guardar_perfil(formulario)))


@api(("GET",))
def panel(request):
    resumen = resumen_cliente(request.cliente, request.usuario)
    kpis = resumen["kpis"]
    return exito(
        {
            "kpis": {
                "por_responder": kpis["por_responder"],
                "en_revision": kpis["en_revision"],
                "pedidos_en_curso": kpis["pedidos_en_curso"],
                "saldo_pendiente": ser.dinero(kpis["saldo_pendiente"]),
                "soporte_abierto": kpis["soporte_abierto"],
            },
            "cotizaciones": [ser.cotizacion_resumen(c) for c in resumen["cotizaciones"]],
            "pedidos": [ser.encargo_resumen(e) for e in resumen["pedidos"]],
            "facturas": [ser.factura_resumen(f) for f in resumen["facturas"]],
            "soporte": [ser.soporte(s) for s in resumen["soporte"]],
            "notificaciones": [ser.notificacion(n) for n, _destino in resumen["notificaciones"]],
        }
    )
__FIN__

    escribir "catalogo.py" <<'__FIN__'
from django.shortcuts import get_object_or_404

from apps.api import serializadores as ser
from apps.api.autenticacion import api
from apps.api.respuestas import ErrorAPI, exito, paginar
from apps.catalogo.selectors import catalogo as selectores


@api(("GET",), requiere_sesion=False)
def categorias(request):
    return exito({"resultados": [ser.categoria(c) for c in selectores.categorias_publicas()]})


@api(("GET",), requiere_sesion=False)
def productos(request):
    consulta = selectores.productos_publicos(request.GET.get("q", "").strip()[:100])
    return exito(paginar(request, consulta, lambda p: ser.producto(p, request)))


@api(("GET",), requiere_sesion=False)
def producto_detalle(request, pk):
    return exito(ser.producto(get_object_or_404(selectores.productos_publicos(), pk=pk), request))


@api(("GET",), requiere_sesion=False)
def servicios(request):
    categoria = request.GET.get("categoria", "")
    if categoria and not categoria.isdigit():
        raise ErrorAPI("La categoría indicada no es válida.", "datos_invalidos", 400)
    consulta = selectores.servicios_publicos(int(categoria) if categoria else None)
    return exito({"resultados": [ser.servicio(s) for s in consulta]})


@api(("GET",), requiere_sesion=False)
def servicio_detalle(request, pk):
    return exito(ser.servicio(get_object_or_404(selectores.servicios_publicos(), pk=pk)))
__FIN__
}

paso_vistas_documentos() {
    info "Vistas: compras, cotizaciones, pedidos, facturas, notificaciones y soporte"
    ir_a "apps/api/vistas"

    escribir "compras.py" <<'__FIN__'
from apps.api import serializadores as ser
from apps.api.autenticacion import api
from apps.api.respuestas import ErrorAPI, exito, leer_json
from apps.core.calculos import totales_documento
from apps.encargos.selectors import encargos as selectores
from apps.encargos.services import compras


@api(("POST",))
def validar_carrito(request):
    datos = leer_json(request)
    try:
        lineas = compras.lineas_de_items(datos.get("items"))
    except compras.ErrorCompra as error:
        raise ErrorAPI(str(error), "carrito_invalido", 400)
    calculos = [linea["calculo"] for linea in lineas if linea["calculo"]]
    totales = totales_documento(calculos)
    return exito(
        {
            "lineas": [
                {
                    "producto_id": linea["producto_id"],
                    "producto": ser.producto(linea["producto"], request) if linea["producto"] else None,
                    "cantidad": linea["cantidad"],
                    "disponible": linea["disponible"],
                    "subtotal": ser.dinero(linea["calculo"]["subtotal"]) if linea["calculo"] else None,
                    "impuesto": ser.dinero(linea["calculo"]["impuesto"]) if linea["calculo"] else None,
                }
                for linea in lineas
            ],
            "totales": {clave: ser.dinero(valor) for clave, valor in totales.items()},
            "hay_problemas": any(not linea["disponible"] for linea in lineas),
        }
    )


@api(("POST",))
def comprar(request):
    datos = leer_json(request)
    try:
        encargo = compras.confirmar_compra_api(request.cliente, request.usuario, datos.get("items"), datos.get("token"))
    except compras.CompraDuplicada as duplicada:
        previo = selectores.obtener_del_cliente(request.cliente, duplicada.encargo_id) if duplicada.encargo_id else None
        if previo is None:
            raise ErrorAPI("La compra ya está en proceso o fue procesada. Revise sus pedidos.", "compra_duplicada", 409)
        return exito({"duplicado": True, "pedido": ser.encargo_detalle(previo)})
    except compras.ErrorCompra as error:
        raise ErrorAPI(str(error), "compra_invalida", 400)
    pedido = selectores.obtener_del_cliente(request.cliente, encargo.pk)
    return exito({"duplicado": False, "pedido": ser.encargo_detalle(pedido)}, 201)
__FIN__

    escribir "cotizaciones.py" <<'__FIN__'
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404

from apps.api import serializadores as ser
from apps.api.autenticacion import api
from apps.api.respuestas import ErrorAPI, exito, fallo_formulario, leer_json, paginar
from apps.core.archivos import respuesta_descarga
from apps.core.storage import almacenamiento_privado
from apps.core.utiles import mensaje_de
from apps.cotizaciones.forms.cotizaciones import SolicitudCotizacionForm
from apps.cotizaciones.selectors import cotizaciones as selectores
from apps.cotizaciones.services import cotizaciones as servicios
from apps.encargos.models import Encargo

ACCIONES = {"aceptar": "aceptar_cotizacion", "rechazar": "rechazar_cotizacion", "cancelar": "cancelar_cotizacion"}
CAMPOS_ESPECIFICACIONES = ("material", "color", "dimensiones")


def _detalle(cliente, pk):
    cotizacion = selectores.obtener_del_cliente(cliente, pk)
    if cotizacion is None:
        raise Http404
    encargo = Encargo.objects.filter(cotizacion=cotizacion).first()
    return ser.cotizacion_detalle(cotizacion, encargo)


def _datos_json(datos):
    plano = {clave: ("" if valor is None else str(valor)) for clave, valor in datos.items() if not isinstance(valor, (dict, list))}
    especificaciones = datos.get("especificaciones")
    if isinstance(especificaciones, dict):
        for clave in CAMPOS_ESPECIFICACIONES:
            if especificaciones.get(clave) is not None:
                plano[clave] = str(especificaciones[clave])
    return plano


@api(("GET", "POST"))
def cotizaciones(request):
    if request.method == "GET":
        return exito(paginar(request, selectores.cotizaciones_del_cliente(request.cliente), ser.cotizacion_resumen))
    if (request.content_type or "").startswith("application/json"):
        formulario = SolicitudCotizacionForm(_datos_json(leer_json(request)))
    else:
        formulario = SolicitudCotizacionForm(request.POST, request.FILES)
    if not formulario.is_valid():
        return fallo_formulario(formulario)
    try:
        cotizacion = servicios.solicitar_cotizacion(
            cliente=request.cliente,
            usuario=request.usuario,
            servicio=formulario.cleaned_data["servicio"],
            cantidad=formulario.cleaned_data["cantidad"],
            descripcion=formulario.cleaned_data["descripcion"],
            solicitud=formulario.cleaned_data["solicitud"],
            especificaciones=formulario.especificaciones(),
            archivos=formulario.cleaned_data["archivos"],
        )
    except (servicios.ErrorCotizacion, ValidationError) as error:
        raise ErrorAPI(mensaje_de(error), "cotizacion_invalida", 400)
    return exito(_detalle(request.cliente, cotizacion.pk), 201)


@api(("GET",))
def cotizacion_detalle(request, pk):
    return exito(_detalle(request.cliente, pk))


@api(("POST",))
def cotizacion_accion(request, pk, accion):
    if accion not in ACCIONES:
        raise Http404
    cotizacion = selectores.obtener_del_cliente(request.cliente, pk)
    if cotizacion is None:
        raise Http404
    try:
        getattr(servicios, ACCIONES[accion])(cotizacion.pk, request.usuario)
    except servicios.CotizacionVencida:
        raise ErrorAPI("La cotización ya venció.", "cotizacion_vencida", 409)
    except servicios.ErrorCotizacion as error:
        raise ErrorAPI(str(error), "transicion_invalida", 409)
    return exito(_detalle(request.cliente, pk))


@api(("GET",))
def cotizacion_archivo(request, pk, archivo_id):
    cotizacion = selectores.obtener_del_cliente(request.cliente, pk)
    if cotizacion is None:
        raise Http404
    archivo = get_object_or_404(cotizacion.archivos.all(), pk=archivo_id)
    return respuesta_descarga(almacenamiento_privado, archivo.ruta_archivo, archivo.nombre_archivo)
__FIN__

    escribir "pedidos.py" <<'__FIN__'
from django.http import Http404

from apps.api import serializadores as ser
from apps.api.autenticacion import api
from apps.api.respuestas import ErrorAPI, exito, paginar
from apps.core.archivos import respuesta_descarga
from apps.core.storage import almacenamiento_privado
from apps.encargos.selectors import encargos as selectores
from apps.encargos.services import encargos as servicios
from apps.facturacion.selectors import facturacion as selectores_facturas


def _pedido(cliente, pk):
    encargo = selectores.obtener_del_cliente(cliente, pk)
    if encargo is None:
        raise Http404
    return encargo


@api(("GET",))
def pedidos(request):
    return exito(paginar(request, selectores.encargos_del_cliente(request.cliente), ser.encargo_resumen))


@api(("GET",))
def pedido_detalle(request, pk):
    return exito(ser.encargo_detalle(_pedido(request.cliente, pk)))


@api(("POST",))
def pedido_cancelar(request, pk):
    encargo = _pedido(request.cliente, pk)
    try:
        servicios.cancelar_por_cliente(encargo.pk, request.usuario)
    except servicios.ErrorEncargo as error:
        raise ErrorAPI(str(error), "transicion_invalida", 409)
    return exito(ser.encargo_detalle(_pedido(request.cliente, pk)))


@api(("GET",))
def pedido_archivo(request, pk, archivo_id):
    encargo = _pedido(request.cliente, pk)
    archivo = next((a for d in encargo.detalles.all() for a in d.archivos.all() if a.pk == archivo_id), None)
    if archivo is None:
        raise Http404
    return respuesta_descarga(almacenamiento_privado, archivo.ruta_archivo, archivo.nombre_archivo)


@api(("GET",))
def facturas(request):
    return exito(paginar(request, selectores_facturas.facturas_del_cliente(request.cliente), ser.factura_resumen))


@api(("GET",))
def factura_detalle(request, pk):
    factura = selectores_facturas.obtener_del_cliente(request.cliente, pk)
    if factura is None:
        raise Http404
    return exito(ser.factura_detalle(factura))
__FIN__

    escribir "seguimiento.py" <<'__FIN__'
from django.core.exceptions import ValidationError
from django.http import Http404

from apps.api import serializadores as ser
from apps.api.autenticacion import api
from apps.api.respuestas import ErrorAPI, exito, fallo_formulario, leer_json, paginar
from apps.core.utiles import mensaje_de
from apps.crm.forms.crm import SolicitudSoporteForm
from apps.crm.selectors import crm as selectores_soporte
from apps.crm.services import crm as servicios_soporte
from apps.notificaciones.models import Notificacion
from apps.notificaciones.selectors import notificaciones as selectores_notificaciones
from apps.notificaciones.services import notificaciones as servicios_notificaciones


@api(("GET",))
def notificaciones(request):
    solo_no_leidas = request.GET.get("no_leidas") in ("1", "true", "True")
    consulta = selectores_notificaciones.de_usuario(request.usuario, solo_no_leidas=solo_no_leidas)
    return exito(paginar(request, consulta, ser.notificacion))


@api(("GET",))
def notificaciones_contador(request):
    return exito({"no_leidas": selectores_notificaciones.contar_no_leidas(request.usuario)})


@api(("POST",))
def notificacion_leer(request, pk):
    if not Notificacion.objects.filter(pk=pk, usuario=request.usuario).exists():
        raise Http404
    servicios_notificaciones.marcar_leida(request.usuario, pk)
    return exito({"no_leidas": selectores_notificaciones.contar_no_leidas(request.usuario)})


@api(("POST",))
def notificaciones_leer_todas(request):
    servicios_notificaciones.marcar_todas(request.usuario)
    return exito({"no_leidas": 0})


@api(("GET", "POST"))
def soporte(request):
    if request.method == "GET":
        return exito(paginar(request, selectores_soporte.solicitudes_del_cliente(request.cliente), ser.soporte))
    formulario = SolicitudSoporteForm(
        {clave: ("" if valor is None else str(valor)) for clave, valor in leer_json(request).items()}
    )
    if not formulario.is_valid():
        return fallo_formulario(formulario)
    try:
        solicitud = servicios_soporte.crear_solicitud(request.cliente, **formulario.cleaned_data)
    except (servicios_soporte.ErrorCRM, ValidationError) as error:
        raise ErrorAPI(mensaje_de(error), "solicitud_invalida", 400)
    return exito(ser.soporte(solicitud), 201)


def _solicitud(cliente, pk):
    solicitud = selectores_soporte.obtener_solicitud_del_cliente(cliente, pk)
    if solicitud is None:
        raise Http404
    return solicitud


@api(("GET",))
def soporte_detalle(request, pk):
    return exito(ser.soporte(_solicitud(request.cliente, pk)))


@api(("POST",))
def soporte_cerrar(request, pk):
    solicitud = _solicitud(request.cliente, pk)
    try:
        servicios_soporte.cerrar_por_cliente(solicitud.pk, request.usuario)
    except servicios_soporte.ErrorCRM as error:
        raise ErrorAPI(str(error), "transicion_invalida", 409)
    return exito(ser.soporte(_solicitud(request.cliente, pk)))
__FIN__
}

paso_urls() {
    info "Rutas de la API y referencia"
    ir_a "apps/api"
    escribir "urls.py" <<'__FIN__'
from django.urls import path

from apps.api.vistas import auth, catalogo, compras, cotizaciones, cuenta, pedidos, seguimiento

app_name = "api"

urlpatterns = [
    path("salud/", cuenta.salud, name="salud"),
    path("negocio/", cuenta.negocio, name="negocio"),
    path("auth/registro/", auth.registro_cuenta, name="registro"),
    path("auth/reenviar-confirmacion/", auth.reenviar_confirmacion, name="reenviar_confirmacion"),
    path("auth/login/", auth.login, name="login"),
    path("auth/refrescar/", auth.refrescar, name="refrescar"),
    path("auth/logout/", auth.cerrar_sesion, name="logout"),
    path("auth/recuperar/", auth.recuperar_password, name="recuperar"),
    path("auth/cambiar-password/", auth.cambiar_password, name="cambiar_password"),
    path("perfil/", cuenta.perfil, name="perfil"),
    path("panel/", cuenta.panel, name="panel"),
    path("catalogo/categorias/", catalogo.categorias, name="categorias"),
    path("catalogo/productos/", catalogo.productos, name="productos"),
    path("catalogo/productos/<int:pk>/", catalogo.producto_detalle, name="producto"),
    path("catalogo/servicios/", catalogo.servicios, name="servicios"),
    path("catalogo/servicios/<int:pk>/", catalogo.servicio_detalle, name="servicio"),
    path("carrito/validar/", compras.validar_carrito, name="carrito_validar"),
    path("compras/", compras.comprar, name="comprar"),
    path("cotizaciones/", cotizaciones.cotizaciones, name="cotizaciones"),
    path("cotizaciones/<int:pk>/", cotizaciones.cotizacion_detalle, name="cotizacion"),
    path("cotizaciones/<int:pk>/archivos/<int:archivo_id>/", cotizaciones.cotizacion_archivo, name="cotizacion_archivo"),
    path("cotizaciones/<int:pk>/<slug:accion>/", cotizaciones.cotizacion_accion, name="cotizacion_accion"),
    path("pedidos/", pedidos.pedidos, name="pedidos"),
    path("pedidos/<int:pk>/", pedidos.pedido_detalle, name="pedido"),
    path("pedidos/<int:pk>/cancelar/", pedidos.pedido_cancelar, name="pedido_cancelar"),
    path("pedidos/<int:pk>/archivos/<int:archivo_id>/", pedidos.pedido_archivo, name="pedido_archivo"),
    path("facturas/", pedidos.facturas, name="facturas"),
    path("facturas/<int:pk>/", pedidos.factura_detalle, name="factura"),
    path("notificaciones/", seguimiento.notificaciones, name="notificaciones"),
    path("notificaciones/contador/", seguimiento.notificaciones_contador, name="notificaciones_contador"),
    path("notificaciones/leer-todas/", seguimiento.notificaciones_leer_todas, name="notificaciones_leer_todas"),
    path("notificaciones/<int:pk>/leer/", seguimiento.notificacion_leer, name="notificacion_leer"),
    path("soporte/", seguimiento.soporte, name="soporte"),
    path("soporte/<int:pk>/", seguimiento.soporte_detalle, name="soporte_detalle"),
    path("soporte/<int:pk>/cerrar/", seguimiento.soporte_cerrar, name="soporte_cerrar"),
]
__FIN__

    ir_a "docs"
    escribir "API_CLIENTES.md" <<'__FIN__'
# API de clientes (app móvil)

Base: `http(s)://<host>:8000/api/` · JSON UTF-8 · fechas ISO-8601 con zona (America/El_Salvador) ·
dinero como **texto** con 2 decimales (`"12.50"`) · rutas con barra final.

**Autenticación:** `POST auth/login/` devuelve `token`; enviar `Authorization: Bearer <token>`.
El token es una sesión de Django de canal `api` (30 días, `API_TOKEN_DIAS`). `auth/refrescar/` lo renueva.

**Errores:** `{"error": {"codigo": "...", "mensaje": "...", "campos": {"campo": ["msg"]}}}`
con estado 400 (datos), 401 (sin sesión/credenciales), 403 (sin permiso/correo sin confirmar),
404, 409 (transición inválida o duplicado), 413/415, 429 (límite/bloqueo) o 500.

**Paginación:** `?pagina=1&por_pagina=20` → `{"resultados":[...],"total":N,"pagina":1,"paginas":P,"hay_mas":bool}`.

| Método y ruta | Sesión | Descripción |
|---|---|---|
| GET `salud/` | no | Comprobar conexión |
| GET `negocio/` | no | Datos del negocio (contacto, logo) |
| POST `auth/registro/` | no | `{nombres, apellidos, correo, telefono?, password, password2?}` → 201; envía correo de confirmación |
| POST `auth/reenviar-confirmacion/` | no | `{correo}` |
| POST `auth/login/` | no | `{correo, password}` → `{token, expira_en, usuario, cliente}` |
| POST `auth/refrescar/` · `auth/logout/` | sí | Renueva/cierra el token |
| POST `auth/recuperar/` | no | `{correo}` → correo con enlace web de restablecimiento |
| POST `auth/cambiar-password/` | sí | `{password_actual, password_nueva}` |
| GET/PUT/PATCH `perfil/` | sí | Ver/editar datos del cliente |
| GET `panel/` | sí | Indicadores y listas cortas |
| GET `catalogo/categorias/` · `catalogo/productos/?q=` · `catalogo/productos/<id>/` · `catalogo/servicios/?categoria=` · `catalogo/servicios/<id>/` | no | Catálogo público |
| POST `carrito/validar/` | sí | `{items:[{producto_id, cantidad}]}` → líneas, totales y problemas |
| POST `compras/` | sí | `{items, token}` (token único por compra, 8–64 caracteres; repetirlo es seguro) → 201 `{duplicado, pedido}` |
| GET/POST `cotizaciones/` | sí | Lista · crear (**multipart**: `servicio, cantidad, descripcion, solicitud, material?, color?, dimensiones?, archivos[]`; o JSON sin archivos) |
| GET `cotizaciones/<id>/` | sí | Detalle con `puede_responder`, `puede_cancelar`, `vencida`, archivos y pedido |
| POST `cotizaciones/<id>/aceptar|rechazar|cancelar/` | sí | Acciones (409 si el estado no lo permite) |
| GET `cotizaciones/<id>/archivos/<aid>/` | sí | Descarga (requiere Bearer) |
| GET `pedidos/` · `pedidos/<id>/` · POST `pedidos/<id>/cancelar/` · GET `pedidos/<id>/archivos/<aid>/` | sí | Pedidos (solo `PENDIENTE` se cancela) |
| GET `facturas/` · `facturas/<id>/` | sí | Facturas con pagos confirmados |
| GET `notificaciones/?no_leidas=1` · `notificaciones/contador/` · POST `notificaciones/<id>/leer/` · `notificaciones/leer-todas/` | sí | Avisos |
| GET/POST `soporte/` · GET `soporte/<id>/` · POST `soporte/<id>/cerrar/` | sí | Soporte (`{asunto, descripcion, prioridad: BAJA\|MEDIA\|ALTA}`) |

Archivos: formatos STL, OBJ, 3MF, STEP/STP, PNG, JPG, PDF; máx. 5 por solicitud y 50 MB c/u (validados por contenido).
__FIN__
}

# ============================================================
# PRUEBAS
# ============================================================

paso_pruebas() {
    info "Pruebas de la API"
    ir_a "apps/api/tests"
    vacio_si_falta "__init__.py"

    crear_si_falta "base.py" <<'__FIN__'
import json

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from apps.usuarios.tests.utiles import CLAVE


class ApiTestCase(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def cabecera(self, token):
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}

    def token_de(self, correo, clave=CLAVE):
        respuesta = self.client.post(
            reverse("api:login"), json.dumps({"correo": correo, "password": clave}), content_type="application/json"
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        return respuesta.json()["token"]

    def get(self, nombre, token=None, args=(), params=None):
        return self.client.get(reverse(f"api:{nombre}", args=args), params or {}, **self.cabecera(token))

    def enviar(self, metodo, nombre, token=None, args=(), datos=None):
        return getattr(self.client, metodo)(
            reverse(f"api:{nombre}", args=args),
            json.dumps({} if datos is None else datos),
            content_type="application/json",
            **self.cabecera(token),
        )

    def post(self, nombre, token=None, args=(), datos=None):
        return self.enviar("post", nombre, token, args, datos)
__FIN__

    crear_si_falta "test_auth.py" <<'__FIN__'
import json

from django.core import mail
from django.test import Client, override_settings
from django.urls import reverse

from allauth.account.models import EmailAddress

from apps.api.tests.base import ApiTestCase
from apps.clientes.models import Cliente
from apps.cotizaciones.tests.utiles import crear_cliente, crear_personal
from apps.usuarios.constants import ESTADO_PENDIENTE, GRUPO_CLIENTE
from apps.usuarios.models import Usuario
from apps.usuarios.tests.utiles import BACKEND, CLAVE, crear_usuario

DATOS = {
    "nombres": "Luis",
    "apellidos": "Pérez",
    "correo": "luis.api@example.com",
    "telefono": "+503 7000-1111",
    "password": "Clave-Segura-123",
    "password2": "Clave-Segura-123",
}


class AutenticacionApiTests(ApiTestCase):
    def test_salud_es_publica(self):
        respuesta = self.get("salud")
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.json()["ok"])

    def test_login_correcto_devuelve_token_y_cliente(self):
        crear_cliente("ana@example.com")
        respuesta = self.client.post(
            reverse("api:login"), json.dumps({"correo": "ANA@example.com", "password": CLAVE}), content_type="application/json"
        )
        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo["tipo"], "Bearer")
        self.assertEqual(cuerpo["cliente"]["correo"], "ana@example.com")
        self.assertEqual(self.get("perfil", cuerpo["token"]).status_code, 200)

    def test_credenciales_incorrectas(self):
        crear_cliente("ana@example.com")
        respuesta = self.client.post(
            reverse("api:login"), json.dumps({"correo": "ana@example.com", "password": "otra-clave-1"}), content_type="application/json"
        )
        self.assertEqual(respuesta.status_code, 401)
        self.assertEqual(respuesta.json()["error"]["codigo"], "credenciales_invalidas")

    def test_endpoint_protegido_sin_token_o_con_token_invalido(self):
        self.assertEqual(self.get("perfil").status_code, 401)
        self.assertEqual(self.get("perfil", "a" * 32).status_code, 401)
        self.assertEqual(self.get("perfil", "no-es-un-token!").status_code, 401)

    def test_el_personal_no_entra_a_la_app_de_clientes(self):
        crear_personal("operador@example.com")
        respuesta = self.client.post(
            reverse("api:login"), json.dumps({"correo": "operador@example.com", "password": CLAVE}), content_type="application/json"
        )
        self.assertEqual(respuesta.status_code, 403)

    def test_cuenta_pendiente_no_entra(self):
        crear_usuario("pendiente@example.com", GRUPO_CLIENTE, estado_id=ESTADO_PENDIENTE)
        respuesta = self.client.post(
            reverse("api:login"), json.dumps({"correo": "pendiente@example.com", "password": CLAVE}), content_type="application/json"
        )
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.json()["error"]["codigo"], "correo_no_confirmado")

    def test_tipo_de_contenido_incorrecto(self):
        respuesta = self.client.post(reverse("api:login"), {"correo": "a@b.com", "password": "x"})
        self.assertEqual(respuesta.status_code, 415)

    def test_logout_invalida_el_token(self):
        crear_cliente("ana@example.com")
        token = self.token_de("ana@example.com")
        self.assertEqual(self.post("logout", token).status_code, 200)
        self.assertEqual(self.get("perfil", token).status_code, 401)

    def test_refrescar_entrega_otro_token_y_cierra_el_anterior(self):
        crear_cliente("ana@example.com")
        viejo = self.token_de("ana@example.com")
        nuevo = self.post("refrescar", viejo).json()["token"]
        self.assertNotEqual(viejo, nuevo)
        self.assertEqual(self.get("perfil", viejo).status_code, 401)
        self.assertEqual(self.get("perfil", nuevo).status_code, 200)

    def test_cambiar_password_cierra_las_otras_sesiones_y_conserva_la_actual(self):
        crear_cliente("ana@example.com")
        actual, otro = self.token_de("ana@example.com"), self.token_de("ana@example.com")
        erronea = self.post("cambiar_password", actual, datos={"password_actual": "mala", "password_nueva": "Nueva-Clave-456"})
        self.assertEqual(erronea.status_code, 400)
        debil = self.post("cambiar_password", actual, datos={"password_actual": CLAVE, "password_nueva": "123"})
        self.assertEqual(debil.status_code, 400)
        ok = self.post("cambiar_password", actual, datos={"password_actual": CLAVE, "password_nueva": "Nueva-Clave-456"})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(self.get("perfil", actual).status_code, 200)
        self.assertEqual(self.get("perfil", otro).status_code, 401)
        self.assertTrue(self.token_de("ana@example.com", "Nueva-Clave-456"))

    def test_iniciar_sesion_en_la_web_no_cierra_el_token_de_la_app(self):
        usuario, _ = crear_cliente("web@example.com")
        token = self.token_de("web@example.com")
        Client().force_login(usuario, backend=BACKEND)
        self.assertEqual(self.get("perfil", token).status_code, 200)

    def test_sesion_unica_de_la_app_es_configurable(self):
        crear_cliente("ana@example.com")
        with override_settings(API_SESION_UNICA=True):
            primero = self.token_de("ana@example.com")
            segundo = self.token_de("ana@example.com")
        self.assertEqual(self.get("perfil", primero).status_code, 401)
        self.assertEqual(self.get("perfil", segundo).status_code, 200)

    def test_bloqueo_por_intentos_fallidos(self):
        crear_cliente("lock@example.com")
        estados = [
            self.client.post(
                reverse("api:login"), json.dumps({"correo": "lock@example.com", "password": "mala-clave-1"}), content_type="application/json"
            ).status_code
            for _ in range(6)
        ]
        self.assertEqual(estados[0], 401)
        self.assertEqual(estados[-1], 429)
        correcta = self.client.post(
            reverse("api:login"), json.dumps({"correo": "lock@example.com", "password": CLAVE}), content_type="application/json"
        )
        self.assertEqual(correcta.status_code, 429)


class RegistroApiTests(ApiTestCase):
    def registrar(self, **cambios):
        return self.client.post(reverse("api:registro"), json.dumps({**DATOS, **cambios}), content_type="application/json")

    def test_registro_crea_cuenta_pendiente_con_perfil_y_correo(self):
        respuesta = self.registrar()
        self.assertEqual(respuesta.status_code, 201)
        usuario = Usuario.objects.get(correo=DATOS["correo"])
        self.assertEqual(usuario.estado_id, ESTADO_PENDIENTE)
        self.assertTrue(usuario.groups.filter(name=GRUPO_CLIENTE).exists())
        self.assertEqual(Cliente.objects.filter(usuario=usuario).count(), 1)
        self.assertTrue(EmailAddress.objects.filter(user=usuario, verified=False).exists())
        self.assertEqual(len(mail.outbox), 1)

    def test_correo_repetido_no_duplica_ni_revela_nada(self):
        self.registrar()
        respuesta = self.registrar()
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(Usuario.objects.filter(correo=DATOS["correo"]).count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_validaciones_del_registro(self):
        malos = self.registrar(nombres="Luis123", password="123", correo="no-es-correo")
        self.assertEqual(malos.status_code, 400)
        campos = malos.json()["error"]["campos"]
        self.assertIn("nombres", campos)
        self.assertIn("correo", campos)
        debil = self.registrar(password="123", password2="123")
        self.assertEqual(debil.status_code, 400)
        self.assertIn("password", debil.json()["error"]["campos"])
        distintas = self.registrar(password2="otra-distinta")
        self.assertIn("password2", distintas.json()["error"]["campos"])

    def test_registro_y_recuperacion_tienen_limite_por_ip(self):
        for indice in range(10):
            self.registrar(correo=f"u{indice}.api@example.com")
        self.assertEqual(self.registrar(correo="exceso.api@example.com").status_code, 429)

    def test_recuperar_password_siempre_responde_igual(self):
        crear_cliente("ana@example.com")
        existente = self.client.post(reverse("api:recuperar"), json.dumps({"correo": "ana@example.com"}), content_type="application/json")
        inexistente = self.client.post(reverse("api:recuperar"), json.dumps({"correo": "nadie@example.com"}), content_type="application/json")
        self.assertEqual((existente.status_code, inexistente.status_code), (200, 200))
        self.assertEqual(existente.json(), inexistente.json())
__FIN__

    crear_si_falta "test_cuenta_y_catalogo.py" <<'__FIN__'
from decimal import Decimal

from apps.api.tests.base import ApiTestCase
from apps.catalogo.models import CategoriaServicio, Producto
from apps.cotizaciones.tests.utiles import crear_cliente, crear_servicio


class CatalogoApiTests(ApiTestCase):
    def test_catalogo_publico_solo_muestra_lo_activo(self):
        Producto.objects.create(sku="CAT-001", nombre="Visible", precio=Decimal("9.99"), stock=5, stock_minimo=1)
        Producto.objects.create(sku="CAT-002", nombre="Agotado", precio=Decimal("5.00"), stock=0)
        Producto.objects.create(sku="CAT-003", nombre="Oculto", precio=Decimal("5.00"), stock=5, activo=False)
        resultados = self.get("productos").json()["resultados"]
        self.assertEqual([p["nombre"] for p in resultados], ["Agotado", "Visible"])
        self.assertEqual({p["nombre"]: p["disponibilidad"] for p in resultados}, {"Visible": "disponible", "Agotado": "agotado"})
        self.assertEqual(resultados[1]["precio"], "9.99")
        oculto = Producto.objects.get(sku="CAT-003")
        self.assertEqual(self.get("producto", args=(oculto.pk,)).status_code, 404)
        self.assertEqual(len(self.get("productos", params={"q": "visi"}).json()["resultados"]), 1)

    def test_servicios_y_categorias_publicos(self):
        servicio = crear_servicio("Impresión API", requiere_archivo=True)
        crear_servicio("Servicio oculto", activo=False)
        resultados = self.get("servicios").json()["resultados"]
        self.assertEqual([s["nombre"] for s in resultados], ["Impresión API"])
        self.assertTrue(resultados[0]["requiere_archivo"])
        self.assertEqual(self.get("servicio", args=(servicio.pk,)).status_code, 200)
        self.assertEqual(self.get("servicios", params={"categoria": "x"}).status_code, 400)
        self.assertEqual(len(self.get("categorias").json()["resultados"]), CategoriaServicio.objects.filter(activo=True).count())

    def test_negocio_responde_aunque_no_haya_configuracion(self):
        self.assertEqual(self.get("negocio").status_code, 200)


class CuentaApiTests(ApiTestCase):
    def test_perfil_ver_y_editar_con_las_reglas_de_la_web(self):
        usuario, cliente = crear_cliente("ana@example.com")
        token = self.token_de("ana@example.com")
        self.assertEqual(self.get("perfil", token).json()["tipo_cliente"], "PERSONA")
        malo = self.enviar("patch", "perfil", token, datos={"tipo_cliente": "EMPRESA", "telefono": "abc"})
        self.assertEqual(malo.status_code, 400)
        campos = malo.json()["error"]["campos"]
        self.assertIn("nombre_empresa", campos)
        self.assertIn("telefono", campos)
        bueno = self.enviar("put", "perfil", token, datos={"tipo_cliente": "PERSONA", "nombres": "Ana María", "apellidos": "Gómez", "telefono": "+503 7000-2222"})
        self.assertEqual(bueno.status_code, 200)
        usuario.refresh_from_db()
        self.assertEqual((usuario.nombres, usuario.telefono), ("Ana María", "+503 7000-2222"))

    def test_panel_con_indicadores(self):
        crear_cliente("ana@example.com")
        token = self.token_de("ana@example.com")
        cuerpo = self.get("panel", token).json()
        self.assertEqual(cuerpo["kpis"]["pedidos_en_curso"], 0)
        self.assertEqual(cuerpo["kpis"]["saldo_pendiente"], "0.00")
        self.assertEqual(cuerpo["cotizaciones"], [])
__FIN__

    crear_si_falta "test_documentos.py" <<'__FIN__'
import json
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.api.tests.base import ApiTestCase
from apps.catalogo.models import Producto
from apps.cotizaciones.models import Cotizacion
from apps.cotizaciones.services import cotizaciones as servicios_cot
from apps.cotizaciones.tests.utiles import AlmacenTemporalMixin, archivo_stl, crear_cliente, crear_personal, crear_servicio
from apps.facturacion.models import Factura
from apps.pagos.models import EstadoPago, MetodoPago, Pago


class CotizacionesApiTests(AlmacenTemporalMixin, ApiTestCase):
    def setUp(self):
        super().setUp()
        self.usuario, self.cliente = crear_cliente("ana@example.com")
        self.otro, _ = crear_cliente("otro@example.com")
        self.token = self.token_de("ana@example.com")
        self.token_otro = self.token_de("otro@example.com")

    def solicitar(self, servicio, archivos=(), **extra):
        datos = {"servicio": servicio.pk, "cantidad": "2", "descripcion": "Pieza", "solicitud": "Necesito una pieza de prueba."}
        datos.update(extra)
        if archivos:
            datos["archivos"] = list(archivos)
        return self.client.post(reverse("api:cotizaciones"), datos, **self.cabecera(self.token))

    def test_solicitud_multipart_con_archivo_valido(self):
        servicio = crear_servicio(requiere_archivo=True)
        respuesta = self.solicitar(servicio, [archivo_stl()], material="PLA")
        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        cuerpo = respuesta.json()
        self.assertTrue(cuerpo["codigo"].startswith("COT-"))
        self.assertEqual(cuerpo["estado"], "SOLICITADA")
        self.assertTrue(cuerpo["puede_cancelar"])
        self.assertEqual(cuerpo["lineas"][0]["especificaciones"], {"material": "PLA"})
        self.assertEqual(len(cuerpo["archivos"]), 1)
        self.assertNotIn("ruta_archivo", cuerpo["archivos"][0])

    def test_archivos_invalidos_o_faltantes_se_rechazan(self):
        servicio = crear_servicio(requiere_archivo=True)
        falso = SimpleUploadedFile("malo.stl", b"MZ\x90\x00binario", content_type="application/octet-stream")
        self.assertIn("archivos", self.solicitar(servicio, [falso]).json()["error"]["campos"])
        self.assertIn("archivos", self.solicitar(servicio).json()["error"]["campos"])
        self.assertEqual(Cotizacion.objects.count(), 0)

    def test_solicitud_json_sin_archivos_para_servicios_que_no_lo_requieren(self):
        servicio = crear_servicio()
        respuesta = self.post(
            "cotizaciones", self.token,
            datos={"servicio": servicio.pk, "cantidad": 3, "descripcion": "Prototipo", "solicitud": "Prototipo de prueba largo.", "especificaciones": {"color": "Rojo"}},
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        self.assertEqual(respuesta.json()["lineas"][0]["especificaciones"], {"color": "Rojo"})
        malo = self.post("cotizaciones", self.token, datos={"servicio": servicio.pk, "cantidad": 0, "descripcion": "", "solicitud": "corta"})
        self.assertEqual(malo.status_code, 400)

    def test_flujo_completo_aceptar_y_aislamiento_entre_clientes(self):
        servicio = crear_servicio()
        cotizacion_id = self.solicitar(servicio).json()["id"]
        self.assertEqual(self.get("cotizacion", self.token_otro, args=(cotizacion_id,)).status_code, 404)
        self.assertEqual(self.post("cotizacion_accion", self.token_otro, args=(cotizacion_id, "cancelar")).status_code, 404)
        self.assertEqual(self.post("cotizacion_accion", self.token, args=(cotizacion_id, "aceptar")).status_code, 409)

        operador = crear_personal("operador@example.com")
        cotizacion = Cotizacion.objects.get(pk=cotizacion_id)
        lineas = [{"id": d.pk, "cantidad": Decimal("2"), "precio_unitario": Decimal("15.00"), "descuento": Decimal("0")} for d in cotizacion.detalles.all()]
        servicios_cot.revisar_cotizacion(cotizacion.pk, operador, lineas)
        servicios_cot.enviar_cotizacion(cotizacion.pk, operador)

        detalle = self.get("cotizacion", self.token, args=(cotizacion_id,)).json()
        self.assertTrue(detalle["puede_responder"])
        aceptada = self.post("cotizacion_accion", self.token, args=(cotizacion_id, "aceptar"))
        self.assertEqual((aceptada.status_code, aceptada.json()["estado"]), (200, "ACEPTADA"))
        self.assertEqual(self.post("cotizacion_accion", self.token, args=(cotizacion_id, "rechazar")).status_code, 409)
        self.assertEqual(self.post("cotizacion_accion", self.token, args=(cotizacion_id, "inventada")).status_code, 404)

    def test_cancelar_solicitud_sin_revisar(self):
        cotizacion_id = self.solicitar(crear_servicio()).json()["id"]
        respuesta = self.post("cotizacion_accion", self.token, args=(cotizacion_id, "cancelar"))
        self.assertEqual(respuesta.json()["estado"], "CANCELADA")

    def test_descarga_de_archivos_solo_para_su_dueno(self):
        servicio = crear_servicio(requiere_archivo=True)
        cuerpo = self.solicitar(servicio, [archivo_stl()]).json()
        argumentos = (cuerpo["id"], cuerpo["archivos"][0]["id"])
        respuesta = self.get("cotizacion_archivo", self.token, args=argumentos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn(b"solid pieza", b"".join(respuesta.streaming_content))
        self.assertEqual(self.get("cotizacion_archivo", self.token_otro, args=argumentos).status_code, 404)
        self.assertEqual(self.get("cotizacion_archivo", None, args=argumentos).status_code, 401)

    def test_listado_paginado(self):
        servicio = crear_servicio()
        for _ in range(3):
            self.solicitar(servicio)
        pagina = self.get("cotizaciones", self.token, params={"por_pagina": 2}).json()
        self.assertEqual((len(pagina["resultados"]), pagina["total"], pagina["hay_mas"]), (2, 3, True))
        self.assertEqual(self.get("cotizaciones", self.token, params={"por_pagina": "x"}).status_code, 400)


class ComprasYPedidosApiTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.usuario, self.cliente = crear_cliente("ana@example.com")
        self.otro, _ = crear_cliente("otro@example.com")
        self.token = self.token_de("ana@example.com")
        self.token_otro = self.token_de("otro@example.com")
        self.producto = Producto.objects.create(sku="API-001", nombre="Producto API", precio=Decimal("10.00"), stock=5, stock_minimo=1)

    def items(self, cantidad):
        return [{"producto_id": self.producto.pk, "cantidad": cantidad}]

    def test_validar_carrito_calcula_totales_y_detecta_problemas(self):
        bueno = self.post("carrito_validar", self.token, datos={"items": self.items(2)}).json()
        self.assertFalse(bueno["hay_problemas"])
        self.assertEqual(bueno["totales"], {"subtotal": "20.00", "descuento": "0.00", "impuesto": "2.60", "total": "22.60"})
        malo = self.post("carrito_validar", self.token, datos={"items": self.items(9)}).json()
        self.assertTrue(malo["hay_problemas"])
        self.assertEqual(self.post("carrito_validar", self.token, datos={"items": []}).status_code, 400)
        self.assertEqual(self.post("carrito_validar", self.token, datos={"items": [{"producto_id": "x", "cantidad": 1}]}).status_code, 400)
        self.assertEqual(self.post("carrito_validar", self.token, datos={"items": self.items(100)}).status_code, 400)

    def test_compra_descuenta_stock_y_es_idempotente(self):
        respuesta = self.post("comprar", self.token, datos={"items": self.items(2), "token": "token-compra-0001"})
        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        pedido = respuesta.json()["pedido"]
        self.assertEqual((pedido["estado"], pedido["total"]), ("PENDIENTE", "22.60"))
        self.assertTrue(pedido["codigo"].startswith("ENC-"))
        self.assertEqual(pedido["historial"][0]["comentario"], "Compra confirmada desde la tienda.")
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 3)
        repetida = self.post("comprar", self.token, datos={"items": self.items(2), "token": "token-compra-0001"})
        self.assertEqual(repetida.status_code, 200)
        self.assertTrue(repetida.json()["duplicado"])
        self.assertEqual(repetida.json()["pedido"]["id"], pedido["id"])
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 3)

    def test_compra_sin_existencias_o_con_token_invalido(self):
        sin_stock = self.post("comprar", self.token, datos={"items": self.items(9), "token": "token-compra-0002"})
        self.assertEqual(sin_stock.status_code, 400)
        self.assertIn("Existencias insuficientes", sin_stock.json()["error"]["mensaje"])
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 5)
        self.assertEqual(self.post("comprar", self.token, datos={"items": self.items(1), "token": "x"}).status_code, 400)

    def test_cancelar_pedido_repone_stock_y_no_se_repite(self):
        pedido_id = self.post("comprar", self.token, datos={"items": self.items(2), "token": "token-compra-0003"}).json()["pedido"]["id"]
        self.assertEqual(self.post("pedido_cancelar", self.token_otro, args=(pedido_id,)).status_code, 404)
        cancelado = self.post("pedido_cancelar", self.token, args=(pedido_id,))
        self.assertEqual((cancelado.status_code, cancelado.json()["estado"]), (200, "CANCELADO"))
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 5)
        self.assertEqual(self.post("pedido_cancelar", self.token, args=(pedido_id,)).status_code, 409)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 5)

    def test_listado_y_detalle_de_pedidos_aislados(self):
        pedido_id = self.post("comprar", self.token, datos={"items": self.items(1), "token": "token-compra-0004"}).json()["pedido"]["id"]
        self.assertEqual([p["id"] for p in self.get("pedidos", self.token).json()["resultados"]], [pedido_id])
        self.assertEqual(self.get("pedidos", self.token_otro).json()["total"], 0)
        self.assertEqual(self.get("pedido", self.token_otro, args=(pedido_id,)).status_code, 404)
        detalle = self.get("pedido", self.token, args=(pedido_id,)).json()
        self.assertEqual(detalle["progreso"], 25)
        self.assertTrue(detalle["puede_cancelar"])
        self.assertEqual(len(detalle["lineas"]), 1)

    def test_facturas_solo_muestran_pagos_confirmados(self):
        factura = Factura.objects.create(
            cliente=self.cliente, numero_factura="FAC-API-1", nombre_facturacion="Cliente",
            subtotal=Decimal("50.00"), total=Decimal("50.00"), saldo_pendiente=Decimal("30.00"),
        )
        metodo, _ = MetodoPago.objects.get_or_create(nombre="Efectivo")
        Pago.objects.create(factura=factura, metodo_pago=metodo, monto=Decimal("20.00"), estado=EstadoPago.CONFIRMADO)
        Pago.objects.create(factura=factura, metodo_pago=metodo, monto=Decimal("5.00"), estado=EstadoPago.CANCELADO)
        self.assertEqual(self.get("facturas", self.token).json()["total"], 1)
        detalle = self.get("factura", self.token, args=(factura.pk,)).json()
        self.assertEqual([p["monto"] for p in detalle["pagos"]], ["20.00"])
        self.assertEqual(detalle["saldo_pendiente"], "30.00")
        self.assertEqual(self.get("factura", self.token_otro, args=(factura.pk,)).status_code, 404)
        self.assertEqual(self.get("facturas", self.token_otro).json()["total"], 0)
__FIN__

    crear_si_falta "test_seguimiento.py" <<'__FIN__'
from apps.api.tests.base import ApiTestCase
from apps.cotizaciones.tests.utiles import crear_cliente
from apps.notificaciones.models import Notificacion
from apps.notificaciones.services.notificaciones import notificar


class NotificacionesApiTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.usuario, _ = crear_cliente("ana@example.com")
        self.otro, _ = crear_cliente("otro@example.com")
        self.token = self.token_de("ana@example.com")
        self.token_otro = self.token_de("otro@example.com")

    def test_listado_contador_y_lectura(self):
        propia = notificar(self.usuario, "Aviso propio", "x", "cotizacion", 1)
        notificar(self.usuario, "Segundo aviso", "x", "encargo", 2)
        ajena = notificar(self.otro, "Aviso ajeno", "x", "cotizacion", 1)
        lista = self.get("notificaciones", self.token).json()
        self.assertEqual(sorted(n["titulo"] for n in lista["resultados"]), ["Aviso propio", "Segundo aviso"])
        self.assertEqual(self.get("notificaciones_contador", self.token).json()["no_leidas"], 2)
        self.assertEqual(self.post("notificacion_leer", self.token, args=(ajena.pk,)).status_code, 404)
        self.assertEqual(self.post("notificacion_leer", self.token, args=(propia.pk,)).json()["no_leidas"], 1)
        self.assertEqual(len(self.get("notificaciones", self.token, params={"no_leidas": "1"}).json()["resultados"]), 1)
        self.assertEqual(self.post("notificaciones_leer_todas", self.token).json()["no_leidas"], 0)
        self.assertFalse(Notificacion.objects.get(pk=ajena.pk).leida)


class SoporteApiTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        crear_cliente("ana@example.com")
        crear_cliente("otro@example.com")
        self.token = self.token_de("ana@example.com")
        self.token_otro = self.token_de("otro@example.com")

    def test_crear_listar_ver_y_cerrar(self):
        malo = self.post("soporte", self.token, datos={"asunto": "", "descripcion": "corta", "prioridad": "URGENTE"})
        self.assertEqual(malo.status_code, 400)
        self.assertIn("prioridad", malo.json()["error"]["campos"])
        creada = self.post("soporte", self.token, datos={"asunto": "Duda", "descripcion": "Necesito ayuda con mi pedido.", "prioridad": "ALTA"})
        self.assertEqual(creada.status_code, 201, creada.content)
        solicitud_id = creada.json()["id"]
        self.assertEqual(creada.json()["estado"], "ABIERTA")
        self.assertEqual(self.get("soporte", self.token).json()["total"], 1)
        self.assertEqual(self.get("soporte", self.token_otro).json()["total"], 0)
        self.assertEqual(self.get("soporte_detalle", self.token_otro, args=(solicitud_id,)).status_code, 404)
        self.assertEqual(self.post("soporte_cerrar", self.token_otro, args=(solicitud_id,)).status_code, 404)
        cerrada = self.post("soporte_cerrar", self.token, args=(solicitud_id,))
        self.assertEqual(cerrada.json()["estado"], "CERRADA")
        self.assertEqual(self.post("soporte_cerrar", self.token, args=(solicitud_id,)).status_code, 409)
__FIN__
}

paso_tasklist() {
    ir_raiz
    [[ -f TASKLIST_USUARIO.txt ]] || return 0
    inyectar_bloque "TASKLIST_USUARIO.txt" "api" <<'__FIN__'

=== P. API PARA LA APP MOVIL (generar-api.sh) ===
Documentacion de endpoints: docs/API_CLIENTES.md. No hay migraciones nuevas ni dependencias nuevas.
[ ] P1. python manage.py test   (envieme el resumen). Las pruebas de la web no deben cambiar.
[ ] P2. Web intacta: iniciar sesion, comprar, cotizar y cerrar sesion como siempre; el bloqueo
        por intentos fallidos de la web sigue mostrando la pagina "Acceso bloqueado".
[ ] P3. Arranque para el celular (Tailscale):
          a) En la PC: tailscale ip -4   (anote la IP 100.x.y.z) y el nombre en la consola de Tailscale.
          b) .env:  DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,100.x.y.z   (los nombres *.ts.net ya se aceptan)
          c) python manage.py runserver 0.0.0.0:8000
          d) Desde el navegador del celular con Tailscale encendido: http://<nombre-o-IP>:8000/api/salud/
             debe responder {"ok": true, ...}.
[ ] P4. Con curl (cambie HOST):
          curl -s http://HOST:8000/api/salud/
          curl -s -X POST http://HOST:8000/api/auth/login/ -H "Content-Type: application/json" \
               -d '{"correo":"cliente@example.com","password":"SU-CLAVE"}'
          curl -s http://HOST:8000/api/panel/ -H "Authorization: Bearer TOKEN"
[ ] P5. Registro por API: POST auth/registro/ -> 201; el correo de confirmacion aparece en la consola de
        runserver (EMAIL por consola); abrir el enlace en el navegador y despues iniciar sesion por API.
        Antes de confirmar, el login debe responder 403 correo_no_confirmado.
[ ] P6. Cotizacion con archivo real: curl -X POST .../api/cotizaciones/ -H "Authorization: Bearer TOKEN"
        -F servicio=1 -F cantidad=2 -F descripcion=Pieza -F "solicitud=Necesito una pieza de prueba" -F archivos=@pieza.stl
        -> 201 con codigo COT-...; el operador la ve en la web con su archivo; subir un .exe renombrado a .stl -> 400.
[ ] P7. Compra: POST carrito/validar/ y POST compras/ con {"items":[{"producto_id":1,"cantidad":2}],"token":"una-clave-unica-123"};
        repetir la misma peticion -> 200 duplicado=true y el stock no vuelve a bajar.
[ ] P8. Aislamiento: con el token del cliente B, pedir ids de cotizaciones/pedidos/facturas del cliente A -> 404.
[ ] P9. Cerrar la sesion web del mismo usuario NO debe cerrar el token del celular (sesion unica por canal).
        Para forzar un solo celular por cuenta: API_SESION_UNICA=True en .env.
[ ] P10. Pendiente conocido: la idempotencia de compras usa cache local (un solo proceso); el token del celular vence a los 30 dias.
__FIN__
}

paso_verificacion() {
    ir_raiz
    local py="python3"
    if [[ -x "$RAIZ/.venv/bin/python" ]]; then
        py="$RAIZ/.venv/bin/python"
    elif [[ -x "$RAIZ/.venv/Scripts/python.exe" ]]; then
        py="$RAIZ/.venv/Scripts/python.exe"
    elif [[ -n ${VIRTUAL_ENV:-} && -x "$VIRTUAL_ENV/bin/python" ]]; then
        py="$VIRTUAL_ENV/bin/python"
    fi
    info "Verificando sintaxis"
    if "$py" -m compileall -q apps config >/dev/null; then
        ok "Sintaxis correcta"
    else
        advertir "Errores de sintaxis: $py -m compileall apps config"
        return 0
    fi
    [[ -f .env ]] || return 0
    if "$py" -c "import django" >/dev/null 2>&1; then
        "$py" manage.py check >/dev/null 2>&1 && ok "manage.py check sin problemas" \
            || advertir "manage.py check reporto problemas; ejecutelo para ver el detalle."
        "$py" manage.py makemigrations --check --dry-run >/dev/null 2>&1 && ok "Sin cambios de esquema pendientes" \
            || advertir "makemigrations --check detecta diferencias; ejecute: python manage.py makemigrations --dry-run"
    fi
}

resumen() {
    echo
    echo "============================================================"
    echo " RESUMEN"
    echo "============================================================"
    echo "Raiz:               $RAIZ"
    echo "Archivos creados:   $CREADOS"
    echo "Actualizados:       $ACTUALIZADOS"
    echo "Sin cambios:        $SIN_CAMBIOS"
    echo "Omitidos/propuestas: $OMITIDOS"
    [[ -n $RESPALDO ]] && echo "Respaldos en:       $RESPALDO"
    if ((${#PROPUESTAS[@]})); then
        echo
        echo "Archivos que usted ya habia editado (version nueva en <archivo>.propuesta):"
        printf '  - %s\n' "${PROPUESTAS[@]}"
    fi
    if ((${#AVISOS[@]})); then
        echo
        echo "Avisos:"
        printf '  - %s\n' "${AVISOS[@]}"
    fi
    echo
    echo "Siguiente: python manage.py test, y la seccion P de TASKLIST_USUARIO.txt (prueba por Tailscale)."
    echo "Servidor para el celular: python manage.py runserver 0.0.0.0:8000"
    echo "============================================================"
}

main() {
    local arg
    for arg in "$@"; do
        case "$arg" in
            -h | --ayuda) ayuda; exit 0 ;;
            -*) fallar "Opcion desconocida: $arg" ;;
            *) RAIZ="$arg" ;;
        esac
    done
    resolver_raiz "$RAIZ"
    verificar_base
    info "Raiz del proyecto: $RAIZ"
    ir_raiz

    paso_configuracion
    paso_nucleo
    paso_serializadores
    paso_vistas_cuenta
    paso_vistas_documentos
    paso_urls
    paso_pruebas
    paso_tasklist
    paso_verificacion
    resumen
}

main "$@"
