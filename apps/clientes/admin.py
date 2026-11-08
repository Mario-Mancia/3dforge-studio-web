from apps.clientes.models import Cliente
from apps.core.admin_utils import registrar

registrar(Cliente, search_fields=("correo", "nombres", "apellidos", "nombre_empresa"))
