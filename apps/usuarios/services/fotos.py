from apps.core.imagenes import eliminar_imagen, guardar_imagen_publica, normalizar_imagen

LADO_FOTO = 256


def guardar_foto(usuario, archivo):
    """Guarda la foto de perfil (cuadrada, 256 px) y elimina la anterior."""
    contenido, extension = normalizar_imagen(archivo, lado=LADO_FOTO)
    nueva = guardar_imagen_publica("perfiles", contenido, extension)
    anterior = usuario.foto
    usuario.foto = nueva
    try:
        usuario.save(update_fields=["foto"])
    except Exception:
        eliminar_imagen(nueva)
        raise
    if anterior and anterior != nueva:
        eliminar_imagen(anterior)
    return nueva


def quitar_foto(usuario):
    anterior = usuario.foto
    if not anterior:
        return
    usuario.foto = None
    usuario.save(update_fields=["foto"])
    eliminar_imagen(anterior)
