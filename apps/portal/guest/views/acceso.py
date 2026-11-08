from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import TemplateView


class AccesoView(TemplateView):
    template_name = "guest/acceso.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("redirigir")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        siguiente = self.request.GET.get("next", "")
        if not url_has_allowed_host_and_scheme(siguiente, {self.request.get_host()}, self.request.is_secure()):
            siguiente = ""
        contexto["siguiente"] = siguiente
        return contexto
