from django.conf import settings
from django.utils.cache import add_never_cache_headers

PREFIJOS_PRIVADOS = ("/cliente/", "/operador/", "/administrador/", "/cuenta/", "/ir/", "/validar/")
PREFIJOS_ESTATICOS = ("/static/", "/media/")


class SinCacheMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.prefijos = PREFIJOS_PRIVADOS + ("/" + settings.ADMIN_URL,)

    def __call__(self, request):
        respuesta = self.get_response(request)
        ruta = request.path
        if not ruta.startswith(PREFIJOS_ESTATICOS):
            usuario = getattr(request, "user", None)
            if ruta.startswith(self.prefijos) or (usuario is not None and usuario.is_authenticated):
                add_never_cache_headers(respuesta)
                respuesta["Pragma"] = "no-cache"
        if request.method == "POST" and ruta.rstrip("/").endswith("/logout"):
            respuesta["Clear-Site-Data"] = '"cache"'
        return respuesta
