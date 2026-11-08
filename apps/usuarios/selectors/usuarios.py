from apps.usuarios.constants import GRUPO_ADMINISTRADOR, GRUPO_CLIENTE, GRUPO_OPERADOR

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
