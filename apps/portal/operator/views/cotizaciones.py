from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import ListView

from apps.core.archivos import respuesta_descarga
from apps.core.storage import almacenamiento_privado
from apps.core.utiles import mensaje_de
from apps.cotizaciones.forms.cotizaciones import LineasFormSet, RevisionCotizacionForm
from apps.cotizaciones.models import EstadoCotizacion
from apps.cotizaciones.selectors import cotizaciones as selectors
from apps.cotizaciones.services import cotizaciones as servicios
from apps.portal.mixins import OperadorRequeridoMixin

ACCIONES = {
    "enviar": ("enviar_cotizacion", "Cotización enviada al cliente."),
    "cancelar": ("cancelar_cotizacion", "Cotización cancelada."),
}


class CotizacionesView(OperadorRequeridoMixin, ListView):
    template_name = "operator/cotizaciones.html"
    context_object_name = "cotizaciones"
    paginate_by = 20

    def get_queryset(self):
        return selectors.bandeja_operador(
            self.request.GET.get("estado", ""),
            self.request.GET.get("q", "").strip(),
        )

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["estados"] = EstadoCotizacion.choices
        contexto["estado"] = self.request.GET.get("estado", "")
        contexto["q"] = self.request.GET.get("q", "").strip()
        contexto["conteos"] = selectors.contar_por_estado()
        return contexto


class CotizacionOperadorView(OperadorRequeridoMixin, View):
    template_name = "operator/cotizacion.html"

    def _cotizacion(self, pk):
        cotizacion = selectors.obtener_para_operador(pk)
        if cotizacion is None:
            raise Http404
        return cotizacion

    def _iniciales(self, cotizacion):
        return [
            {
                "id": detalle.pk,
                "descripcion": detalle.descripcion,
                "cantidad": detalle.cantidad,
                "precio_unitario": detalle.precio_unitario,
                "descuento": detalle.descuento,
            }
            for detalle in cotizacion.detalles.all()
        ]

    def _responder(self, request, cotizacion, form=None, formset=None):
        editable = cotizacion.estado in servicios.EDITABLES
        if editable and form is None:
            form = RevisionCotizacionForm(
                initial={
                    "observaciones": cotizacion.observaciones,
                    "plazo_entrega_dias": cotizacion.plazo_entrega_dias,
                }
            )
            formset = LineasFormSet(initial=self._iniciales(cotizacion), prefix="lineas")
        contexto = {"cotizacion": cotizacion, "editable": editable, "form": form, "formset": formset}
        return render(request, self.template_name, contexto)

    def get(self, request, pk):
        return self._responder(request, self._cotizacion(pk))

    def post(self, request, pk):
        cotizacion = self._cotizacion(pk)
        if cotizacion.estado not in servicios.EDITABLES:
            messages.error(request, "Esta cotización ya no se puede editar.")
            return redirect("operator:cotizacion", pk=pk)
        form = RevisionCotizacionForm(request.POST)
        formset = LineasFormSet(request.POST, initial=self._iniciales(cotizacion), prefix="lineas")
        if form.is_valid() and formset.is_valid():
            try:
                servicios.revisar_cotizacion(
                    cotizacion.pk,
                    request.user,
                    lineas=formset.cleaned_data,
                    observaciones=form.cleaned_data["observaciones"] or None,
                    plazo_entrega_dias=form.cleaned_data["plazo_entrega_dias"],
                )
            except (servicios.ErrorCotizacion, ValidationError) as error:
                messages.error(request, mensaje_de(error))
            else:
                messages.success(request, "Cotización actualizada.")
                return redirect("operator:cotizacion", pk=pk)
        return self._responder(request, cotizacion, form, formset)


class CotizacionOperadorAccionView(OperadorRequeridoMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk, accion):
        if accion not in ACCIONES:
            raise Http404
        if selectors.obtener_para_operador(pk) is None:
            raise Http404
        nombre_funcion, mensaje = ACCIONES[accion]
        try:
            getattr(servicios, nombre_funcion)(pk, request.user)
        except (servicios.ErrorCotizacion, ValidationError) as error:
            messages.error(request, mensaje_de(error))
        else:
            messages.success(request, mensaje)
        return redirect("operator:cotizacion", pk=pk)


class CotizacionOperadorArchivoView(OperadorRequeridoMixin, View):
    def get(self, request, pk, archivo_id):
        cotizacion = selectors.obtener_para_operador(pk)
        if cotizacion is None:
            raise Http404
        archivo = get_object_or_404(cotizacion.archivos.all(), pk=archivo_id)
        return respuesta_descarga(almacenamiento_privado, archivo.ruta_archivo, archivo.nombre_archivo)
