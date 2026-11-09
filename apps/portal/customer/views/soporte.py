from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.views import View

from apps.clientes.services.clientes import asegurar_cliente
from apps.core.utiles import mensaje_de
from apps.crm.forms.crm import SolicitudSoporteForm
from apps.crm.selectors import crm as selectors
from apps.crm.services import crm as servicios
from apps.portal.mixins import ClienteRequeridoMixin


class SoporteView(ClienteRequeridoMixin, View):
    template_name = "customer/soporte.html"

    def _responder(self, request, form, cliente):
        contexto = {"form": form, "solicitudes": selectors.solicitudes_del_cliente(cliente)[:20]}
        return render(request, self.template_name, contexto)

    def get(self, request):
        return self._responder(request, SolicitudSoporteForm(), asegurar_cliente(request.user))

    def post(self, request):
        cliente = asegurar_cliente(request.user)
        form = SolicitudSoporteForm(request.POST)
        if form.is_valid():
            try:
                solicitud = servicios.crear_solicitud(cliente, **form.cleaned_data)
            except (servicios.ErrorCRM, ValidationError) as error:
                form.add_error(None, mensaje_de(error))
            else:
                messages.success(request, f"Solicitud #{solicitud.pk} enviada.")
                return redirect("customer:soporte_detalle", pk=solicitud.pk)
        return self._responder(request, form, cliente)


class SoporteDetalleView(ClienteRequeridoMixin, View):
    template_name = "customer/soporte_detalle.html"

    def get(self, request, pk):
        solicitud = selectors.obtener_solicitud_del_cliente(asegurar_cliente(request.user), pk)
        if solicitud is None:
            raise Http404
        return render(request, self.template_name, {"solicitud": solicitud})


class SoporteCerrarView(ClienteRequeridoMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        solicitud = selectors.obtener_solicitud_del_cliente(asegurar_cliente(request.user), pk)
        if solicitud is None:
            raise Http404
        try:
            servicios.cerrar_por_cliente(solicitud.pk, request.user)
        except servicios.ErrorCRM as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "Solicitud cerrada.")
        return redirect("customer:soporte_detalle", pk=pk)
