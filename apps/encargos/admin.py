from apps.core.admin_utils import registrar
from apps.encargos.models import ArchivoEncargo, Encargo, EncargoDetalle, HistorialEncargo

registrar(Encargo, list_filter=("estado",), search_fields=("codigo",))
registrar(EncargoDetalle, ArchivoEncargo)
registrar(HistorialEncargo, has_change_permission=lambda self, request, obj=None: False)
