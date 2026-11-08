from apps.core.admin_utils import registrar
from apps.cotizaciones.models import Cotizacion, CotizacionDetalle

registrar(Cotizacion, list_filter=("estado",), search_fields=("codigo",))
registrar(CotizacionDetalle)
