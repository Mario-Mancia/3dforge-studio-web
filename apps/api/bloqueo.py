from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render


def respuesta_bloqueo(request, credentials=None):
    """Respuesta de axes al bloquear por intentos fallidos: JSON en /api/, HTML en la web."""
    if request.path.startswith("/api/"):
        cuerpo = {"error": {"codigo": "bloqueado", "mensaje": "Demasiados intentos fallidos. Intente de nuevo más tarde.", "campos": {}}}
        return JsonResponse(cuerpo, status=429, json_dumps_params={"ensure_ascii": False})
    return render(request, "errors/bloqueado.html", status=getattr(settings, "AXES_HTTP_RESPONSE_CODE", 403))
