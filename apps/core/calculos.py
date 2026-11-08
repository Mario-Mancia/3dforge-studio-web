from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.conf import settings

from apps.core.constants import CENTAVO, TASA_IMPUESTO_DEFECTO


def tasa_impuesto():
    return Decimal(str(getattr(settings, "TASA_IMPUESTO", TASA_IMPUESTO_DEFECTO)))


def redondear(valor):
    return Decimal(valor).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def subtotal_linea(cantidad, precio_unitario, descuento=Decimal("0")):
    return redondear(Decimal(cantidad) * Decimal(precio_unitario) - Decimal(descuento))


def calcular_linea(cantidad, precio_unitario, descuento=Decimal("0"), tasa=None):
    tasa = tasa_impuesto() if tasa is None else Decimal(str(tasa))
    descuento = redondear(descuento)
    subtotal = subtotal_linea(cantidad, precio_unitario, descuento)
    return {"subtotal": subtotal, "descuento": descuento, "impuesto": redondear(subtotal * tasa)}


def totales_documento(lineas):
    lineas = list(lineas)
    bruto = sum((linea["subtotal"] + linea["descuento"] for linea in lineas), Decimal("0"))
    descuento = sum((linea["descuento"] for linea in lineas), Decimal("0"))
    impuesto = sum((linea["impuesto"] for linea in lineas), Decimal("0"))
    return {
        "subtotal": redondear(bruto),
        "descuento": redondear(descuento),
        "impuesto": redondear(impuesto),
        "total": redondear(bruto - descuento + impuesto),
    }


def importes_coherentes(subtotal, descuento, impuesto, total):
    try:
        esperado = redondear(subtotal) - redondear(descuento) + redondear(impuesto)
        return esperado == redondear(total)
    except (InvalidOperation, TypeError, ValueError):
        return True


def linea_coherente(cantidad, precio_unitario, descuento, subtotal):
    try:
        return subtotal_linea(cantidad, precio_unitario, descuento) == redondear(subtotal)
    except (InvalidOperation, TypeError, ValueError):
        return True
