from django.contrib.auth import SESSION_KEY
from django.contrib.sessions.models import Session
from django.utils import timezone


def cerrar_otras_sesiones(usuario, sesion_actual=None, canal=None):
    """Cierra las demas sesiones del usuario DEL MISMO CANAL.

    canal=None son las sesiones web; las de la app movil llevan canal="api". Asi iniciar
    sesion en la web no expulsa al celular (ni al reves).
    """
    consulta = Session.objects.filter(expire_date__gte=timezone.now())
    if sesion_actual:
        consulta = consulta.exclude(session_key=sesion_actual)
    cerradas = 0
    for sesion in consulta.iterator():
        try:
            datos = sesion.get_decoded()
        except Exception:
            continue
        if datos.get(SESSION_KEY) == str(usuario.pk) and datos.get("canal") == canal:
            sesion.delete()
            cerradas += 1
    return cerradas
