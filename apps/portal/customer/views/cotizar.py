from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.views import View

from apps.clientes.services.clientes import asegurar_cliente
from apps.core.utiles import mensaje_de
from apps.cotizaciones.forms.cotizaciones import SolicitudCotizacionForm
from apps.cotizaciones.services import cotizaciones as servicios
from apps.portal.mixins import ClienteRequeridoMixin


class CotizarView(ClienteRequeridoMixin, View):
    template_name = "customer/cotizar.html"

    def get(self, request):
        return render(request, self.template_name, {"form": SolicitudCotizacionForm()})

    def post(self, request):
        form = SolicitudCotizacionForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                cotizacion = servicios.solicitar_cotizacion(
                    cliente=asegurar_cliente(request.user),
                    usuario=request.user,
                    servicio=form.cleaned_data["servicio"],
                    cantidad=form.cleaned_data["cantidad"],
                    descripcion=form.cleaned_data["descripcion"],
                    solicitud=form.cleaned_data["solicitud"],
                    especificaciones=form.especificaciones(),
                    archivos=form.cleaned_data["archivos"],
                )
            except (servicios.ErrorCotizacion, ValidationError) as error:
                form.add_error(None, mensaje_de(error))
            else:
                messages.success(request, f"Su solicitud {cotizacion.codigo} fue recibida.")
                return redirect("customer:cotizacion", pk=cotizacion.pk)
        return render(request, self.template_name, {"form": form})
