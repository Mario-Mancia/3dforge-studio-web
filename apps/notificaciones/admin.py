from apps.core.admin_utils import registrar
from apps.notificaciones.models import Notificacion

registrar(Notificacion, list_filter=("leida", "tipo"))
