from django.core.cache import cache

from apps.api.respuestas import ErrorAPI


def limitar(request, clave, maximo, ventana):
    """Limita peticiones por IP (cache local: valido con un solo proceso)."""
    llave = f"api:limite:{clave}:{request.META.get('REMOTE_ADDR', '?')}"
    cache.add(llave, 0, ventana)
    try:
        usadas = cache.incr(llave)
    except ValueError:
        cache.set(llave, 1, ventana)
        usadas = 1
    if usadas > maximo:
        raise ErrorAPI("Demasiadas solicitudes. Intente de nuevo más tarde.", "limite_excedido", 429)
