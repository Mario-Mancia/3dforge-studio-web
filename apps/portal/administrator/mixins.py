from django.contrib import messages

from apps.portal.mixins import AdministradorRequeridoMixin


class FormularioAdminMixin(AdministradorRequeridoMixin):
    template_name = "administrator/formulario.html"
    titulo = ""
    mensaje_exito = "Los cambios se guardaron correctamente."

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["titulo"] = self.titulo
        contexto["volver"] = str(self.success_url)
        return contexto

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, self.mensaje_exito)
        return respuesta
