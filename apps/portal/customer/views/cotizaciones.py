from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import ListView

from apps.clientes.services.clientes import asegurar_cliente
from apps.core.archivos import respuesta_descarga
from apps.core.storage import almacenamiento_privado
from apps.cotizaciones.selectors import cotizaciones as selectors
from apps.cotizaciones.services import cotizaciones as servicios
from apps.portal.mixins import ClienteRequeridoMixin

ACCIONES = {
    "aceptar": ("aceptar_cotizacion", "Cotización aceptada. Gracias por su confianza."),
    "rechazar": ("rechazar_cotizacion", "Cotización rechazada."),
    "cancelar": ("cancelar_cotizacion", "Solicitud cancelada."),
}


class CotizacionesView(ClienteRequeridoMixin, ListView):
    template_name = "customer/cotizaciones.html"
    context_object_name = "cotizaciones"
    paginate_by = 10

    def get_queryset(self):
        return selectors.cotizaciones_del_cliente(asegurar_cliente(self.request.user))


class CotizacionDetalleView(ClienteRequeridoMixin, View):
    template_name = "customer/cotizacion_detalle.html"

    def get(self, request, pk):
        cotizacion = selectors.obtener_del_cliente(asegurar_cliente(request.user), pk)
        if cotizacion is None:
            raise Http404
        return render(request, self.template_name, {"cotizacion": cotizacion})


class CotizacionAccionView(ClienteRequeridoMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk, accion):
        if accion not in ACCIONES:
            raise Http404
        cotizacion = selectors.obtener_del_cliente(asegurar_cliente(request.user), pk)
        if cotizacion is None:
            raise Http404
        nombre_funcion, mensaje = ACCIONES[accion]
        try:
            getattr(servicios, nombre_funcion)(cotizacion.pk, request.user)
        except servicios.ErrorCotizacion as error:
            messages.error(request, str(error))
        else:
            messages.success(request, mensaje)
        return redirect("customer:cotizacion", pk=pk)


class CotizacionArchivoView(ClienteRequeridoMixin, View):
    def get(self, request, pk, archivo_id):
        cotizacion = selectors.obtener_del_cliente(asegurar_cliente(request.user), pk)
        if cotizacion is None:
            raise Http404
        archivo = get_object_or_404(cotizacion.archivos.all(), pk=archivo_id)
        return respuesta_descarga(almacenamiento_privado, archivo.ruta_archivo, archivo.nombre_archivo)
