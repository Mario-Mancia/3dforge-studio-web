from django.contrib.auth import SESSION_KEY
from django.contrib.sessions.models import Session
from django.utils import timezone


def cerrar_otras_sesiones(usuario, sesion_actual=None):
    consulta = Session.objects.filter(expire_date__gte=timezone.now())
    if sesion_actual:
        consulta = consulta.exclude(session_key=sesion_actual)
    cerradas = 0
    for sesion in consulta.iterator():
        try:
            datos = sesion.get_decoded()
        except Exception:
            continue
        if datos.get(SESSION_KEY) == str(usuario.pk):
            sesion.delete()
            cerradas += 1
    return cerradas
