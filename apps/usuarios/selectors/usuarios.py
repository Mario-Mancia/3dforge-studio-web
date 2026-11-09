from django.db.models import Q

from apps.usuarios.constants import GRUPO_ADMINISTRADOR, GRUPO_CLIENTE, GRUPO_OPERADOR, GRUPOS
from apps.usuarios.models import Usuario

ORDEN_ROLES = (
    (GRUPO_ADMINISTRADOR, "administrator:dashboard"),
    (GRUPO_OPERADOR, "operator:panel"),
    (GRUPO_CLIENTE, "customer:panel"),
)


def destino_por_rol(usuario):
    if not usuario.is_authenticated:
        return None
    for grupo, destino in ORDEN_ROLES:
        if usuario.tiene_algun_rol((grupo,)):
            return destino
    return None


def usuarios_para_panel(busqueda="", rol="", estado=""):
    consulta = Usuario.objects.select_related("estado", "empleado").prefetch_related("groups").order_by("correo")
    if busqueda:
        consulta = consulta.filter(
            Q(correo__icontains=busqueda) | Q(nombres__icontains=busqueda) | Q(apellidos__icontains=busqueda)
        )
    if rol == "SIN_ROL":
        consulta = consulta.filter(groups__isnull=True)
    elif rol in GRUPOS:
        consulta = consulta.filter(groups__name=rol)
    if estado.isdigit():
        consulta = consulta.filter(estado_id=int(estado))
    return consulta.distinct()
