from apps.core.admin_utils import registrar
from apps.facturacion.models import Factura, FacturaDetalle

registrar(Factura, list_filter=("estado",), search_fields=("numero_factura", "nombre_facturacion"))
registrar(FacturaDetalle)
