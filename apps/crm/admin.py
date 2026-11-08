from apps.core.admin_utils import registrar
from apps.crm.models import InteraccionCliente, NotaCliente, Resena, SolicitudSoporte

registrar(InteraccionCliente, NotaCliente, Resena)
registrar(SolicitudSoporte, list_filter=("estado", "prioridad"))
