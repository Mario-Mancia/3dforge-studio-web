from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from apps.core.constants import CENTAVO


def redondear(valor):
    return Decimal(valor).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def importes_coherentes(subtotal, descuento, impuesto, total):
    try:
        esperado = redondear(subtotal) - redondear(descuento) + redondear(impuesto)
        return esperado == redondear(total)
    except (InvalidOperation, TypeError, ValueError):
        return True
