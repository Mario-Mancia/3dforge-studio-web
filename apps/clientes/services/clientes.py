from django.db import transaction

from apps.clientes.models import Cliente, TipoCliente


@transaction.atomic
def asegurar_cliente(usuario):
    cliente = Cliente.objects.filter(usuario=usuario).first()
    if cliente is not None:
        return cliente
    return Cliente.objects.create(
        usuario=usuario,
        tipo_cliente=TipoCliente.PERSONA,
        nombres=usuario.nombres,
        apellidos=usuario.apellidos,
        correo=usuario.correo,
        telefono=usuario.telefono,
    )


@transaction.atomic
def guardar_perfil(form):
    cliente = form.save()
    usuario = cliente.usuario
    if usuario is not None and cliente.tipo_cliente == TipoCliente.PERSONA:
        usuario.nombres = cliente.nombres
        usuario.apellidos = cliente.apellidos
        usuario.telefono = cliente.telefono
        usuario.save(update_fields=["nombres", "apellidos", "telefono"])
    return cliente
