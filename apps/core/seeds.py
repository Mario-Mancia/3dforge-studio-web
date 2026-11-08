from django.contrib.auth.models import Group
from django.core.management.color import no_style
from django.db import connections, transaction

ESTADOS_USUARIO = (
    (1, "Activo", "Cuenta habilitada para utilizar la plataforma."),
    (2, "Inactivo", "Cuenta deshabilitada."),
    (3, "Suspendido", "Cuenta suspendida temporalmente."),
    (4, "Pendiente de verificación", "Cuenta pendiente de verificar."),
)

CATEGORIAS_SERVICIOS = (
    ("Impresión 3D", "Servicios de fabricación mediante impresión 3D."),
    ("Diseño 3D", "Diseño de piezas y productos tridimensionales."),
    ("Modelado 3D", "Creación y edición de modelos tridimensionales."),
    ("Asesorías", "Asesoría técnica y acompañamiento en proyectos."),
    ("Prototipado", "Desarrollo de prototipos y validación de diseños."),
)

METODOS_PAGO = (
    (1, "Efectivo", "Pago registrado directamente por un empleado."),
    (2, "Pasarela de pagos", "Pago electrónico mediante proveedor externo."),
)


def sembrar_datos_iniciales(sender=None, using="default", **kwargs):
    from apps.catalogo.models import CategoriaServicio
    from apps.pagos.models import MetodoPago
    from apps.usuarios.constants import GRUPOS
    from apps.usuarios.models import EstadoUsuario

    conexion = connections[using]
    existentes = set(conexion.introspection.table_names())
    requeridas = {modelo._meta.db_table for modelo in (EstadoUsuario, CategoriaServicio, MetodoPago, Group)}
    if not requeridas <= existentes:
        return

    with transaction.atomic(using=using):
        for id_, nombre, descripcion in ESTADOS_USUARIO:
            EstadoUsuario.objects.using(using).get_or_create(
                nombre=nombre, defaults={"id": id_, "descripcion": descripcion}
            )
        for id_, nombre, descripcion in METODOS_PAGO:
            MetodoPago.objects.using(using).get_or_create(
                nombre=nombre, defaults={"id": id_, "descripcion": descripcion}
            )
        for nombre, descripcion in CATEGORIAS_SERVICIOS:
            CategoriaServicio.objects.using(using).get_or_create(
                nombre=nombre, defaults={"descripcion": descripcion}
            )
        for nombre in GRUPOS:
            Group.objects.using(using).get_or_create(name=nombre)

        sentencias = conexion.ops.sequence_reset_sql(no_style(), [EstadoUsuario, MetodoPago])
        with conexion.cursor() as cursor:
            for sentencia in sentencias:
                cursor.execute(sentencia)
