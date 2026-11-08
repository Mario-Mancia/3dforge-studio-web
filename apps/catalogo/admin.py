from apps.catalogo.models import CategoriaServicio, Promocion, Servicio
from apps.core.admin_utils import registrar

registrar(CategoriaServicio, Promocion)
registrar(Servicio, list_filter=("categoria", "activo"), search_fields=("nombre",))
