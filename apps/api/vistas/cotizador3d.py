import time

from django.core.cache import cache
from django.core.exceptions import ValidationError

from apps.api.autenticacion import api
from apps.api.respuestas import ErrorAPI, exito, fallo_formulario
from apps.api.vistas.cotizaciones import _detalle
from apps.core.constants import MAX_ARCHIVO_BYTES
from apps.core.utiles import mensaje_de
from apps.cotizaciones.forms.automatica import (
    EXTENSIONES_3D,
    Cotizacion3DForm,
    OpcionesEstimacionForm,
    validar_modelo_3d,
)
from apps.cotizaciones.modelos3d.analisis import analisis_desde_json, analizar_archivo
from apps.cotizaciones.modelos3d.errores import ErrorAnalisis
from apps.cotizaciones.modelos3d.estimacion import (
    AVISO,
    CALIDADES,
    ESCALAS,
    ETIQUETAS_UNIDADES,
    RELLENOS,
    SOPORTES,
    a_json,
    estimar,
)
from apps.cotizaciones.models import ConfiguracionCotizador
from apps.cotizaciones.selectors.automatica import filamentos_activos
from apps.cotizaciones.services import automatica
from apps.cotizaciones.services import cotizaciones as servicios

LIMITE_ANALISIS_POR_MINUTO = 20


def _limitar_analisis(usuario):
    """Como en la web: cada analisis de un archivo cuenta; recalcular con el analisis ya hecho no."""
    clave = f"api:cotizador3d:{usuario.pk}:{int(time.time() // 60)}"
    cache.add(clave, 0, 120)
    try:
        usados = cache.incr(clave)
    except ValueError:
        cache.set(clave, 1, 120)
        usados = 1
    if usados > LIMITE_ANALISIS_POR_MINUTO:
        raise ErrorAPI("Demasiados análisis seguidos. Espere un minuto.", "limite_excedido", 429)


@api(("GET",))
def opciones_3d(request):
    """Opciones del cotizador automatico para armar el formulario de la app sin valores fijos."""
    parametros = ConfiguracionCotizador.obtener()
    filamentos = [
        {"id": f.pk, "material": f.material, "color": f.color, "nombre": f"{f.material} {f.color}"}
        for f in filamentos_activos()
    ]
    return exito(
        {
            "disponible": bool(filamentos),
            "filamentos": filamentos,
            "rellenos": list(RELLENOS),
            "calidades": [{"codigo": clave, "texto": datos["texto"]} for clave, datos in CALIDADES.items()],
            "escalas": list(ESCALAS),
            "unidades": [{"codigo": clave, "texto": texto} for clave, texto in ETIQUETAS_UNIDADES.items()],
            "soportes": [{"codigo": clave, "texto": texto} for clave, texto in SOPORTES.items()],
            "cantidad_maxima": 50,
            "formatos": list(EXTENSIONES_3D),
            "tamano_maximo_mb": int(MAX_ARCHIVO_BYTES // (1024 * 1024)),
            "cama_mm": [float(parametros.cama_x_mm), float(parametros.cama_y_mm), float(parametros.cama_z_mm)],
            "aviso": AVISO,
        }
    )


@api(("POST",))
def estimar_3d(request):
    """Estimacion sin guardar nada. multipart: opciones + `archivo` (primera vez) o `analisis` (JSON devuelto antes)."""
    formulario = OpcionesEstimacionForm(request.POST)
    if not formulario.is_valid():
        return fallo_formulario(formulario)
    parametros = ConfiguracionCotizador.obtener()
    archivo = request.FILES.get("archivo")
    try:
        if archivo is not None:
            _limitar_analisis(request.usuario)
            validar_modelo_3d(archivo)
            analisis = analizar_archivo(archivo, parametros.max_triangulos)
        else:
            analisis = analisis_desde_json(request.POST.get("analisis"))
    except ValidationError as error:
        raise ErrorAPI(mensaje_de(error), "archivo_invalido", 400)
    except ErrorAnalisis as error:
        raise ErrorAPI(str(error), "analisis_invalido", 400)
    resultado = estimar(analisis, formulario.cleaned_data["filamento"], formulario.opciones(), parametros)
    return exito({"analisis": analisis, "estimacion": a_json(resultado)})


@api(("POST",))
def solicitar_3d(request):
    """Crea la cotizacion normal (SOLICITADA, importes preliminares) igual que la web. multipart: opciones + archivo."""
    formulario = Cotizacion3DForm(request.POST, request.FILES)
    if not formulario.is_valid():
        return fallo_formulario(formulario)
    _limitar_analisis(request.usuario)
    try:
        cotizacion = automatica.solicitar_cotizacion_automatica(
            cliente=request.cliente,
            usuario=request.usuario,
            archivo=formulario.cleaned_data["archivo"],
            opciones=formulario.opciones(),
            descripcion=formulario.cleaned_data["descripcion"],
            comentarios=formulario.cleaned_data["comentarios"],
        )
    except (servicios.ErrorCotizacion, ValidationError) as error:
        raise ErrorAPI(mensaje_de(error), "cotizacion_invalida", 400)
    return exito(_detalle(request.cliente, cotizacion.pk), 201)
