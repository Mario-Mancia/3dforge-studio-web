from django.http import Http404
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme

from apps.notificaciones.selectors import notificaciones as selectors
from apps.notificaciones.services import notificaciones as servicios


class ListaNotificacionesMixin:
    context_object_name = "notificaciones"
    paginate_by = 20
    ruta_accion = ""

    def get_queryset(self):
        return selectors.de_usuario(self.request.user, solo_no_leidas=bool(self.request.GET.get("no_leidas")))

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["ruta_accion"] = self.ruta_accion
        contexto["solo_no_leidas"] = bool(self.request.GET.get("no_leidas"))
        contexto["items"] = [
            (n, selectors.destino(n, self.request.user)) for n in contexto["page_obj"].object_list
        ]
        return contexto


class AccionNotificacionMixin:
    http_method_names = ["post"]
    destino = ""

    def post(self, request, accion):
        if accion == "leer":
            servicios.marcar_leida(request.user, request.POST.get("pk", ""))
        elif accion == "todas":
            servicios.marcar_todas(request.user)
        else:
            raise Http404
        siguiente = request.POST.get("siguiente", "")
        if siguiente and url_has_allowed_host_and_scheme(siguiente, {request.get_host()}, request.is_secure()):
            return redirect(siguiente)
        return redirect(self.destino)
