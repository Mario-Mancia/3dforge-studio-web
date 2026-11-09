from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import ListView

from apps.core.utiles import mensaje_de
from apps.crm.forms.crm import CambioEstadoSoporteForm
from apps.crm.models import EstadoSoporte
from apps.crm.selectors import crm as selectors
from apps.crm.services import crm as servicios
from apps.portal.mixins import OperadorRequeridoMixin


class SoporteOperadorView(OperadorRequeridoMixin, ListView):
    template_name = "operator/soporte.html"
    context_object_name = "solicitudes"
    paginate_by = 20

    def get_queryset(self):
        return selectors.bandeja_soporte(self.request.GET.get("estado", ""), self.request.GET.get("q", "").strip())

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["estados"] = EstadoSoporte.choices
        contexto["estado"] = self.request.GET.get("estado", "")
        contexto["q"] = self.request.GET.get("q", "").strip()
        return contexto


class SoporteOperadorDetalleView(OperadorRequeridoMixin, View):
    template_name = "operator/soporte_detalle.html"

    def get(self, request, pk):
        solicitud = selectors.obtener_solicitud(pk)
        if solicitud is None:
            raise Http404
        permitidos = servicios.TRANSICIONES_SOPORTE.get(solicitud.estado, set())
        contexto = {
            "solicitud": solicitud,
            "form_estado": CambioEstadoSoporteForm(permitidos=permitidos) if permitidos else None,
        }
        return render(request, self.template_name, contexto)


class SoporteAccionView(OperadorRequeridoMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk, accion):
        solicitud = selectors.obtener_solicitud(pk)
        if solicitud is None or accion not in ("tomar", "estado"):
            raise Http404
        try:
            if accion == "tomar":
                servicios.tomar_solicitud(pk, request.user)
                messages.success(request, "Solicitud asignada a usted.")
            else:
                form = CambioEstadoSoporteForm(request.POST, permitidos=servicios.TRANSICIONES_SOPORTE.get(solicitud.estado, set()))
                if not form.is_valid():
                    raise ValidationError("Seleccione un estado válido.")
                servicios.cambiar_estado_solicitud(pk, request.user, form.cleaned_data["estado"])
                messages.success(request, "Estado actualizado.")
        except (servicios.ErrorCRM, ValidationError) as error:
            messages.error(request, mensaje_de(error))
        return redirect("operator:soporte_detalle", pk=pk)
