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
Uso: generar-ui1.sh [opciones] [RAIZ_DEL_PROYECTO]

  -h, --ayuda    muestra esta ayuda

UI-1: sistema de diseno (Material 3 sobre Bootstrap):
  - static/css/app.css con Roboto, paleta clara y oscura y estilos M3 para todos los
    componentes Bootstrap (botones, campos, tarjetas, tablas, menus, paginacion...).
  - Iconos Material Symbols en los layouts y alternador de tema claro/oscuro en cada
    pantalla (guest, auth y paneles) con el unico script en linea permitido (cabecera).
  - Barra superior unificada: rutas al centro, notificaciones + tema + menu de usuario
    (perfil y cerrar sesion) a la derecha, ruta activa con el color de marca.
  - Toasts con icono y 4 tipos (exito, error, advertencia amarilla, informacion azul).
  - Pantallas de acceso con una sola pestaña visible (ingresar / crear cuenta), tambien
    cuando falla la autenticacion; paginas de allauth dentro del mismo diseno.
  - Pagina de terminos y condiciones, pie de pagina y paginas de error.
Las pantallas de negocio heredan el estilo por CSS; las tarjetas de producto, tablas con
botones de accion, formularios de encargos y perfil se rehacen en el script UI-2.
No cambia el esquema ni la logica de negocio.
__FIN__
}

PROPUESTAS=()

declare -A HASHES_STUB=(
    [static/css/app.css]=b6ee797968ed6a5dcdee523b6bb86b573ae3304d80a44973230d1761dd097df3
    [templates/layouts/base.html]=fd919651f4165d7f209c515abb81516861903ec77fc711681693535e7a4260e7
    [templates/layouts/guest.html]=38148763bb32d2dfc91e118f59ec93abefdb4537ec784688bfc7f17b9da1402e
    [templates/layouts/customer.html]=0a9d7b775a20a734491a9353b970c0aaeefc4b7120d648f64fabc495a1e04d05
    [templates/layouts/dashboard.html]=9e53cb24a5dc4c00c748513c12421e2bf5bf70f0296e457b58fa03120f44b69f
    [templates/components/footer.html]=fac3bdf2df1ff807d9369f607bb5cf49e48d05fb800575fbbf88a9966ac51ddb
    [templates/components/mensajes.html]=b8486d2ba986c42943e5ccd3bed33953587b5326f53a7e751b628832481b1b43
    [templates/guest/acceso.html]=61265f8194bdbd81a2b7ceb82dbe0f60ee433a20b117a0a3c7a652045fdf3e26
    [apps/portal/guest/views/acceso.py]=ecf9d0bafdeb62f1e01488e3fe03e6f00a9eb458eb0b59d1080b175ae7bb8dc2
    [apps/portal/guest/views/__init__.py]=1366142934dc7b11aa527f427e533f24d1d8e611f618c405f10149336a6a61d2
    [apps/portal/guest/urls.py]=530b7bbae48eeb5b9788ef0d4e67306c47f4a6d86b403f333f50fa52f2adbbac
    [static/js/vistas/guest/acceso.js]=168b96426b2c545ba149bb93587bd9305c5292e754f8576d07031e4d52cd51cb
    [templates/403.html]=d292c9cf93f273955e8094f90d990a2395d90ce8ee3e684f9fe580245e2b1e24
    [templates/404.html]=1616e238b861bf7024977266199e894f7300c61ae7ee01e547b0df266d8b8933
    [templates/500.html]=2221907ba7bc8e9d24688af7e96d18edd302e97016cbff4fe0a1a33aea2cb825
    [templates/errors/bloqueado.html]=3daa0c5105bfca97190acbd24000a3a4d0d78d9dafc2b0e13acf72de86fd935e
)

escribir_stub() {
    local rel destino tmp actual
    rel="$(rel_actual "$1")"
    validar_ruta "$rel"
    destino="$RAIZ/$rel"
    tmp="$(mktemp)"
    cat >"$tmp"
    if [[ ! -e $destino ]]; then
        mkdir -p -- "$(dirname -- "$destino")"
        mv -- "$tmp" "$destino"
        chmod 0644 -- "$destino"
        CREADOS=$((CREADOS + 1))
        return 0
    fi
    if cmp -s -- "$tmp" "$destino"; then
        rm -f -- "$tmp"
        SIN_CAMBIOS=$((SIN_CAMBIOS + 1))
        return 0
    fi
    actual="$(sha256sum -- "$destino" | cut -d' ' -f1)"
    if [[ ${HASHES_STUB[$rel]:-} == "$actual" ]]; then
        respaldar "$rel"
        rm -f -- "$destino"
        mv -- "$tmp" "$destino"
        chmod 0644 -- "$destino"
        ACTUALIZADOS=$((ACTUALIZADOS + 1))
    else
        mv -- "$tmp" "$destino.propuesta"
        PROPUESTAS+=("$rel")
        OMITIDOS=$((OMITIDOS + 1))
    fi
}

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


verificar_base() {
    [[ -f "$RAIZ/apps/reportes/selectors/ventas.py" && -f "$RAIZ/templates/layouts/base.html" ]] \
        || fallar "Faltan los archivos de la fase 9B. Ejecute primero generar-fase9b.sh."
}

# ============================================================
# ETIQUETAS DE PLANTILLA
# ============================================================

paso_etiquetas() {
    info "Etiquetas: ruta activa e iconos de toast"
    ir_a "apps/core/templatetags"
    inyectar_bloque "bootstrap.py" "ui-1" <<'__FIN__'
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
__FIN__
}

# ============================================================
# CSS GLOBAL (Material 3 sobre Bootstrap)
# ============================================================

paso_css() {
    info "CSS global: paleta clara/oscura y componentes Material 3"
    ir_a "static/css"
    escribir_stub "app.css" <<'__FIN__'
@import url("https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap");

/* ============================================================
   1. TOKENS DE DISEÑO (Material 3) - tema claro y oscuro
   ============================================================ */
:root,
[data-bs-theme="light"] {
    color-scheme: light;
    --md-primary: #167C80;
    --md-primary-hover: #11666A;
    --md-on-primary: #FFFFFF;
    --md-primary-container: #D5F0ED;
    --md-on-primary-container: #103F41;
    --md-background: #F5F7F7;
    --md-surface: #FFFFFF;
    --md-surface-elevated: #FFFFFF;
    --md-surface-secondary: #EAF0F0;
    --md-border: #D8E1E1;
    --md-text: #172B2D;
    --md-text-secondary: #52686A;
    --md-success: #2E7D32;
    --md-success-container: #DDF1DE;
    --md-warning: #F2B705;
    --md-warning-container: #FFF4CC;
    --md-error: #B3261E;
    --md-error-container: #F9DEDC;
    --md-info: #1565C0;
    --md-info-container: #DCEBFA;
    --md-shadow-1: 0 1px 2px rgba(23, 43, 45, .08), 0 1px 3px rgba(23, 43, 45, .06);
    --md-shadow-2: 0 2px 6px rgba(23, 43, 45, .10), 0 1px 2px rgba(23, 43, 45, .06);
    --md-shadow-3: 0 10px 28px rgba(23, 43, 45, .18);

    --bs-body-bg: var(--md-background);
    --bs-body-bg-rgb: 245, 247, 247;
    --bs-body-color: var(--md-text);
    --bs-body-color-rgb: 23, 43, 45;
    --bs-emphasis-color: var(--md-text);
    --bs-heading-color: var(--md-text);
    --bs-secondary-color: var(--md-text-secondary);
    --bs-secondary-bg: var(--md-surface-secondary);
    --bs-secondary-bg-rgb: 234, 240, 240;
    --bs-tertiary-bg: var(--md-background);
    --bs-tertiary-bg-rgb: 245, 247, 247;
    --bs-border-color: var(--md-border);
    --bs-border-color-translucent: var(--md-border);
    --bs-primary: var(--md-primary);
    --bs-primary-rgb: 22, 124, 128;
    --bs-link-color: var(--md-primary);
    --bs-link-color-rgb: 22, 124, 128;
    --bs-link-hover-color: var(--md-primary-hover);
    --bs-link-hover-color-rgb: 17, 102, 106;
    --bs-success-rgb: 46, 125, 50;
    --bs-warning-rgb: 242, 183, 5;
    --bs-danger-rgb: 179, 38, 30;
    --bs-info-rgb: 21, 101, 192;
}

[data-bs-theme="dark"] {
    color-scheme: dark;
    --md-primary: #65D4CE;
    --md-primary-hover: #86E3DD;
    --md-on-primary: #05302F;
    --md-primary-container: #173B3D;
    --md-on-primary-container: #B4EFEB;
    --md-background: #101819;
    --md-surface: #1A2527;
    --md-surface-elevated: #243234;
    --md-surface-secondary: #202D2F;
    --md-border: #354648;
    --md-text: #E2E9E9;
    --md-text-secondary: #A6B9B9;
    --md-success: #81C784;
    --md-success-container: #1F3A22;
    --md-warning: #FFD54F;
    --md-warning-container: #3F3411;
    --md-error: #F2B8B5;
    --md-error-container: #4A1F1C;
    --md-info: #90CAF9;
    --md-info-container: #173250;
    --md-shadow-1: 0 1px 2px rgba(0, 0, 0, .4), 0 1px 3px rgba(0, 0, 0, .3);
    --md-shadow-2: 0 2px 8px rgba(0, 0, 0, .45);
    --md-shadow-3: 0 12px 32px rgba(0, 0, 0, .55);

    --bs-body-bg: var(--md-background);
    --bs-body-bg-rgb: 16, 24, 25;
    --bs-body-color: var(--md-text);
    --bs-body-color-rgb: 226, 233, 233;
    --bs-emphasis-color: #FFFFFF;
    --bs-heading-color: var(--md-text);
    --bs-secondary-color: var(--md-text-secondary);
    --bs-secondary-bg: var(--md-surface-secondary);
    --bs-secondary-bg-rgb: 32, 45, 47;
    --bs-tertiary-bg: var(--md-background);
    --bs-tertiary-bg-rgb: 16, 24, 25;
    --bs-border-color: var(--md-border);
    --bs-border-color-translucent: var(--md-border);
    --bs-primary: var(--md-primary);
    --bs-primary-rgb: 101, 212, 206;
    --bs-link-color: var(--md-primary);
    --bs-link-color-rgb: 101, 212, 206;
    --bs-link-hover-color: var(--md-primary-hover);
    --bs-link-hover-color-rgb: 134, 227, 221;
    --bs-success-rgb: 129, 199, 132;
    --bs-warning-rgb: 255, 213, 79;
    --bs-danger-rgb: 242, 184, 181;
    --bs-info-rgb: 144, 202, 249;
}

:root {
    --bs-body-font-family: "Roboto", system-ui, -apple-system, "Segoe UI", sans-serif;
    --bs-body-font-size: .975rem;
    --md-radio-s: 8px;
    --md-radio-m: 12px;
    --md-radio-l: 16px;
    --md-radio-xl: 24px;
    --md-mov: cubic-bezier(.2, 0, 0, 1);
}

/* ============================================================
   2. BASE
   ============================================================ */
body {
    font-family: var(--bs-body-font-family);
    background: var(--md-background);
    color: var(--md-text);
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    -webkit-font-smoothing: antialiased;
}

main { flex: 1 0 auto; }

h1, h2, h3, h4, h5, h6, .h1, .h2, .h3, .h4, .h5, .h6 { font-weight: 500; letter-spacing: -.005em; }
h1, .h3 { letter-spacing: -.01em; }
a { text-decoration: none; transition: color .15s var(--md-mov); }
a:hover { text-decoration: underline; }
hr { border-color: var(--md-border); opacity: 1; }
code { color: var(--md-on-primary-container); background: var(--md-primary-container); padding: .1rem .4rem; border-radius: var(--md-radio-s); }
::selection { background: var(--md-primary-container); color: var(--md-on-primary-container); }
:focus-visible { outline: 3px solid color-mix(in srgb, var(--md-primary) 55%, transparent); outline-offset: 2px; }

.material-symbols-rounded {
    font-variation-settings: "FILL" 0, "wght" 400, "GRAD" 0, "opsz" 24;
    font-size: 1.3rem;
    line-height: 1;
    vertical-align: middle;
    user-select: none;
}
.icono-relleno { font-variation-settings: "FILL" 1, "wght" 400, "GRAD" 0, "opsz" 24; }
.icono-grande { font-size: 2.5rem; }
.icono-xl { font-size: 4rem; }

/* ============================================================
   3. BOTONES (Material 3: relleno, tonal, contorno, texto)
   ============================================================ */
.btn {
    --bs-btn-border-radius: 100px;
    --bs-btn-padding-x: 1.35rem;
    --bs-btn-padding-y: .5rem;
    --bs-btn-font-weight: 500;
    border-radius: 100px;
    letter-spacing: .01em;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: .4rem;
    transition: background-color .2s var(--md-mov), box-shadow .2s var(--md-mov), transform .12s var(--md-mov), color .2s var(--md-mov);
}
.btn:hover { text-decoration: none; }
.btn:active { transform: scale(.98); }
.btn-sm { --bs-btn-padding-x: 1rem; --bs-btn-padding-y: .3rem; --bs-btn-font-size: .85rem; }
.btn-lg { --bs-btn-padding-x: 1.8rem; --bs-btn-padding-y: .7rem; }
.btn .material-symbols-rounded { font-size: 1.15rem; }

.btn-primary {
    --bs-btn-color: var(--md-on-primary);
    --bs-btn-bg: var(--md-primary);
    --bs-btn-border-color: var(--md-primary);
    --bs-btn-hover-color: var(--md-on-primary);
    --bs-btn-hover-bg: var(--md-primary-hover);
    --bs-btn-hover-border-color: var(--md-primary-hover);
    --bs-btn-active-color: var(--md-on-primary);
    --bs-btn-active-bg: var(--md-primary-hover);
    --bs-btn-active-border-color: var(--md-primary-hover);
    --bs-btn-disabled-bg: var(--md-primary);
    --bs-btn-disabled-border-color: var(--md-primary);
    --bs-btn-disabled-color: var(--md-on-primary);
    box-shadow: var(--md-shadow-1);
}
.btn-primary:hover { box-shadow: var(--md-shadow-2); }

.btn-success { --bs-btn-bg: var(--md-success); --bs-btn-border-color: var(--md-success); --bs-btn-hover-bg: var(--md-success); --bs-btn-hover-border-color: var(--md-success); --bs-btn-color: #fff; --bs-btn-hover-color: #fff; filter: none; }
[data-bs-theme="dark"] .btn-success { --bs-btn-color: #10250f; --bs-btn-hover-color: #10250f; }
.btn-success:hover { filter: brightness(.92); }

.btn-outline-primary {
    --bs-btn-color: var(--md-primary);
    --bs-btn-border-color: var(--md-primary);
    --bs-btn-hover-color: var(--md-on-primary-container);
    --bs-btn-hover-bg: var(--md-primary-container);
    --bs-btn-hover-border-color: var(--md-primary);
    --bs-btn-active-color: var(--md-on-primary-container);
    --bs-btn-active-bg: var(--md-primary-container);
    --bs-btn-active-border-color: var(--md-primary);
}
.btn-outline-secondary {
    --bs-btn-color: var(--md-on-primary-container);
    --bs-btn-bg: var(--md-primary-container);
    --bs-btn-border-color: transparent;
    --bs-btn-hover-color: var(--md-on-primary-container);
    --bs-btn-hover-bg: var(--md-primary-container);
    --bs-btn-hover-border-color: transparent;
    --bs-btn-active-color: var(--md-on-primary-container);
    --bs-btn-active-bg: var(--md-primary-container);
    --bs-btn-active-border-color: transparent;
}
.btn-outline-secondary:hover { filter: brightness(.96); }
[data-bs-theme="dark"] .btn-outline-secondary:hover { filter: brightness(1.15); }
.btn-outline-danger { --bs-btn-color: var(--md-error); --bs-btn-border-color: var(--md-error); --bs-btn-hover-color: var(--md-error); --bs-btn-hover-bg: var(--md-error-container); --bs-btn-hover-border-color: var(--md-error); --bs-btn-active-color: var(--md-error); --bs-btn-active-bg: var(--md-error-container); }
.btn-outline-light { --bs-btn-color: var(--md-text); --bs-btn-border-color: var(--md-border); --bs-btn-hover-color: var(--md-text); --bs-btn-hover-bg: var(--md-surface-secondary); --bs-btn-hover-border-color: var(--md-border); }
.btn-link { --bs-btn-color: var(--md-primary); --bs-btn-hover-color: var(--md-primary-hover); text-decoration: none; }
.btn-link:hover { background: color-mix(in srgb, var(--md-primary) 10%, transparent); }
.btn-icono {
    width: 2.6rem;
    height: 2.6rem;
    padding: 0;
    border: 0;
    border-radius: 50%;
    background: transparent;
    color: var(--md-text-secondary);
    position: relative;
}
.btn-icono:hover, .btn-icono:focus-visible { background: var(--md-surface-secondary); color: var(--md-text); }
.btn-tonal { background: var(--md-primary-container); color: var(--md-on-primary-container); border: 0; }
.btn-tonal:hover, .btn-tonal.show { background: var(--md-primary-container); color: var(--md-on-primary-container); filter: brightness(.96); }
.btn-close { border-radius: 50%; }
[data-bs-theme="dark"] .btn-close { filter: invert(1) grayscale(100%) brightness(200%); }

/* ============================================================
   4. CAMPOS DE FORMULARIO (M3: relleno con foco de marca)
   ============================================================ */
.form-label { font-weight: 500; font-size: .85rem; color: var(--md-text-secondary); margin-bottom: .35rem; }
.form-control,
.form-select {
    background-color: var(--md-surface-secondary);
    color: var(--md-text);
    border: 1px solid var(--md-border);
    border-radius: var(--md-radio-m);
    padding: .65rem .9rem;
    transition: border-color .15s var(--md-mov), box-shadow .15s var(--md-mov), background-color .15s var(--md-mov);
}
.form-control::placeholder { color: var(--md-text-secondary); opacity: .75; }
.form-control:focus,
.form-select:focus {
    background-color: var(--md-surface);
    color: var(--md-text);
    border-color: var(--md-primary);
    box-shadow: 0 0 0 1px var(--md-primary);
}
.form-control:disabled,
.form-control[disabled] { background-color: var(--md-surface-secondary); opacity: .7; }
.form-control.is-invalid, .form-select.is-invalid { border-color: var(--md-error); box-shadow: none; background-image: none; }
.form-control.is-valid, .form-select.is-valid { border-color: var(--md-success); background-image: none; }
.invalid-feedback { color: var(--md-error); font-size: .8rem; }
.form-text { color: var(--md-text-secondary); }
textarea.form-control { min-height: 5.5rem; }
.form-check-input { border-color: var(--md-text-secondary); background-color: transparent; }
.form-check-input:checked { background-color: var(--md-primary); border-color: var(--md-primary); }
.form-check-input:focus { box-shadow: 0 0 0 3px color-mix(in srgb, var(--md-primary) 30%, transparent); border-color: var(--md-primary); }
.form-check-input[type="checkbox"] { border-radius: 6px; }
.input-group > .input-group-text {
    background: var(--md-surface-secondary);
    border: 1px solid var(--md-border);
    border-right: 0;
    color: var(--md-text-secondary);
    border-radius: var(--md-radio-m) 0 0 var(--md-radio-m);
}
.input-group > .form-control:not(:first-child) { border-left: 0; border-radius: 0; }
.input-group > .form-control:last-child { border-radius: 0 var(--md-radio-m) var(--md-radio-m) 0; }
.input-group > .btn-icono { background: var(--md-surface-secondary); border: 1px solid var(--md-border); border-left: 0; border-radius: 0 var(--md-radio-m) var(--md-radio-m) 0; width: 3rem; height: auto; }
.input-group:focus-within > .input-group-text,
.input-group:focus-within > .form-control,
.input-group:focus-within > .btn-icono { border-color: var(--md-primary); }
.input-group-sm > .btn,
.input-group-sm > .form-control { border-radius: 100px; }

/* ============================================================
   5. TARJETAS, LISTAS, TABLAS, CHIPS
   ============================================================ */
.card {
    --bs-card-bg: var(--md-surface);
    --bs-card-border-color: var(--md-border);
    --bs-card-border-radius: var(--md-radio-l);
    --bs-card-inner-border-radius: calc(var(--md-radio-l) - 1px);
    --bs-card-cap-bg: transparent;
    box-shadow: var(--md-shadow-1);
    transition: box-shadow .25s var(--md-mov), transform .25s var(--md-mov), border-color .25s var(--md-mov);
}
.card-footer { background: transparent; border-top: 1px solid var(--md-border); }
.card-hover:hover, a.card:hover { box-shadow: var(--md-shadow-3); transform: translateY(-3px); border-color: color-mix(in srgb, var(--md-primary) 40%, var(--md-border)); }
.card-img-top { border-top-left-radius: calc(var(--md-radio-l) - 1px); border-top-right-radius: calc(var(--md-radio-l) - 1px); }

.list-group {
    --bs-list-group-bg: var(--md-surface);
    --bs-list-group-color: var(--md-text);
    --bs-list-group-border-color: var(--md-border);
    --bs-list-group-border-radius: var(--md-radio-m);
    --bs-list-group-action-hover-bg: var(--md-surface-secondary);
    box-shadow: var(--md-shadow-1);
}
.list-group-item-primary { --bs-list-group-color: var(--md-on-primary-container); --bs-list-group-bg: var(--md-primary-container); }

.table-responsive {
    background: var(--md-surface);
    border: 1px solid var(--md-border);
    border-radius: var(--md-radio-l);
    box-shadow: var(--md-shadow-1);
}
.table {
    --bs-table-bg: transparent;
    --bs-table-color: var(--md-text);
    --bs-table-border-color: var(--md-border);
    --bs-table-striped-bg: color-mix(in srgb, var(--md-surface-secondary) 45%, transparent);
    --bs-table-striped-color: var(--md-text);
    --bs-table-hover-bg: var(--md-primary-container);
    --bs-table-hover-color: var(--md-on-primary-container);
    margin-bottom: 0;
}
.table > thead > tr > th {
    background: var(--md-surface-secondary);
    color: var(--md-text-secondary);
    font-size: .75rem;
    font-weight: 500;
    letter-spacing: .06em;
    text-transform: uppercase;
    white-space: nowrap;
    border-bottom: 1px solid var(--md-border);
    padding: .85rem 1rem;
}
.table > tbody > tr > td { padding: .8rem 1rem; }
.table > tbody > tr:last-child > td { border-bottom: 0; }
.table-danger { --bs-table-bg: var(--md-error-container); --bs-table-color: var(--md-text); }
.acciones-tabla { display: inline-flex; gap: .35rem; flex-wrap: wrap; justify-content: flex-end; }

.badge {
    --bs-badge-border-radius: var(--md-radio-s);
    --bs-badge-padding-x: .65em;
    --bs-badge-padding-y: .4em;
    font-weight: 500;
    letter-spacing: .02em;
}
.badge.text-bg-primary { background-color: var(--md-primary) !important; color: var(--md-on-primary) !important; }
.badge.text-bg-secondary { background-color: var(--md-surface-secondary) !important; color: var(--md-text-secondary) !important; border: 1px solid var(--md-border); }
.badge.text-bg-success { background-color: var(--md-success-container) !important; color: var(--md-success) !important; }
.badge.text-bg-warning { background-color: var(--md-warning-container) !important; color: #7A5B00 !important; }
[data-bs-theme="dark"] .badge.text-bg-warning { color: var(--md-warning) !important; }
.badge.text-bg-danger { background-color: var(--md-error-container) !important; color: var(--md-error) !important; }
.badge.text-bg-info { background-color: var(--md-info-container) !important; color: var(--md-info) !important; }
.badge.text-bg-dark { background-color: var(--md-text) !important; color: var(--md-background) !important; }

.alert { border: 0; border-radius: var(--md-radio-m); }
.alert-danger { background: var(--md-error-container); color: var(--md-error); }
.alert-success { background: var(--md-success-container); color: var(--md-success); }
.alert-warning { background: var(--md-warning-container); color: #7A5B00; }
[data-bs-theme="dark"] .alert-warning { color: var(--md-warning); }
.alert-info { background: var(--md-info-container); color: var(--md-info); }
.alert-secondary { background: var(--md-surface-secondary); color: var(--md-text-secondary); }

.progress { --bs-progress-height: .55rem; --bs-progress-bg: var(--md-surface-secondary); --bs-progress-bar-bg: var(--md-primary); --bs-progress-border-radius: 100px; }
.progress-bar { transition: width .6s var(--md-mov); }

/* ============================================================
   6. NAVEGACION: pestañas, paginacion, menus
   ============================================================ */
.nav-pills { --bs-nav-pills-border-radius: 100px; --bs-nav-pills-link-active-bg: var(--md-primary-container); --bs-nav-pills-link-active-color: var(--md-on-primary-container); }
.nav-pills .nav-link { color: var(--md-text-secondary); font-weight: 500; }
.nav-pills .nav-link:hover { background: var(--md-surface-secondary); }
.nav-pills .nav-link.active { box-shadow: none; }

.pagination { --bs-pagination-bg: transparent; --bs-pagination-color: var(--md-text); --bs-pagination-border-color: transparent; --bs-pagination-hover-bg: var(--md-surface-secondary); --bs-pagination-hover-color: var(--md-primary); --bs-pagination-hover-border-color: transparent; --bs-pagination-active-bg: var(--md-primary-container); --bs-pagination-active-color: var(--md-on-primary-container); --bs-pagination-active-border-color: transparent; --bs-pagination-disabled-bg: transparent; --bs-pagination-disabled-border-color: transparent; --bs-pagination-border-radius: 100px; gap: .25rem; }
.page-link { border-radius: 100px !important; padding: .45rem 1rem; font-weight: 500; }

.dropdown-menu {
    --bs-dropdown-bg: var(--md-surface-elevated);
    --bs-dropdown-color: var(--md-text);
    --bs-dropdown-border-color: var(--md-border);
    --bs-dropdown-border-radius: var(--md-radio-m);
    --bs-dropdown-link-color: var(--md-text);
    --bs-dropdown-link-hover-bg: var(--md-surface-secondary);
    --bs-dropdown-link-hover-color: var(--md-text);
    --bs-dropdown-link-active-bg: var(--md-primary-container);
    --bs-dropdown-link-active-color: var(--md-on-primary-container);
    --bs-dropdown-divider-bg: var(--md-border);
    box-shadow: var(--md-shadow-3);
    padding: .4rem;
    min-width: 14rem;
    animation: aparecer-rapido .16s var(--md-mov);
}
.dropdown-item { border-radius: var(--md-radio-s); display: flex; align-items: center; gap: .65rem; padding: .55rem .8rem; }

/* ============================================================
   7. BARRA SUPERIOR
   ============================================================ */
.barra-superior {
    background: var(--md-surface);
    border-bottom: 1px solid var(--md-border);
    z-index: 1030;
}
.barra-superior .navbar { padding-top: .5rem; padding-bottom: .5rem; --bs-navbar-toggler-border-color: var(--md-border); }
.navbar-toggler { border-radius: var(--md-radio-m); color: var(--md-text); }
.navbar-toggler-icon { background-image: none; display: inline-flex; align-items: center; justify-content: center; }
.navbar-toggler-icon::before { content: "menu"; font-family: "Material Symbols Rounded"; font-size: 1.5rem; color: var(--md-text); }
.navbar-brand { font-weight: 500; color: var(--md-text); display: inline-flex; align-items: center; gap: .55rem; }
.navbar-brand:hover { text-decoration: none; color: var(--md-primary); }
.icono-marca { color: var(--md-primary); font-size: 1.7rem; font-variation-settings: "FILL" 1, "wght" 500, "GRAD" 0, "opsz" 24; }
.barra-superior .navbar-nav { gap: .15rem; }
.barra-superior .nav-link {
    display: inline-flex;
    align-items: center;
    gap: .45rem;
    padding: .5rem 1rem;
    border-radius: 100px;
    color: var(--md-text-secondary);
    font-weight: 500;
    transition: background-color .2s var(--md-mov), color .2s var(--md-mov);
}
.barra-superior .nav-link:hover { background: var(--md-surface-secondary); color: var(--md-text); text-decoration: none; }
.barra-superior .nav-link.active { background: var(--md-primary-container); color: var(--md-on-primary-container); }
.barra-superior .nav-link.active .material-symbols-rounded { font-variation-settings: "FILL" 1, "wght" 500, "GRAD" 0, "opsz" 24; }
.avatar-inicial {
    width: 1.9rem;
    height: 1.9rem;
    border-radius: 50%;
    background: var(--md-primary);
    color: var(--md-on-primary);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: .85rem;
    font-weight: 500;
}
.insignia-notificacion {
    position: absolute;
    top: .1rem;
    right: .05rem;
    min-width: 1.15rem;
    height: 1.15rem;
    padding: 0 .3rem;
    border-radius: 100px;
    background: var(--md-error);
    color: #fff;
    font-size: .68rem;
    font-weight: 700;
    display: inline-flex;
    align-items: center;
    justify-content: center;
}
[data-bs-theme="dark"] .insignia-notificacion { color: #3b0a07; }
@media (min-width: 992px) {
    .barra-izquierda, .barra-derecha { flex: 1 1 0; }
    .barra-derecha { justify-content: flex-end; }
}
@media (max-width: 991.98px) {
    .barra-derecha { padding: .75rem 0 .25rem; border-top: 1px solid var(--md-border); margin-top: .5rem; }
}

/* ============================================================
   8. TOASTS (iconos y 4 tipos)
   ============================================================ */
.toast-container { z-index: 1090; }
.toast-md {
    --toast-color: var(--md-info);
    --bs-toast-bg: var(--md-surface-elevated);
    --bs-toast-border-width: 0;
    --bs-toast-border-radius: var(--md-radio-l);
    --bs-toast-color: var(--md-text);
    width: min(24rem, calc(100vw - 2rem));
    background: var(--md-surface-elevated);
    color: var(--md-text);
    border: 0;
    border-left: 6px solid var(--toast-color);
    border-radius: var(--md-radio-l);
    box-shadow: var(--md-shadow-3);
    overflow: hidden;
    margin-bottom: .75rem;
}
.toast-md.showing, .toast-md.show { animation: toast-entrada .3s var(--md-mov); }
.toast-success { --toast-color: var(--md-success); }
.toast-error { --toast-color: var(--md-error); }
.toast-warning { --toast-color: var(--md-warning); }
.toast-info { --toast-color: var(--md-info); }
.toast-md .toast-icono { color: var(--toast-color); font-size: 1.7rem; font-variation-settings: "FILL" 1, "wght" 400, "GRAD" 0, "opsz" 24; }
.toast-md strong { font-weight: 500; }
.toast-progreso { height: 3px; background: var(--toast-color); transform-origin: left; animation: toast-progreso 5s linear forwards; }
.toast-md:hover .toast-progreso { animation-play-state: paused; }

/* ============================================================
   9. PAGINA: contenedor, cabeceras, estados vacios, pie
   ============================================================ */
.contenido-animado > * { animation: aparecer .4s var(--md-mov) both; }
.contenido-animado > *:nth-child(2) { animation-delay: .04s; }
.contenido-animado > *:nth-child(3) { animation-delay: .08s; }
.contenido-animado > *:nth-child(4) { animation-delay: .12s; }
.contenido-animado > *:nth-child(5) { animation-delay: .16s; }
.contenido-animado > *:nth-child(n+6) { animation-delay: .2s; }

.heroe {
    background: linear-gradient(135deg, var(--md-primary-container), var(--md-surface) 70%);
    border: 1px solid var(--md-border);
    border-radius: var(--md-radio-xl);
    box-shadow: var(--md-shadow-1);
}
.estado-vacio { text-align: center; padding: 2.5rem 1rem; color: var(--md-text-secondary); }
.estado-vacio .material-symbols-rounded { font-size: 3rem; color: var(--md-primary); opacity: .8; }

.pie-pagina { background: var(--md-surface); border-top: 1px solid var(--md-border); margin-top: 3rem; }
.pie-pagina a { color: var(--md-text-secondary); }
.pie-pagina a:hover { color: var(--md-primary); }

.documento-legal { max-width: 52rem; margin: 0 auto; }
.documento-legal h2 { font-size: 1.15rem; margin-top: 2rem; color: var(--md-primary); }
.documento-legal p, .documento-legal li { color: var(--md-text); line-height: 1.7; }

.pagina-error { min-height: 70vh; display: flex; align-items: center; justify-content: center; text-align: center; }

/* ============================================================
   10. ACCESO / AUTENTICACION
   ============================================================ */
.auth-contenedor { max-width: 31rem; margin: 1.5rem auto; }
.auth-tarjeta { border-radius: var(--md-radio-xl); box-shadow: var(--md-shadow-2); }
.auth-pestanas { background: var(--md-surface-secondary); border-radius: 100px; padding: .3rem; }
.auth-pestanas .nav-link { justify-content: center; }
.auth-pestanas .nav-link.active { background: var(--md-surface); color: var(--md-primary); box-shadow: var(--md-shadow-1); }
.auth-separador { display: flex; align-items: center; gap: .75rem; color: var(--md-text-secondary); font-size: .8rem; margin: 1rem 0; }
.auth-separador::before, .auth-separador::after { content: ""; flex: 1; height: 1px; background: var(--md-border); }
.tab-pane.fade { transition: opacity .25s var(--md-mov); }

/* Paginas de allauth sin plantilla propia (recuperar contrasena, correo, etc.) */
.auth-contenido { max-width: 34rem; margin: 1.5rem auto; background: var(--md-surface); border: 1px solid var(--md-border); border-radius: var(--md-radio-xl); box-shadow: var(--md-shadow-2); padding: 2rem; }
.auth-contenido h1 { font-size: 1.5rem; margin-bottom: 1rem; }
.auth-contenido p, .auth-contenido li { color: var(--md-text-secondary); }
.auth-contenido form { display: flex; flex-direction: column; gap: .9rem; margin-top: 1rem; }
.auth-contenido label { font-weight: 500; font-size: .85rem; color: var(--md-text-secondary); display: block; margin-bottom: .25rem; }
.auth-contenido input:not([type="checkbox"]):not([type="radio"]):not([type="hidden"]) {
    width: 100%;
    background: var(--md-surface-secondary);
    color: var(--md-text);
    border: 1px solid var(--md-border);
    border-radius: var(--md-radio-m);
    padding: .65rem .9rem;
}
.auth-contenido input:focus { outline: 0; border-color: var(--md-primary); box-shadow: 0 0 0 1px var(--md-primary); background: var(--md-surface); }
.auth-contenido button,
.auth-contenido input[type="submit"] {
    background: var(--md-primary);
    color: var(--md-on-primary);
    border: 0;
    border-radius: 100px;
    padding: .6rem 1.4rem;
    font-weight: 500;
    cursor: pointer;
    box-shadow: var(--md-shadow-1);
    transition: background-color .2s var(--md-mov), box-shadow .2s var(--md-mov);
}
.auth-contenido button:hover { background: var(--md-primary-hover); box-shadow: var(--md-shadow-2); }
.auth-contenido ul.errorlist, .auth-contenido .errorlist { list-style: none; padding: .5rem .8rem; margin: .4rem 0 0; background: var(--md-error-container); color: var(--md-error); border-radius: var(--md-radio-s); font-size: .85rem; }
.auth-contenido hr { margin: 1.25rem 0; }

/* ============================================================
   11. ANIMACIONES
   ============================================================ */
@keyframes aparecer { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }
@keyframes aparecer-rapido { from { opacity: 0; transform: translateY(-4px) scale(.98); } to { opacity: 1; transform: none; } }
@keyframes toast-entrada { from { opacity: 0; transform: translateX(24px); } to { opacity: 1; transform: none; } }
@keyframes toast-progreso { from { transform: scaleX(1); } to { transform: scaleX(0); } }

@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation-duration: .01ms !important; animation-iteration-count: 1 !important; transition-duration: .01ms !important; scroll-behavior: auto !important; }
}
__FIN__
}

# ============================================================
# JS COMUN: tema, toasts y graficos
# ============================================================

paso_js_comun() {
    info "JS comun: alternador de tema, toasts con icono y graficos adaptados al tema"
    ir_a "static/js/components"

    escribir "tema.js" <<'__FIN__'
(function () {
    "use strict";

    var CLAVE = "tema";

    function actual() {
        return document.documentElement.getAttribute("data-bs-theme") || "light";
    }

    function guardado() {
        try { return localStorage.getItem(CLAVE); } catch (error) { return null; }
    }

    function aplicar(tema, guardar) {
        document.documentElement.setAttribute("data-bs-theme", tema);
        if (guardar) {
            try { localStorage.setItem(CLAVE, tema); } catch (error) { /* almacenamiento no disponible */ }
        }
        var oscuro = tema === "dark";
        document.querySelectorAll(".icono-tema").forEach(function (icono) {
            icono.textContent = oscuro ? "light_mode" : "dark_mode";
        });
        document.querySelectorAll("[data-alternar-tema]").forEach(function (boton) {
            boton.setAttribute("aria-pressed", oscuro ? "true" : "false");
            boton.setAttribute("aria-label", oscuro ? "Cambiar a tema claro" : "Cambiar a tema oscuro");
            boton.setAttribute("title", oscuro ? "Tema claro" : "Tema oscuro");
        });
        document.dispatchEvent(new CustomEvent("tema:cambio", { detail: { tema: tema } }));
    }

    document.addEventListener("DOMContentLoaded", function () {
        aplicar(actual(), false);
        document.querySelectorAll("[data-alternar-tema]").forEach(function (boton) {
            boton.addEventListener("click", function () {
                aplicar(actual() === "dark" ? "light" : "dark", true);
            });
        });
        var sistema = window.matchMedia("(prefers-color-scheme: dark)");
        sistema.addEventListener("change", function (evento) {
            if (!guardado()) { aplicar(evento.matches ? "dark" : "light", false); }
        });
    });
})();
__FIN__

    escribir "toasts.js" <<'__FIN__'
(function (global, $) {
    "use strict";

    var TIPOS = {
        success: { icono: "check_circle", titulo: "Listo" },
        error: { icono: "error", titulo: "Error" },
        warning: { icono: "warning", titulo: "Atención" },
        info: { icono: "info", titulo: "Información" }
    };

    function contenedor() {
        var $c = $("#contenedor-toasts");
        if (!$c.length) {
            $c = $('<div id="contenedor-toasts" class="toast-container position-fixed top-0 end-0 p-3" aria-live="polite" aria-atomic="true"></div>');
            $c.appendTo("body");
        }
        return $c;
    }

    function activar(elemento) {
        new bootstrap.Toast(elemento, { delay: 5000 }).show();
    }

    function mostrar(tipo, mensaje) {
        var clave = TIPOS[tipo] ? tipo : "info";
        var datos = TIPOS[clave];
        var $toast = $('<div class="toast toast-md" role="alert" aria-live="assertive" aria-atomic="true"></div>').addClass("toast-" + clave);
        var $icono = $('<span class="material-symbols-rounded toast-icono" aria-hidden="true"></span>').text(datos.icono);
        var $texto = $('<div class="flex-grow-1"></div>')
            .append($('<strong class="d-block"></strong>').text(datos.titulo))
            .append($("<span></span>").text(mensaje));
        var $cerrar = $('<button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Cerrar"></button>');
        $toast.append($('<div class="d-flex align-items-start gap-3 p-3"></div>').append($icono).append($texto).append($cerrar));
        $toast.append('<div class="toast-progreso"></div>');
        contenedor().append($toast);
        $toast.on("hidden.bs.toast", function () { $toast.remove(); });
        activar($toast[0]);
    }

    $(function () {
        $("#contenedor-toasts .toast").each(function () { activar(this); });
    });

    global.Toast = { mostrar: mostrar };
})(window, jQuery);
__FIN__

    escribir "graficos.js" <<'__FIN__'
(function ($) {
    "use strict";

    var PALETA = ["primary", "success", "warning", "danger", "info", "secondary", "purple"];
    var instancias = [];

    function variable(nombre) {
        return getComputedStyle(document.documentElement).getPropertyValue(nombre).trim();
    }

    function color(nombre) {
        return variable("--bs-" + nombre) || "#167C80";
    }

    function colores(cantidad) {
        var lista = [];
        for (var i = 0; i < cantidad; i++) { lista.push(color(PALETA[i % PALETA.length])); }
        return lista;
    }

    function formato(valor, dinero) {
        return dinero ? "$" + Number(valor).toFixed(2) : String(valor);
    }

    function sinDatos(datos) {
        return datos.series.every(function (serie) {
            return serie.valores.every(function (valor) { return !valor; });
        });
    }

    function configurarBase() {
        Chart.defaults.color = variable("--md-text-secondary") || "#52686A";
        Chart.defaults.borderColor = variable("--md-border") || "#D8E1E1";
        Chart.defaults.font.family = "Roboto, system-ui, sans-serif";
    }

    function construir(canvas, datos) {
        var tipo = canvas.getAttribute("data-tipo") || "bar";
        var circular = tipo === "doughnut" || tipo === "pie";
        var horizontal = canvas.getAttribute("data-eje") === "y";
        var paleta = colores(circular ? datos.etiquetas.length : datos.series.length);
        var conjuntos = datos.series.map(function (serie, i) {
            return {
                label: serie.nombre,
                data: serie.valores,
                backgroundColor: circular ? paleta : paleta[i],
                borderColor: circular ? variable("--md-surface") : paleta[i],
                borderRadius: circular ? 0 : 6,
                tension: 0.25
            };
        });
        var escalas = {};
        if (!circular) {
            escalas[horizontal ? "x" : "y"] = {
                beginAtZero: true,
                ticks: { callback: function (valor) { return datos.dinero ? "$" + valor : valor; } }
            };
        }
        return new Chart(canvas, {
            type: tipo,
            data: { labels: datos.etiquetas, datasets: conjuntos },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: horizontal ? "y" : "x",
                plugins: {
                    legend: { display: conjuntos.length > 1 || circular },
                    tooltip: {
                        callbacks: {
                            label: function (contexto) {
                                var valor = circular ? contexto.parsed : (horizontal ? contexto.parsed.x : contexto.parsed.y);
                                return (contexto.dataset.label || "") + ": " + formato(valor, datos.dinero);
                            }
                        }
                    }
                },
                scales: escalas
            }
        });
    }

    function dibujar() {
        var origen = document.getElementById("datos-graficos");
        if (!origen || typeof Chart === "undefined") { return; }
        instancias.forEach(function (grafico) { grafico.destroy(); });
        instancias = [];
        configurarBase();
        var todos = JSON.parse(origen.textContent);
        $("canvas[data-grafico]").each(function () {
            var datos = todos[this.getAttribute("data-grafico")];
            if (!datos) { return; }
            if (sinDatos(datos)) {
                $(this).closest(".ratio").replaceWith($('<p class="text-body-secondary mb-0"></p>').text("Sin datos en este período."));
                return;
            }
            instancias.push(construir(this, datos));
        });
    }

    $(dibujar);
    document.addEventListener("tema:cambio", dibujar);
})(jQuery);
__FIN__
}

# ============================================================
# LAYOUTS Y COMPONENTES COMUNES
# ============================================================

paso_layouts() {
    info "Layouts, barra superior y pie de pagina"
    ir_a "templates/layouts"

    escribir_stub "base.html" <<'__FIN__'
{% load static %}<!doctype html>
<html lang="es" data-bs-theme="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <script>
    (function () {
      try {
        var tema = localStorage.getItem("tema");
        if (!tema) { tema = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"; }
        document.documentElement.setAttribute("data-bs-theme", tema);
      } catch (error) {
        document.documentElement.setAttribute("data-bs-theme", "light");
      }
    })();
  </script>
  <title>{% block titulo %}{% endblock %} | {{ negocio.nombre_negocio|default:"3DForge Studio" }}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,0,0&display=block" rel="stylesheet">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <link href="{% static 'css/app.css' %}" rel="stylesheet">
  {% block estilos %}{% endblock %}
</head>
<body>
  {% block cuerpo %}{% block contenido %}{% endblock %}{% endblock %}
  {% include "components/mensajes.html" %}
  <script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
  <script src="{% static 'js/components/tema.js' %}"></script>
  <script src="{% static 'js/components/toasts.js' %}"></script>
  <script src="{% static 'js/components/formularios.js' %}"></script>
  {% if request.resolver_match.namespace %}
  {% with ruta="js/vistas/"|add:request.resolver_match.namespace|add:"/"|add:request.resolver_match.url_name|add:".js" %}
  <script src="{% static ruta %}"></script>
  {% endwith %}
  {% endif %}
  {% block scripts %}{% endblock %}
</body>
</html>
__FIN__

    escribir_stub "guest.html" <<'__FIN__'
{% extends "layouts/base.html" %}

{% block cuerpo %}
{% include "components/barra.html" %}
<main class="container-xxl py-4 contenido-animado">
  {% block contenido %}{% endblock %}
</main>
{% include "components/footer.html" %}
{% endblock %}
__FIN__

    escribir_stub "customer.html" <<'__FIN__'
{% extends "layouts/base.html" %}

{% block cuerpo %}
{% include "components/barra.html" %}
<main class="container-xxl py-4 contenido-animado">
  {% block contenido %}{% endblock %}
</main>
{% include "components/footer.html" %}
{% endblock %}
__FIN__

    escribir_stub "dashboard.html" <<'__FIN__'
{% extends "layouts/base.html" %}

{% block cuerpo %}
{% include "components/barra.html" %}
<main class="container-xxl py-4 contenido-animado">
  {% block contenido %}{% endblock %}
</main>
{% include "components/footer.html" %}
{% endblock %}
__FIN__

    ir_a "templates/components"
    escribir "barra.html" <<'__FIN__'
{% load bootstrap %}
{% with ns=request.resolver_match.namespace %}
<header class="barra-superior sticky-top">
  <nav class="navbar navbar-expand-lg" aria-label="Navegación principal">
    <div class="container-xxl">
      <div class="barra-izquierda d-flex align-items-center">
        <a class="navbar-brand me-0" href="{% if user.is_authenticated %}{% url 'redirigir' %}{% else %}{% url 'guest:inicio' %}{% endif %}">
          <span class="material-symbols-rounded icono-marca" aria-hidden="true">deployed_code</span>
          <span>{{ negocio.nombre_negocio|default:"3DForge Studio" }}</span>
        </a>
      </div>
      <button class="navbar-toggler ms-auto" type="button" data-bs-toggle="collapse" data-bs-target="#menu-principal" aria-controls="menu-principal" aria-expanded="false" aria-label="Abrir menú">
        <span class="navbar-toggler-icon"></span>
      </button>
      <div class="collapse navbar-collapse" id="menu-principal">
        <ul class="navbar-nav mx-lg-auto mb-2 mb-lg-0">
          {% if ns == "customer" %}
            {% activo "customer:panel" as a %}<li class="nav-item"><a class="nav-link {{ a }}" href="{% url 'customer:panel' %}"{% if a %} aria-current="page"{% endif %}><span class="material-symbols-rounded">space_dashboard</span>Panel</a></li>
            {% activo "customer:tienda" "customer:carrito" "customer:checkout" as a %}<li class="nav-item"><a class="nav-link {{ a }}" href="{% url 'customer:tienda' %}"{% if a %} aria-current="page"{% endif %}><span class="material-symbols-rounded">storefront</span>Tienda</a></li>
            {% activo "customer:cotizar" "customer:cotizaciones" "customer:cotizacion" as a %}<li class="nav-item"><a class="nav-link {{ a }}" href="{% url 'customer:cotizaciones' %}"{% if a %} aria-current="page"{% endif %}><span class="material-symbols-rounded">request_quote</span>Cotizaciones</a></li>
            {% activo "customer:pedidos" "customer:pedido" as a %}<li class="nav-item"><a class="nav-link {{ a }}" href="{% url 'customer:pedidos' %}"{% if a %} aria-current="page"{% endif %}><span class="material-symbols-rounded">package_2</span>Pedidos</a></li>
            {% activo "customer:facturas" "customer:factura" as a %}<li class="nav-item"><a class="nav-link {{ a }}" href="{% url 'customer:facturas' %}"{% if a %} aria-current="page"{% endif %}><span class="material-symbols-rounded">receipt_long</span>Facturas</a></li>
            {% activo "customer:soporte" "customer:soporte_detalle" as a %}<li class="nav-item"><a class="nav-link {{ a }}" href="{% url 'customer:soporte' %}"{% if a %} aria-current="page"{% endif %}><span class="material-symbols-rounded">support_agent</span>Soporte</a></li>
          {% elif ns == "operator" %}
            {% activo "operator:panel" as a %}<li class="nav-item"><a class="nav-link {{ a }}" href="{% url 'operator:panel' %}"{% if a %} aria-current="page"{% endif %}><span class="material-symbols-rounded">space_dashboard</span>Panel</a></li>
            {% activo "operator:cotizaciones" "operator:cotizacion" as a %}<li class="nav-item"><a class="nav-link {{ a }}" href="{% url 'operator:cotizaciones' %}"{% if a %} aria-current="page"{% endif %}><span class="material-symbols-rounded">request_quote</span>Cotizaciones</a></li>
            {% activo "operator:encargos" "operator:encargo" as a %}<li class="nav-item"><a class="nav-link {{ a }}" href="{% url 'operator:encargos' %}"{% if a %} aria-current="page"{% endif %}><span class="material-symbols-rounded">package_2</span>Encargos</a></li>
            {% activo "operator:facturas" "operator:factura" as a %}<li class="nav-item"><a class="nav-link {{ a }}" href="{% url 'operator:facturas' %}"{% if a %} aria-current="page"{% endif %}><span class="material-symbols-rounded">receipt_long</span>Facturas</a></li>
            {% activo "operator:clientes" "operator:cliente" as a %}<li class="nav-item"><a class="nav-link {{ a }}" href="{% url 'operator:clientes' %}"{% if a %} aria-current="page"{% endif %}><span class="material-symbols-rounded">groups</span>Clientes</a></li>
            {% activo "operator:soporte" "operator:soporte_detalle" as a %}<li class="nav-item"><a class="nav-link {{ a }}" href="{% url 'operator:soporte' %}"{% if a %} aria-current="page"{% endif %}><span class="material-symbols-rounded">support_agent</span>Soporte</a></li>
          {% elif ns == "administrator" %}
            {% activo "administrator:dashboard" as a %}<li class="nav-item"><a class="nav-link {{ a }}" href="{% url 'administrator:dashboard' %}"{% if a %} aria-current="page"{% endif %}><span class="material-symbols-rounded">monitoring</span>Dashboard</a></li>
            {% activo "administrator:inventario" "administrator:producto_crear" "administrator:producto_editar" as a %}<li class="nav-item"><a class="nav-link {{ a }}" href="{% url 'administrator:inventario' %}"{% if a %} aria-current="page"{% endif %}><span class="material-symbols-rounded">inventory_2</span>Productos</a></li>
            {% activo "administrator:servicios" "administrator:servicio_crear" "administrator:servicio_editar" "administrator:categoria_crear" "administrator:categoria_editar" as a %}<li class="nav-item"><a class="nav-link {{ a }}" href="{% url 'administrator:servicios' %}"{% if a %} aria-current="page"{% endif %}><span class="material-symbols-rounded">handyman</span>Servicios</a></li>
            {% activo "administrator:usuarios" "administrator:usuario_crear" "administrator:usuario_editar" as a %}<li class="nav-item"><a class="nav-link {{ a }}" href="{% url 'administrator:usuarios' %}"{% if a %} aria-current="page"{% endif %}><span class="material-symbols-rounded">manage_accounts</span>Usuarios</a></li>
            {% activo "administrator:ventas" as a %}<li class="nav-item"><a class="nav-link {{ a }}" href="{% url 'administrator:ventas' %}"{% if a %} aria-current="page"{% endif %}><span class="material-symbols-rounded">payments</span>Ventas</a></li>
            {% activo "administrator:configuracion" as a %}<li class="nav-item"><a class="nav-link {{ a }}" href="{% url 'administrator:configuracion' %}"{% if a %} aria-current="page"{% endif %}><span class="material-symbols-rounded">settings</span>Configuración</a></li>
            <li class="nav-item"><a class="nav-link" href="{% url 'operator:panel' %}"><span class="material-symbols-rounded">swap_horiz</span>Operación</a></li>
          {% else %}
            {% activo "guest:inicio" as a %}<li class="nav-item"><a class="nav-link {{ a }}" href="{% url 'guest:inicio' %}"{% if a %} aria-current="page"{% endif %}><span class="material-symbols-rounded">home</span>Inicio</a></li>
            {% activo "guest:catalogo" "guest:producto" as a %}<li class="nav-item"><a class="nav-link {{ a }}" href="{% url 'guest:catalogo' %}"{% if a %} aria-current="page"{% endif %}><span class="material-symbols-rounded">storefront</span>Productos</a></li>
            {% activo "guest:servicios" "guest:servicio" as a %}<li class="nav-item"><a class="nav-link {{ a }}" href="{% url 'guest:servicios' %}"{% if a %} aria-current="page"{% endif %}><span class="material-symbols-rounded">handyman</span>Servicios</a></li>
          {% endif %}
        </ul>
        <div class="barra-derecha d-flex align-items-center gap-1">
          {% if user.is_authenticated %}
          <a class="btn btn-icono" href="{% if user.is_staff %}{% url 'operator:notificaciones' %}{% else %}{% url 'customer:notificaciones' %}{% endif %}" aria-label="Notificaciones">
            <span class="material-symbols-rounded">notifications</span>
            {% if notificaciones_no_leidas %}<span class="insignia-notificacion">{{ notificaciones_no_leidas }}</span>{% endif %}
          </a>
          {% endif %}
          <button type="button" class="btn btn-icono" data-alternar-tema aria-label="Cambiar a tema oscuro" aria-pressed="false">
            <span class="material-symbols-rounded icono-tema">dark_mode</span>
          </button>
          {% if user.is_authenticated %}
          <div class="dropdown">
            <button class="btn btn-tonal dropdown-toggle" type="button" data-bs-toggle="dropdown" aria-expanded="false">
              <span class="avatar-inicial">{{ user.nombres|slice:":1"|upper }}</span>
              <span class="d-none d-sm-inline">{{ user.nombres }}</span>
            </button>
            <ul class="dropdown-menu dropdown-menu-end">
              <li class="px-3 py-2"><div class="fw-medium">{{ user.nombre_completo }}</div><small class="text-body-secondary">{{ user.correo }}</small></li>
              <li><hr class="dropdown-divider"></li>
              <li><a class="dropdown-item" href="{% if user.is_staff %}{% url 'account_change_password' %}{% else %}{% url 'customer:cuenta' %}{% endif %}"><span class="material-symbols-rounded">person</span>{% if user.is_staff %}Mi cuenta{% else %}Mi perfil{% endif %}</a></li>
              <li><hr class="dropdown-divider"></li>
              <li>
                <form method="post" action="{% url 'account_logout' %}">{% csrf_token %}
                  <button type="submit" class="dropdown-item"><span class="material-symbols-rounded">logout</span>Cerrar sesión</button>
                </form>
              </li>
            </ul>
          </div>
          {% else %}
          <a class="btn btn-primary ms-1" href="{% url 'guest:acceso' %}"><span class="material-symbols-rounded">login</span>Ingresar</a>
          {% endif %}
        </div>
      </div>
    </div>
  </nav>
</header>
{% endwith %}
__FIN__

    escribir_stub "footer.html" <<'__FIN__'
<footer class="pie-pagina">
  <div class="container-xxl py-4 d-flex flex-column flex-md-row justify-content-between align-items-center gap-2">
    <div class="d-flex align-items-center gap-2">
      <span class="material-symbols-rounded icono-marca" aria-hidden="true">deployed_code</span>
      <span>{{ negocio.nombre_negocio|default:"3DForge Studio" }}{% if negocio.correo %} · {{ negocio.correo }}{% endif %}</span>
    </div>
    <nav class="d-flex flex-wrap justify-content-center gap-3 small" aria-label="Enlaces del pie de página">
      <a href="{% url 'guest:catalogo' %}">Productos</a>
      <a href="{% url 'guest:servicios' %}">Servicios</a>
      <a href="{% url 'guest:terminos' %}">Términos y condiciones</a>
    </nav>
  </div>
</footer>
__FIN__

    escribir_stub "mensajes.html" <<'__FIN__'
{% load bootstrap %}
<div id="contenedor-toasts" class="toast-container position-fixed top-0 end-0 p-3" aria-live="polite" aria-atomic="true">
  {% for mensaje in messages %}
  <div class="toast toast-md toast-{{ mensaje.level_tag|tipo_toast }}" role="alert" aria-live="assertive" aria-atomic="true">
    <div class="d-flex align-items-start gap-3 p-3">
      <span class="material-symbols-rounded toast-icono" aria-hidden="true">{{ mensaje.level_tag|icono_toast }}</span>
      <div class="flex-grow-1">
        <strong class="d-block">{{ mensaje.level_tag|titulo_toast }}</strong>
        <span>{{ mensaje }}</span>
      </div>
      <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Cerrar"></button>
    </div>
    <div class="toast-progreso"></div>
  </div>
  {% endfor %}
</div>
__FIN__
}

# ============================================================
# ACCESO Y AUTENTICACION (una pestaña a la vez, tambien al fallar)
# ============================================================

paso_auth() {
    info "Acceso: pestañas ingresar/crear cuenta y paginas de allauth dentro del diseno"

    ir_a "templates/components"
    escribir "campo_auth.html" <<'__FIN__'
<div class="mb-3">
  <label class="form-label" for="{{ id }}">{{ etiqueta }}</label>
  <div class="input-group{% if errores %} has-validation{% endif %}">
    <span class="input-group-text"><span class="material-symbols-rounded" aria-hidden="true">{{ icono }}</span></span>
    <input type="{{ tipo }}" class="form-control{% if errores %} is-invalid{% endif %}" id="{{ id }}" name="{{ nombre }}" value="{{ valor|default:'' }}"{% if autocomplete %} autocomplete="{{ autocomplete }}"{% endif %}{% if requerido %} required{% endif %}{% if maximo %} maxlength="{{ maximo }}"{% endif %}{% if minimo %} minlength="{{ minimo }}"{% endif %}>
    {% if tipo == "password" %}<button type="button" class="btn btn-icono toggle-password" data-objetivo="#{{ id }}" aria-label="Mostrar contraseña"><span class="material-symbols-rounded">visibility</span></button>{% endif %}
    {% if errores %}<div class="invalid-feedback">{{ errores|join:" " }}</div>{% endif %}
  </div>
</div>
__FIN__

    escribir "auth_paneles.html" <<'__FIN__'
{% load socialaccount %}
<div class="auth-contenedor">
  <div class="card auth-tarjeta">
    <div class="card-body p-4 p-md-5">
      <div class="text-center mb-4">
        <span class="material-symbols-rounded icono-marca icono-grande" aria-hidden="true">deployed_code</span>
        <h1 class="h4 mt-2 mb-1">Bienvenido a {{ negocio.nombre_negocio|default:"3DForge Studio" }}</h1>
        <p class="text-body-secondary mb-0">Ingrese o cree su cuenta para comprar, cotizar y dar seguimiento a sus pedidos.</p>
      </div>

      <ul class="nav nav-pills nav-fill auth-pestanas mb-4" role="tablist">
        <li class="nav-item" role="presentation">
          <button class="nav-link{% if pestana != 'registro' %} active{% endif %}" id="tab-login" data-bs-toggle="pill" data-bs-target="#panel-login" type="button" role="tab" aria-controls="panel-login" aria-selected="{% if pestana != 'registro' %}true{% else %}false{% endif %}"><span class="material-symbols-rounded">login</span>Ingresar</button>
        </li>
        <li class="nav-item" role="presentation">
          <button class="nav-link{% if pestana == 'registro' %} active{% endif %}" id="tab-registro" data-bs-toggle="pill" data-bs-target="#panel-registro" type="button" role="tab" aria-controls="panel-registro" aria-selected="{% if pestana == 'registro' %}true{% else %}false{% endif %}"><span class="material-symbols-rounded">person_add</span>Crear cuenta</button>
        </li>
      </ul>

      <div class="tab-content">
        <div class="tab-pane fade{% if pestana != 'registro' %} show active{% endif %}" id="panel-login" role="tabpanel" aria-labelledby="tab-login" tabindex="0">
          <form method="post" action="{% url 'account_login' %}" id="form-ingreso">
            {% csrf_token %}
            {% if siguiente %}<input type="hidden" name="next" value="{{ siguiente }}">{% endif %}
            {% if pestana == "login" and form.non_field_errors %}
            <div class="alert alert-danger d-flex align-items-start gap-2" role="alert"><span class="material-symbols-rounded">error</span><div>{{ form.non_field_errors|join:" " }}</div></div>
            {% endif %}
            {% include "components/campo_auth.html" with etiqueta="Correo electrónico" nombre="login" id="login-correo" tipo="email" icono="mail" valor=form.login.value errores=form.login.errors autocomplete="email" requerido=True %}
            {% include "components/campo_auth.html" with etiqueta="Contraseña" nombre="password" id="login-clave" tipo="password" icono="lock" errores=form.password.errors autocomplete="current-password" requerido=True %}
            <div class="d-flex justify-content-between align-items-center mb-3">
              <div class="form-check mb-0"><input type="checkbox" class="form-check-input" id="login-recordar" name="remember"><label class="form-check-label" for="login-recordar">Recordarme</label></div>
              <a href="{% url 'account_reset_password' %}">¿Olvidó su contraseña?</a>
            </div>
            <button type="submit" class="btn btn-primary w-100 btn-lg">Ingresar</button>
          </form>
        </div>

        <div class="tab-pane fade{% if pestana == 'registro' %} show active{% endif %}" id="panel-registro" role="tabpanel" aria-labelledby="tab-registro" tabindex="0">
          <form method="post" action="{% url 'account_signup' %}" id="form-registro">
            {% csrf_token %}
            {% if siguiente %}<input type="hidden" name="next" value="{{ siguiente }}">{% endif %}
            {% if pestana == "registro" and form.non_field_errors %}
            <div class="alert alert-danger d-flex align-items-start gap-2" role="alert"><span class="material-symbols-rounded">error</span><div>{{ form.non_field_errors|join:" " }}</div></div>
            {% endif %}
            <div class="row g-2">
              <div class="col-sm-6">{% include "components/campo_auth.html" with etiqueta="Nombres" nombre="nombres" id="reg-nombres" tipo="text" icono="badge" valor=form.nombres.value errores=form.nombres.errors requerido=True maximo=100 %}</div>
              <div class="col-sm-6">{% include "components/campo_auth.html" with etiqueta="Apellidos" nombre="apellidos" id="reg-apellidos" tipo="text" icono="badge" valor=form.apellidos.value errores=form.apellidos.errors requerido=True maximo=100 %}</div>
            </div>
            {% include "components/campo_auth.html" with etiqueta="Correo electrónico" nombre="email" id="reg-correo" tipo="email" icono="mail" valor=form.email.value errores=form.email.errors autocomplete="email" requerido=True %}
            {% include "components/campo_auth.html" with etiqueta="Teléfono (opcional)" nombre="telefono" id="reg-telefono" tipo="tel" icono="call" valor=form.telefono.value errores=form.telefono.errors maximo=25 %}
            {% include "components/campo_auth.html" with etiqueta="Contraseña" nombre="password1" id="reg-clave1" tipo="password" icono="lock" errores=form.password1.errors autocomplete="new-password" requerido=True minimo=10 %}
            {% include "components/campo_auth.html" with etiqueta="Confirmar contraseña" nombre="password2" id="reg-clave2" tipo="password" icono="lock_reset" errores=form.password2.errors autocomplete="new-password" requerido=True %}
            <div class="form-check mb-3">
              <input class="form-check-input" type="checkbox" id="reg-terminos" name="terminos" required>
              <label class="form-check-label" for="reg-terminos">Acepto los <a href="{% url 'guest:terminos' %}" target="_blank" rel="noopener">términos y condiciones</a></label>
            </div>
            <button type="submit" class="btn btn-primary w-100 btn-lg">Crear cuenta</button>
          </form>
        </div>
      </div>

      <div class="auth-separador">o continúe con</div>
      <form method="post" action="{% provider_login_url 'google' process='login' %}">
        {% csrf_token %}
        <button type="submit" class="btn btn-outline-secondary w-100"><span class="material-symbols-rounded">account_circle</span>Continuar con Google</button>
      </form>
    </div>
  </div>
</div>
__FIN__

    ir_a "templates/guest"
    escribir_stub "acceso.html" <<'__FIN__'
{% extends "layouts/guest.html" %}

{% block titulo %}Acceso{% endblock %}

{% block contenido %}
{% include "components/auth_paneles.html" %}
{% endblock %}
__FIN__

    ir_a "templates/account"
    escribir "login.html" <<'__FIN__'
{% extends "layouts/guest.html" %}

{% block titulo %}Ingresar{% endblock %}

{% block contenido %}
{% with pestana="login" siguiente=redirect_field_value %}
{% include "components/auth_paneles.html" %}
{% endwith %}
{% endblock %}
__FIN__
    escribir "signup.html" <<'__FIN__'
{% extends "layouts/guest.html" %}

{% block titulo %}Crear cuenta{% endblock %}

{% block contenido %}
{% with pestana="registro" siguiente=redirect_field_value %}
{% include "components/auth_paneles.html" %}
{% endwith %}
{% endblock %}
__FIN__

    ir_a "templates/allauth/layouts"
    escribir "base.html" <<'__FIN__'
{% extends "layouts/guest.html" %}

{% block titulo %}{% block head_title %}{% endblock head_title %}{% endblock %}

{% block estilos %}{% block extra_head %}{% endblock extra_head %}{% endblock %}

{% block contenido %}
<div class="auth-contenido">
  {% block body %}{% block content %}{% endblock content %}{% endblock body %}
</div>
{% endblock %}

{% block scripts %}{% block extra_body %}{% endblock extra_body %}{% endblock %}
__FIN__

    ir_a "apps/portal/guest/views"
    escribir_stub "acceso.py" <<'__FIN__'
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import TemplateView


class AccesoView(TemplateView):
    template_name = "guest/acceso.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("redirigir")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        siguiente = self.request.GET.get("next", "")
        if not url_has_allowed_host_and_scheme(siguiente, {self.request.get_host()}, self.request.is_secure()):
            siguiente = ""
        contexto["siguiente"] = siguiente
        contexto["pestana"] = "registro" if self.request.GET.get("registro") else "login"
        return contexto
__FIN__

    crear_si_falta "terminos.py" <<'__FIN__'
from django.views.generic import TemplateView


class TerminosView(TemplateView):
    template_name = "guest/terminos.html"
__FIN__

    escribir_stub "__init__.py" <<'__FIN__'
from .acceso import AccesoView
from .catalogo import CatalogoView, ProductoDetalleView
from .inicio import InicioView
from .servicios import ServicioDetalleView, ServiciosView
from .terminos import TerminosView
__FIN__

    ir_a "apps/portal/guest"
    escribir_stub "urls.py" <<'__FIN__'
from django.urls import path

from . import views

app_name = "guest"

urlpatterns = [
    path("", views.InicioView.as_view(), name="inicio"),
    path("catalogo/", views.CatalogoView.as_view(), name="catalogo"),
    path("catalogo/<int:pk>/", views.ProductoDetalleView.as_view(), name="producto"),
    path("servicios/", views.ServiciosView.as_view(), name="servicios"),
    path("servicios/<int:pk>/", views.ServicioDetalleView.as_view(), name="servicio"),
    path("acceso/", views.AccesoView.as_view(), name="acceso"),
    path("terminos/", views.TerminosView.as_view(), name="terminos"),
]
__FIN__

    ir_a "static/js/vistas/guest"
    escribir_stub "acceso.js" <<'__FIN__'
$(function () {
    $(".toggle-password").on("click", function () {
        var $campo = $($(this).data("objetivo"));
        var visible = $campo.attr("type") === "text";
        $campo.attr("type", visible ? "password" : "text");
        $(this).find(".material-symbols-rounded").text(visible ? "visibility" : "visibility_off");
        $(this).attr("aria-label", visible ? "Mostrar contraseña" : "Ocultar contraseña");
    });

    $("#form-registro").on("submit", function (evento) {
        var errores = [];
        var clave = $("#reg-clave1").val();
        if (clave.length < 10) { errores.push("La contraseña debe tener al menos 10 caracteres."); }
        if (clave !== $("#reg-clave2").val()) { errores.push("Las contraseñas no coinciden."); }
        if (!$("#reg-terminos").is(":checked")) { errores.push("Debe aceptar los términos y condiciones."); }
        if (errores.length) {
            evento.preventDefault();
            window.Toast.mostrar("warning", errores.join(" "));
        }
    });

    if (window.location.hash === "#registro") {
        bootstrap.Tab.getOrCreateInstance(document.querySelector("#tab-registro")).show();
    }
});
__FIN__
    crear_si_falta "terminos.js" <<'__FIN__'
$(function () {
    console.debug("vista cargada: guest:terminos");
});
__FIN__
}

# ============================================================
# TERMINOS Y CONDICIONES, PAGINAS DE ERROR
# ============================================================

pagina_error() {
    local icono="$1" titulo="$2" mensaje="$3" cabecera="$4"
    printf '{%% load static %%}<!doctype html>\n<html lang="es" data-bs-theme="light">\n<head>\n  <meta charset="utf-8">\n  <meta name="viewport" content="width=device-width, initial-scale=1">\n  <script>\n    (function () {\n      try {\n        var tema = localStorage.getItem("tema");\n        if (!tema) { tema = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"; }\n        document.documentElement.setAttribute("data-bs-theme", tema);\n      } catch (error) {\n        document.documentElement.setAttribute("data-bs-theme", "light");\n      }\n    })();\n  </script>\n  <title>%s</title>\n  <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,0,0&display=block" rel="stylesheet">\n  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">\n  <link href="{%% static '"'"'css/app.css'"'"' %%}" rel="stylesheet">\n</head>\n<body>\n  <main class="container pagina-error contenido-animado">\n    <div class="card auth-tarjeta">\n      <div class="card-body p-4 p-md-5">\n        <span class="material-symbols-rounded icono-xl">%s</span>\n        <p class="text-body-secondary mb-0">%s</p>\n        <h1 class="display-6 mt-2">%s</h1>\n        <p class="lead text-body-secondary">%s</p>\n        <a class="btn btn-primary" href="/"><span class="material-symbols-rounded">home</span>Volver al inicio</a>\n      </div>\n    </div>\n  </main>\n</body>\n</html>\n' \
        "$titulo" "$icono" "$cabecera" "$titulo" "$mensaje"
}

paso_paginas() {
    info "Terminos y condiciones y paginas de error"

    ir_a "templates/guest"
    crear_si_falta "terminos.html" <<'__FIN__'
{% extends "layouts/guest.html" %}

{% block titulo %}Términos y condiciones{% endblock %}

{% block contenido %}
{# Documento de referencia: revisar con asesoría legal antes de publicar. #}
<article class="documento-legal">
  <div class="heroe p-4 p-md-5 mb-4">
    <span class="material-symbols-rounded icono-grande text-primary" aria-hidden="true">gavel</span>
    <h1 class="h2 mt-2">Términos y condiciones de uso</h1>
    <p class="mb-0 text-body-secondary">Última actualización: 9 de noviembre de 2026</p>
  </div>

  <h2>1. Aceptación</h2>
  <p>Al crear una cuenta, navegar o utilizar la plataforma de {{ negocio.nombre_negocio|default:"3DForge Studio" }} usted acepta estos términos. Si no está de acuerdo, le pedimos no utilizar el sitio.</p>

  <h2>2. Servicios y productos</h2>
  <p>Ofrecemos impresión 3D, diseño, modelado, asesorías, prototipado y productos preimpresos. Las descripciones, imágenes y existencias son referenciales y pueden cambiar sin previo aviso.</p>

  <h2>3. Cuenta de usuario</h2>
  <ul>
    <li>Debe proporcionar información veraz y mantenerla actualizada.</li>
    <li>Es responsable de la confidencialidad de su contraseña y de la actividad de su cuenta.</li>
    <li>Podemos suspender cuentas que incumplan estos términos o comprometan la seguridad de la plataforma.</li>
  </ul>

  <h2>4. Cotizaciones y pedidos</h2>
  <p>Las cotizaciones tienen una vigencia limitada indicada en cada propuesta. Un pedido se considera confirmado cuando el cliente acepta la cotización o confirma la compra en la tienda. Los plazos de entrega son estimados.</p>

  <h2>5. Precios, impuestos y pagos</h2>
  <p>Los precios se expresan en dólares estadounidenses e incluyen o detallan los impuestos aplicables. Los pagos se coordinan con nuestro equipo y se registran en la plataforma. Las facturas indican su fecha de vencimiento y saldo.</p>

  <h2>6. Archivos y propiedad intelectual</h2>
  <p>Al subir archivos (modelos, imágenes, documentos) usted declara contar con los derechos necesarios sobre ellos y nos autoriza a utilizarlos únicamente para atender su solicitud. No fabricaremos piezas que infrinjan derechos de terceros o que estén prohibidas por la ley.</p>

  <h2>7. Cancelaciones</h2>
  <p>Puede cancelar un pedido mientras se encuentre pendiente. Una vez aprobado o en producción, la cancelación depende del avance del trabajo y debe acordarse con el equipo.</p>

  <h2>8. Datos personales</h2>
  <p>Usamos sus datos para gestionar su cuenta, cotizaciones, pedidos, facturación y comunicaciones sobre su actividad. No los compartimos con terceros salvo obligación legal o proveedores necesarios para prestar el servicio.</p>

  <h2>9. Uso aceptable</h2>
  <p>Queda prohibido intentar acceder a información de otros usuarios, interferir con el funcionamiento del sitio o utilizar la plataforma con fines ilícitos.</p>

  <h2>10. Limitación de responsabilidad</h2>
  <p>Nos esforzamos por la calidad de cada trabajo; sin embargo, no respondemos por daños indirectos derivados del uso de las piezas fuera de las especificaciones acordadas.</p>

  <h2>11. Cambios en los términos</h2>
  <p>Podemos actualizar estos términos. La versión vigente es la publicada en esta página.</p>

  <h2>12. Contacto</h2>
  <p>Para consultas escriba a {% if negocio.correo %}<a href="mailto:{{ negocio.correo }}">{{ negocio.correo }}</a>{% else %}nuestro equipo mediante la sección de soporte{% endif %}.</p>
</article>
{% endblock %}
__FIN__

    ir_a "templates"
    pagina_error "lock" "Acceso denegado" "No tiene permisos para ver esta página." "Error 403" | escribir_stub "403.html"
    pagina_error "search_off" "Página no encontrada" "La dirección no existe o fue movida." "Error 404" | escribir_stub "404.html"
    pagina_error "cloud_off" "Algo salió mal" "Ocurrió un error en el servidor. Intente nuevamente en unos minutos." "Error 500" | escribir_stub "500.html"

    ir_a "templates/errors"
    pagina_error "gpp_maybe" "Acceso bloqueado temporalmente" "Se superó el número de intentos permitidos. Intente nuevamente más tarde." "Seguridad" | escribir_stub "bloqueado.html"
}

# ============================================================
# PRUEBAS
# ============================================================

paso_pruebas() {
    info "Pruebas del sistema de diseno"
    ir_a "apps/portal/tests"
    crear_si_falta "test_diseno.py" <<'__FIN__'
import re
from pathlib import Path

from django.conf import settings
from django.contrib.messages.storage.base import Message
from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse

from apps.usuarios.constants import GRUPO_ADMINISTRADOR, GRUPO_CLIENTE, GRUPO_OPERADOR
from apps.usuarios.tests.utiles import crear_usuario, iniciar_sesion


class LayoutTests(TestCase):
    def test_layout_incluye_tema_iconos_y_css_global(self):
        respuesta = self.client.get(reverse("guest:inicio"))
        for texto in ("localStorage.getItem", "Material+Symbols+Rounded", "css/app.css", "data-alternar-tema", "js/components/tema.js"):
            self.assertContains(respuesta, texto)
        self.assertNotIn(" style=", respuesta.content.decode())

    def test_alternador_de_tema_en_cada_pantalla(self):
        paginas = {
            None: ["guest:inicio", "guest:catalogo", "guest:servicios", "guest:acceso", "guest:terminos"],
            GRUPO_CLIENTE: ["customer:panel", "customer:tienda", "customer:cuenta"],
            GRUPO_OPERADOR: ["operator:panel", "operator:cotizaciones"],
            GRUPO_ADMINISTRADOR: ["administrator:dashboard", "administrator:usuarios", "administrator:ventas"],
        }
        for indice, (rol, nombres) in enumerate(paginas.items()):
            if rol:
                self.client.logout()
                iniciar_sesion(self.client, crear_usuario(f"ui{indice}@example.com", rol, is_staff=rol != GRUPO_CLIENTE))
            for nombre in nombres:
                respuesta = self.client.get(reverse(nombre))
                self.assertEqual(respuesta.status_code, 200, nombre)
                self.assertContains(respuesta, "data-alternar-tema", msg_prefix=nombre)

    def test_terminos_y_enlace_en_el_pie(self):
        respuesta = self.client.get(reverse("guest:terminos"))
        self.assertContains(respuesta, "Términos y condiciones de uso")
        self.assertContains(self.client.get(reverse("guest:inicio")), reverse("guest:terminos"))

    def test_css_define_ambas_paletas_y_la_fuente(self):
        css = (Path(settings.BASE_DIR) / "static" / "css" / "app.css").read_text(encoding="utf-8")
        for texto in ("#167C80", "#11666A", "#D5F0ED", "#65D4CE", "#101819", "family=Roboto", '[data-bs-theme="dark"]'):
            self.assertIn(texto, css)
        self.assertTrue((Path(settings.BASE_DIR) / "static" / "js" / "vistas" / "guest" / "terminos.js").exists())


class BarraTests(TestCase):
    def test_menu_de_usuario_del_cliente(self):
        usuario = crear_usuario("cliente@example.com", GRUPO_CLIENTE)
        iniciar_sesion(self.client, usuario)
        respuesta = self.client.get(reverse("customer:panel"))
        for texto in ("Cerrar sesión", "Mi perfil", reverse("customer:cuenta"), usuario.nombres, "data-bs-toggle=\"dropdown\""):
            self.assertContains(respuesta, texto)

    def test_menu_de_usuario_del_personal(self):
        iniciar_sesion(self.client, crear_usuario("op@example.com", GRUPO_OPERADOR, is_staff=True))
        respuesta = self.client.get(reverse("operator:panel"))
        self.assertContains(respuesta, "Mi cuenta")
        self.assertContains(respuesta, reverse("account_change_password"))

    def test_ruta_activa_resaltada(self):
        iniciar_sesion(self.client, crear_usuario("cliente2@example.com", GRUPO_CLIENTE))
        contenido = self.client.get(reverse("customer:tienda")).content.decode()
        self.assertIn(f'nav-link active" href="{reverse("customer:tienda")}"', contenido)
        self.assertNotIn(f'nav-link active" href="{reverse("customer:pedidos")}"', contenido)

    def test_visitante_ve_ingresar_y_no_el_menu_de_usuario(self):
        contenido = self.client.get(reverse("guest:inicio")).content.decode()
        self.assertIn(reverse("guest:acceso"), contenido)
        self.assertNotIn("Cerrar sesión", contenido)


class ToastsTests(TestCase):
    def test_los_cuatro_tipos_con_su_icono(self):
        html = render_to_string(
            "components/mensajes.html",
            {"messages": [Message(25, "ok"), Message(40, "falla"), Message(30, "cuidado"), Message(20, "dato")]},
        )
        for clase, icono in (("toast-success", "check_circle"), ("toast-error", "error"), ("toast-warning", "warning"), ("toast-info", "info")):
            self.assertIn(clase, html)
            self.assertIn(f'aria-hidden="true">{icono}</span>', html)
        self.assertIn("toast-progreso", html)

    def test_un_mensaje_de_negocio_se_muestra_como_toast(self):
        iniciar_sesion(self.client, crear_usuario("toast@example.com", GRUPO_CLIENTE))
        respuesta = self.client.post(reverse("customer:carrito_agregar", args=[999999]), {"cantidad": "1"}, follow=True)
        self.assertContains(respuesta, "toast-error")


class AutenticacionTests(TestCase):
    def activa(self, contenido):
        return re.findall(r'tab-pane fade show active" id="(panel-[a-z]+)"', contenido)

    def test_acceso_muestra_una_sola_pestana(self):
        self.assertEqual(self.activa(self.client.get(reverse("guest:acceso")).content.decode()), ["panel-login"])
        self.assertEqual(self.activa(self.client.get(reverse("guest:acceso"), {"registro": "1"}).content.decode()), ["panel-registro"])

    def test_login_fallido_mantiene_el_diseno_y_el_error(self):
        respuesta = self.client.post(reverse("account_login"), {"login": "nadie@example.com", "password": "incorrecta"})
        self.assertEqual(respuesta.status_code, 200)
        contenido = respuesta.content.decode()
        for texto in ("bootstrap.min.css", "css/app.css", "auth-tarjeta", "alert-danger", "data-alternar-tema"):
            self.assertIn(texto, contenido)
        self.assertEqual(self.activa(contenido), ["panel-login"])
        self.assertIn("nadie@example.com", contenido)

    def test_registro_con_errores_reabre_la_pestana_de_registro(self):
        datos = {"nombres": "Luis", "apellidos": "Pérez", "email": "luis.ui@example.com", "telefono": "", "password1": "Clave-Segura-123", "password2": "distinta"}
        respuesta = self.client.post(reverse("account_signup"), datos)
        self.assertEqual(respuesta.status_code, 200)
        contenido = respuesta.content.decode()
        self.assertEqual(self.activa(contenido), ["panel-registro"])
        self.assertIn("is-invalid", contenido)
        self.assertIn("luis.ui@example.com", contenido)

    def test_paginas_de_allauth_usan_el_layout(self):
        respuesta = self.client.get(reverse("account_reset_password"))
        self.assertEqual(respuesta.status_code, 200)
        for texto in ("css/app.css", "data-alternar-tema", "auth-contenido"):
            self.assertContains(respuesta, texto)

    def test_paginas_de_error_usan_el_diseno(self):
        respuesta = self.client.get("/ruta/que/no/existe/")
        self.assertEqual(respuesta.status_code, 404)
        self.assertContains(respuesta, "css/app.css", status_code=404)
__FIN__
}

paso_tasklist() {
    ir_raiz
    [[ -f TASKLIST_USUARIO.txt ]] || return 0
    inyectar_bloque "TASKLIST_USUARIO.txt" "ui-1" <<'__FIN__'

=== N. UI-1: SISTEMA DE DISEÑO (generar-ui1.sh) ===
Requiere internet en el navegador (Roboto, Material Symbols, Bootstrap, jQuery).
[ ] N1. python manage.py test   (envieme el resumen). No hay migraciones nuevas.
[ ] N2. Haga Ctrl+F5 (cache del navegador) y recorra guest, acceso, cliente, operador y
        administrador: fuente Roboto, iconos visibles (si aparece texto como "dark_mode",
        la fuente de iconos no cargo: revise la conexion).
[ ] N3. Tema: boton luna/sol en la barra de TODAS las pantallas (tambien acceso y terminos);
        recarga conserva el tema; sin parpadeo blanco al recargar en oscuro; sin tema guardado
        sigue el del sistema. Revise graficos del dashboard en oscuro (colores legibles).
[ ] N4. Barra: rutas centradas; a la derecha notificaciones (con contador), tema y menu de
        usuario (Mi perfil / Mi cuenta y Cerrar sesion); ruta activa en color de marca;
        en movil se colapsa en el boton de menu.
[ ] N5. Acceso: una sola pestaña visible; provoque un login fallido y un registro con errores
        (contraseñas distintas): la pantalla vuelve con estilo y en la pestaña correcta.
[ ] N6. Paginas de allauth (olvido de contraseña, enlace de correo, cambiar contraseña):
        dentro del diseño. Si alguna se ve rara, mandeme una captura y la reviso.
[ ] N7. Toasts: exito, error, advertencia (amarillo) e informacion (azul) con su icono. Para
        ver los dos ultimos, en la consola del navegador: Toast.mostrar("warning","prueba")
        y Toast.mostrar("info","prueba").
[ ] N8. Terminos y condiciones (/terminos/): enlazados en el pie y en el registro. Revise el
        texto con asesoria legal antes de publicar.
[ ] N9. Paginas de error 403/404 (por ejemplo /ruta-inexistente/) con el nuevo diseño.
[ ] N10. Animaciones sutiles: contenido que aparece suave, tarjetas que se elevan al pasar el
         mouse. Con "reducir movimiento" activado en el sistema operativo no deben animarse.
[ ] N11. Pendiente para UI-2 (siguiente script): tarjetas de producto, tablas con botones de
         accion (Ver/Editar), formularios de encargos en vertical, perfil con foto (9C) y pulido
         de paneles. Anote aqui lo que vea mejorable.
__FIN__
}

paso_verificacion() {
    ir_raiz
    local py="python3" estilos
    if [[ -x "$RAIZ/.venv/bin/python" ]]; then
        py="$RAIZ/.venv/bin/python"
    elif [[ -x "$RAIZ/.venv/Scripts/python.exe" ]]; then
        py="$RAIZ/.venv/Scripts/python.exe"
    elif [[ -n ${VIRTUAL_ENV:-} && -x "$VIRTUAL_ENV/bin/python" ]]; then
        py="$VIRTUAL_ENV/bin/python"
    fi
    info "Verificando sintaxis y plantillas"
    if "$py" -m compileall -q apps config >/dev/null; then
        ok "Sintaxis correcta"
    else
        advertir "Errores de sintaxis: $py -m compileall apps config"
        return 0
    fi
    estilos="$(grep -rlE ' style=|<style' templates 2>/dev/null | tr '\n' ' ' || true)"
    if [[ -n $estilos ]]; then
        advertir "Plantillas con style embebido: $estilos"
    else
        ok "Ninguna plantilla usa style embebido"
    fi
    [[ -f .env ]] || return 0
    if "$py" -c "import django" >/dev/null 2>&1; then
        "$py" manage.py check >/dev/null 2>&1 && ok "manage.py check sin problemas" \
            || advertir "manage.py check reporto problemas; ejecutelo para ver el detalle."
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
    echo "Siguiente: Ctrl+F5 en el navegador, python manage.py test y la seccion N de TASKLIST_USUARIO.txt."
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

    paso_etiquetas
    paso_css
    paso_js_comun
    paso_layouts
    paso_auth
    paso_paginas
    paso_pruebas
    paso_tasklist
    paso_verificacion
    resumen
}

main "$@"
