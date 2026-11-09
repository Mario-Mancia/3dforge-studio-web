from apps.core.admin_utils import registrar
from apps.crm.models import InteraccionCliente, NotaCliente, SolicitudSoporte

registrar(InteraccionCliente, NotaCliente)
registrar(SolicitudSoporte, list_filter=("estado", "prioridad"))
