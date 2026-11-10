import math
from decimal import Decimal

from apps.core.calculos import calcular_linea, redondear

CALIDADES = {
    "borrador": {"altura": 0.28, "flujo": 1.3, "texto": "Borrador (0.28 mm)"},
    "estandar": {"altura": 0.20, "flujo": 1.0, "texto": "Estándar (0.20 mm)"},
    "fina": {"altura": 0.12, "flujo": 0.6, "texto": "Fina (0.12 mm)"},
}
RELLENOS = (10, 15, 20, 30, 50, 100)
ESCALAS = (50, 75, 100, 125, 150, 200)
UNIDADES = {"mm": 1.0, "cm": 10.0, "in": 25.4}
ETIQUETAS_UNIDADES = {"mm": "Milímetros (mm)", "cm": "Centímetros (cm)", "in": "Pulgadas (in)"}
SOPORTES = {"auto": "Automático", "si": "Sí", "no": "No"}
CONFIANZA = {"alta": "Alta", "media": "Media", "baja": "Baja"}
ORDEN_CONFIANZA = ("alta", "media", "baja")
AVISO = (
    "Las cotizaciones automáticas son aproximadas, lo más exactas posible. "
    "Cuando un profesional revise su solicitud confirmará el precio final."
)
ETIQUETA_AUTOMATICA = "Cotización automática 3D"


def _decimal(valor):
    return Decimal(str(valor))


def _peor(actual, nueva):
    return max(actual, nueva, key=ORDEN_CONFIANZA.index)


def _cabe(extents, cama):
    x, y, z = extents
    cama_x, cama_y, cama_z = cama
    return z <= cama_z and ((x <= cama_x and y <= cama_y) or (y <= cama_x and x <= cama_y))


def texto_tiempo(horas):
    minutos = max(1, round(horas * 60))
    h, m = divmod(minutos, 60)
    if h and m:
        return f"{h} h {m} min"
    return f"{h} h" if h else f"{m} min"


def estimar(analisis, filamento, opciones, p):
    """Estima material, tiempo y precio. Aproximado a proposito: pensado para una pre-cotizacion que revisa un operador."""
    factor = (opciones["escala"] / 100) * UNIDADES[opciones["unidades"]]
    extents = [float(valor) * factor for valor in analisis["extents_mm"]]
    cama = (float(p.cama_x_mm), float(p.cama_y_mm), float(p.cama_z_mm))
    advertencias = []
    confianza = "alta"

    cabe = _cabe(extents, cama)
    dimensiones_texto = " × ".join(f"{valor:.1f}" for valor in extents) + " mm"
    mensaje_cabida = ""
    if not cabe:
        mensaje_cabida = (
            f"La pieza ({dimensiones_texto}) no cabe en la impresora "
            f"({cama[0]:.0f} × {cama[1]:.0f} × {cama[2]:.0f} mm). Reduzca la escala o solicite una cotización manual."
        )
        advertencias.append(mensaje_cabida)

    hermetica = bool(analisis.get("hermetica") or analisis.get("reparada"))
    volumen_malla = float(analisis.get("volumen_mm3") or 0)
    if hermetica and volumen_malla > 0:
        volumen = volumen_malla * factor**3
        if analisis.get("reparada"):
            confianza = _peor(confianza, "media")
            advertencias.append("La malla tenía huecos pequeños que se repararon automáticamente.")
    else:
        volumen = extents[0] * extents[1] * extents[2] * float(p.factor_caja_pct) / 100
        confianza = _peor(confianza, "baja")
        advertencias.append("La malla tiene huecos o errores: el volumen se estimó a partir de las dimensiones.")
    if max(extents) < 5:
        confianza = _peor(confianza, "baja")
        advertencias.append("La pieza mide menos de 5 mm: verifique las unidades del archivo.")

    area = float(analisis["area_mm2"]) * factor**2
    paredes = min(area * float(p.grosor_pared_mm), volumen)
    relleno = max(volumen - paredes, 0.0) * opciones["relleno"] / 100
    voladizo = float(analisis.get("voladizo_ratio") or 0)
    soportes = opciones["soportes"] == "si" or (
        opciones["soportes"] == "auto" and voladizo * 100 >= float(p.umbral_voladizo_pct)
    )
    plastico = (paredes + relleno) * ((1 + float(p.soporte_extra_pct) / 100) if soportes else 1)
    gramos = plastico / 1000 * float(filamento.densidad) * (1 + float(p.desperdicio_pct) / 100)

    calidad = CALIDADES[opciones["calidad"]]
    capas = max(1, math.ceil(extents[2] / calidad["altura"]))
    segundos = plastico / (float(p.caudal_mm3_s) * calidad["flujo"]) + capas * float(p.seg_por_capa)
    if soportes:
        segundos *= 1.10
    horas = segundos / 3600

    cantidad = int(opciones["cantidad"])
    costo_material = _decimal(gramos) / 1000 * filamento.precio_kg
    costo_maquina = _decimal(horas) * p.tarifa_hora
    por_pieza = (costo_material + costo_maquina) * (1 + p.margen_pct / 100)
    total_base = max(p.minimo, por_pieza * cantidad + p.cargo_fijo)
    precio_unitario = redondear(total_base / cantidad)
    linea = calcular_linea(cantidad, precio_unitario)

    return {
        "cabe": cabe,
        "mensaje_cabida": mensaje_cabida,
        "dimensiones": [round(valor, 1) for valor in extents],
        "dimensiones_texto": dimensiones_texto,
        "gramos": round(gramos, 1),
        "horas": round(horas, 2),
        "tiempo_texto": texto_tiempo(horas),
        "capas": capas,
        "soportes": soportes,
        "confianza": confianza,
        "advertencias": advertencias,
        "cantidad": cantidad,
        "costo_material": redondear(costo_material),
        "costo_maquina": redondear(costo_maquina),
        "precio_unitario": precio_unitario,
        "subtotal": linea["subtotal"],
        "impuesto": linea["impuesto"],
        "total": linea["subtotal"] + linea["impuesto"],
    }


def a_json(resultado):
    """Version serializable (dinero como texto) para responder al navegador."""
    salida = {}
    for clave, valor in resultado.items():
        salida[clave] = str(valor) if isinstance(valor, Decimal) else valor
    salida["confianza_texto"] = CONFIANZA[resultado["confianza"]]
    salida["soportes_texto"] = "Sí" if resultado["soportes"] else "No"
    salida["aviso"] = AVISO
    return salida


def especificaciones_de(resultado, opciones):
    """Especificaciones (texto) que se guardan en la linea de la cotizacion para el operador y el cliente."""
    filamento = opciones["filamento"]
    return {
        "Tipo": ETIQUETA_AUTOMATICA,
        "Filamento": f"{filamento.material} {filamento.color}",
        "Relleno": f"{opciones['relleno']} %",
        "Calidad": CALIDADES[opciones["calidad"]]["texto"],
        "Escala": f"{opciones['escala']} %",
        "Dimensiones": resultado["dimensiones_texto"],
        "Soportes": "Sí" if resultado["soportes"] else "No",
        "Peso estimado": f"{resultado['gramos']} g",
        "Tiempo estimado": resultado["tiempo_texto"],
        "Confianza": CONFIANZA[resultado["confianza"]],
    }
