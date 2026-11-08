
#!/usr/bin/env bash

set -Eeuo pipefail

# ============================================================
# INSPECTOR UNIVERSAL DE PROYECTOS
# Compatible con proyectos de cualquier lenguaje o framework.
# ============================================================

# ---------------------- CONFIGURACIÓN -----------------------

readonly NOMBRE_SALIDA="project-context.txt"

# Tamaño máximo por archivo: 1 MB por defecto.
# Se puede modificar mediante la variable MAX_FILE_SIZE.
MAX_FILE_SIZE="${MAX_FILE_SIZE:-1048576}"

# Directorios que normalmente contienen dependencias,
# archivos temporales, cachés o resultados de compilación.
readonly -a EXCLUDE_DIRS=(
    ".git"
    ".svn"
    ".hg"
    "node_modules"
    "vendor"
    ".venv"
    "venv"
    "__pycache__"
    ".pytest_cache"
    ".mypy_cache"
    ".ruff_cache"
    ".tox"
    ".cache"
    ".idea"
    ".vscode"
    ".angular"
    ".next"
    ".nuxt"
    ".svelte-kit"
    ".turbo"
    ".gradle"
    ".terraform"
    ".dart_tool"
    "Pods"
    "DerivedData"
    "coverage"
    "dist"
    "build"
    "target"
    "out"
    "bin"
    "obj"
)

# Patrones de archivos que pueden contener información sensible.
readonly -a SENSITIVE_PATTERNS=(
    ".env"
    ".env.*"
    "*.pem"
    "*.key"
    "*.p12"
    "*.pfx"
    "id_rsa*"
    "id_ed25519*"
    ".netrc"
    ".npmrc"
    ".pypirc"
    "credentials.json"
    "*credentials*.json"
    "*secrets*.json"
    "*.tfstate"
    "*.tfstate.backup"
)

# ---------------------- ARGUMENTOS --------------------------

mostrar_ayuda() {
    cat <<'EOF'
INSPECTOR UNIVERSAL DE PROYECTOS

Uso:
  ./inspeccionar-proyecto.sh [DIRECTORIO] [ARCHIVO_SALIDA]

Ejemplos:
  ./inspeccionar-proyecto.sh
  ./inspeccionar-proyecto.sh ./backend
  ./inspeccionar-proyecto.sh ./backend informe.txt
  ./inspeccionar-proyecto.sh ~/Projects/mi-proyecto ~/Documents/informe.txt

Variables de entorno:
  MAX_FILE_SIZE=2097152

La variable MAX_FILE_SIZE permite modificar el tamaño máximo
de cada archivo que se incorporará al informe (en bytes).

EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    mostrar_ayuda
    exit 0
fi

if (( $# > 2 )); then
    echo "[ERROR] Número de argumentos incorrecto."
    mostrar_ayuda
    exit 1
fi

# ---------------------- VALIDACIONES ------------------------

if [[ ! "$MAX_FILE_SIZE" =~ ^[0-9]+$ ]] || (( MAX_FILE_SIZE < 1 )); then
    echo "[ERROR] MAX_FILE_SIZE debe ser un entero positivo."
    exit 1
fi

DIRECTORIO="${1:-.}"
SALIDA="${2:-$NOMBRE_SALIDA}"

if [[ ! -d "$DIRECTORIO" ]]; then
    echo "[ERROR] El directorio indicado no existe: $DIRECTORIO"
    exit 1
fi

ROOT="$(cd -- "$DIRECTORIO" && pwd -P)"

# Resolver la ruta de salida.
if [[ "$SALIDA" != /* ]]; then
    SALIDA="$ROOT/$SALIDA"
fi

DIRECTORIO_SALIDA="$(dirname -- "$SALIDA")"
NOMBRE_ARCHIVO="$(basename -- "$SALIDA")"

mkdir -p -- "$DIRECTORIO_SALIDA"

DIRECTORIO_SALIDA="$(cd -- "$DIRECTORIO_SALIDA" && pwd -P)"
SALIDA="$DIRECTORIO_SALIDA/$NOMBRE_ARCHIVO"

if [[ "$SALIDA" == "$ROOT" ]]; then
    echo "[ERROR] La ruta de salida no puede ser un directorio."
    exit 1
fi

if [[ -d "$SALIDA" ]]; then
    echo "[ERROR] La ruta de salida corresponde a un directorio."
    exit 1
fi

# ---------------------- FUNCIONES ---------------------------

es_archivo_sensible() {
    local nombre
    nombre="$(basename -- "$1")"

    for patron in "${SENSITIVE_PATTERNS[@]}"; do
        if [[ "$nombre" == $patron ]]; then
            return 0
        fi
    done

    return 1
}

buscar_elementos() {
    local -a argumentos

    argumentos=("$ROOT" "(" -type d "(")

    for directorio in "${EXCLUDE_DIRS[@]}"; do
        argumentos+=(-name "$directorio" -o)
    done

    # -false evita dejar un -o al final de la expresión.
    argumentos+=(
        -false
        ")"
        -prune
        ")"
        -o
        "("
        -type f
        -o
        -type d
        ")"
        -print0
    )

    find "${argumentos[@]}"
}

obtener_ruta_relativa() {
    local ruta="$1"

    if [[ "$ROOT" == "/" ]]; then
        printf '%s' "${ruta#/}"
    else
        printf '%s' "${ruta#"$ROOT"/}"
    fi
}

es_archivo_texto() {
    local archivo="$1"

    # Los archivos vacíos también son válidos.
    [[ ! -s "$archivo" ]] && return 0

    # grep -Iq permite detectar contenido binario habitual.
    grep -Iq . "$archivo"
}

# ---------------------- INICIALIZACIÓN ----------------------

echo
echo "============================================================"
echo "             INSPECTOR UNIVERSAL DE PROYECTOS"
echo "============================================================"
echo
echo "Directorio raíz : $ROOT"
echo "Archivo salida  : $SALIDA"
echo "Límite por archivo: $MAX_FILE_SIZE bytes"
echo

if [[ -e "$SALIDA" && ! -w "$SALIDA" ]]; then
    echo "[ERROR] No tienes permisos para sobrescribir el informe."
    exit 1
fi

echo "[INFO] Explorando directorios y archivos..."

mapfile -d '' -t ELEMENTOS < <(
    buscar_elementos | LC_ALL=C sort -z
)

# ---------------------- GENERACIÓN --------------------------

TOTAL_ARCHIVOS=0
ARCHIVOS_INCLUIDOS=0
ARCHIVOS_OMITIDOS=0

{
    echo "============================================================"
    echo "              INFORME DEL PROYECTO"
    echo "============================================================"
    echo
    echo "Directorio raíz: $ROOT"
    echo "Fecha: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "Límite por archivo: $MAX_FILE_SIZE bytes"
    echo

    # ========================================================
    # 1. ESTRUCTURA DEL PROYECTO
    # ========================================================

    echo "============================================================"
    echo " 1. ESTRUCTURA DE DIRECTORIOS Y ARCHIVOS"
    echo "============================================================"
    echo

    printf '[ROOT] %s/\n' "$(basename -- "$ROOT")"

    for elemento in "${ELEMENTOS[@]}"; do

        [[ "$elemento" == "$ROOT" ]] && continue
        [[ "$elemento" == "$SALIDA" ]] && continue

        relativo="$(obtener_ruta_relativa "$elemento")"

        separadores="${relativo//[^\/]/}"
        nivel="${#separadores}"

        if [[ -d "$elemento" ]]; then
            printf '%*s[DIR]  %s/\n' \
                "$((nivel * 4))" "" \
                "$(basename -- "$elemento")"

        elif [[ -f "$elemento" ]]; then
            printf '%*s[FILE] %s\n' \
                "$((nivel * 4))" "" \
                "$(basename -- "$elemento")"
        fi
    done

    echo

    # ========================================================
    # 2. CONTENIDO DE LOS ARCHIVOS
    # ========================================================

    echo "============================================================"
    echo " 2. CONTENIDO DE LOS ARCHIVOS"
    echo "============================================================"
    echo

    for elemento in "${ELEMENTOS[@]}"; do

        [[ ! -f "$elemento" ]] && continue
        [[ "$elemento" == "$SALIDA" ]] && continue

        ((TOTAL_ARCHIVOS += 1))

        relativo="$(obtener_ruta_relativa "$elemento")"

        echo "============================================================"
        echo "ARCHIVO: $relativo"
        echo "============================================================"
        echo

        # Comprobar información sensible.
        if es_archivo_sensible "$elemento"; then
            echo "[ARCHIVO OMITIDO: posible información sensible]"
            ((ARCHIVOS_OMITIDOS += 1))
            echo
            continue
        fi

        # Comprobar tamaño.
        tamano="$(wc -c < "$elemento")"

        if (( tamano > MAX_FILE_SIZE )); then
            echo "[ARCHIVO OMITIDO: supera el límite permitido]"
            echo "Tamaño: $tamano bytes"
            ((ARCHIVOS_OMITIDOS += 1))
            echo
            continue
        fi

        # Comprobar contenido binario.
        if ! es_archivo_texto "$elemento"; then
            echo "[ARCHIVO OMITIDO: contenido binario]"
            ((ARCHIVOS_OMITIDOS += 1))
            echo
            continue
        fi

        # Incorporar contenido.
        if [[ -s "$elemento" ]]; then
            cat -- "$elemento"
        else
            echo "[Archivo vacío]"
        fi

        ((ARCHIVOS_INCLUIDOS += 1))

        echo
        echo
    done

    # ========================================================
    # 3. RESUMEN
    # ========================================================

    echo "============================================================"
    echo " 3. RESUMEN DE LA INSPECCIÓN"
    echo "============================================================"
    echo
    echo "Archivos encontrados: $TOTAL_ARCHIVOS"
    echo "Archivos incluidos:   $ARCHIVOS_INCLUIDOS"
    echo "Archivos omitidos:    $ARCHIVOS_OMITIDOS"
    echo

} > "$SALIDA"

# ---------------------- FINALIZACIÓN ------------------------

echo "[OK] Inspección completada."
echo
echo "Archivos encontrados: $TOTAL_ARCHIVOS"
echo "Archivos incluidos:   $ARCHIVOS_INCLUIDOS"
echo "Archivos omitidos:    $ARCHIVOS_OMITIDOS"
echo
echo "Informe generado:"
echo "$SALIDA"
echo
du -h -- "$SALIDA"
echo
echo "============================================================"
