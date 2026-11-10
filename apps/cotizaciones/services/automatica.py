from decimal import Decimal

from django.db import transaction

from apps.catalogo.models import CategoriaServicio, Servicio
from apps.core.archivos import nombre_seguro
from apps.cotizaciones.modelos3d.analisis import analizar_archivo
from apps.cotizaciones.modelos3d.errores import ErrorAnalisis
from apps.cotizaciones.modelos3d.estimacion import AVISO, especificaciones_de, estimar
from apps.cotizaciones.models import ConfiguracionCotizador
from apps.cotizaciones.services.cotizaciones import ErrorCotizacion, solicitar_cotizacion

NOMBRE_CATEGORIA = "Impresión 3D"
NOMBRE_SERVICIO = "Impresión 3D (cotización automática)"


def servicio_cotizador():
    """Servicio interno al que se asocian las cotizaciones automaticas (inactivo: no se ofrece en el formulario manual)."""
    categoria, _ = CategoriaServicio.objects.get_or_create(
        nombre=NOMBRE_CATEGORIA, defaults={"descripcion": "Servicios de impresión 3D"}
    )
    servicio, _ = Servicio.objects.get_or_create(
        nombre=NOMBRE_SERVICIO,
        defaults={
            "categoria": categoria,
            "descripcion": "Servicio interno del cotizador automático de impresión 3D. No activar.",
            "precio_base": Decimal("0"),
            "requiere_archivo": True,
            "activo": False,
        },
    )
    return servicio


@transaction.atomic
def solicitar_cotizacion_automatica(cliente, usuario, archivo, opciones, descripcion="", comentarios=""):
    """Analiza el modelo, estima el precio y crea una cotizacion normal (Solicitada) con importes preliminares."""
    parametros = ConfiguracionCotizador.obtener()
    try:
        analisis = analizar_archivo(archivo, parametros.max_triangulos)
    except ErrorAnalisis as error:
        raise ErrorCotizacion(str(error)) from error
    resultado = estimar(analisis, opciones["filamento"], opciones, parametros)
    if not resultado["cabe"]:
        raise ErrorCotizacion(resultado["mensaje_cabida"])

    nombre_pieza = (descripcion or "").strip() or nombre_seguro(archivo.name).rsplit(".", 1)[0] or "Pieza 3D"
    partes = [
        "Cotización automática de impresión 3D.",
        f"Archivo: {nombre_seguro(archivo.name)}",
        f"Estimación del sistema: {resultado['gramos']} g de filamento, {resultado['tiempo_texto']} de impresión.",
        AVISO,
    ]
    if (comentarios or "").strip():
        partes.insert(2, f"Comentarios del cliente: {comentarios.strip()}")
    return solicitar_cotizacion(
        cliente=cliente,
        usuario=usuario,
        servicio=servicio_cotizador(),
        cantidad=Decimal(resultado["cantidad"]),
        descripcion=f"Impresión 3D: {nombre_pieza}",
        solicitud="\n".join(partes),
        especificaciones=especificaciones_de(resultado, opciones),
        archivos=[archivo],
        precio_unitario=resultado["precio_unitario"],
        verificar_servicio=False,
    )
