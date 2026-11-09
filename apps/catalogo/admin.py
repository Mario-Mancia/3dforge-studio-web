from apps.catalogo.models import CategoriaServicio, Producto, Servicio
from apps.core.admin_utils import registrar

registrar(CategoriaServicio)
registrar(Servicio, list_filter=("categoria", "activo"), search_fields=("nombre",))
registrar(Producto, list_filter=("activo",), search_fields=("sku", "nombre"))
