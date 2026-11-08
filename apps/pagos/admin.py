from apps.core.admin_utils import registrar
from apps.pagos.models import MetodoPago, Pago, TransaccionPasarela

registrar(MetodoPago)
registrar(Pago, list_filter=("estado", "metodo_pago"))
registrar(TransaccionPasarela)
