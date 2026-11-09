from apps.core.admin_utils import registrar
from apps.pagos.models import MetodoPago, Pago

registrar(MetodoPago)
registrar(Pago, list_filter=("estado", "metodo_pago"))
