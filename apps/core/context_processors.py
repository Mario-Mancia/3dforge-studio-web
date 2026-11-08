from django.core.cache import cache

from apps.core.models import ConfiguracionNegocio
from apps.core.models.configuracion_negocio import CLAVE_CACHE


def negocio(request):
    configuracion = cache.get(CLAVE_CACHE)
    if configuracion is None:
        configuracion = ConfiguracionNegocio.objects.first()
        cache.set(CLAVE_CACHE, configuracion, 300)
    return {"negocio": configuracion}
