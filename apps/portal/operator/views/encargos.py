from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import ListView

from apps.core.archivos import respuesta_descarga
from apps.core.storage import almacenamiento_privado
from apps.core.utiles import mensaje_de
from apps.cotizaciones.models import Cotizacion
from apps.encargos.forms.encargos import AsignacionForm, CambioEstadoForm, SubirArchivoForm
from apps.encargos.models import EstadoEncargo
from apps.encargos.selectors import encargos as selectors
from apps.encargos.services import encargos as servicios
from apps.portal.mixins import OperadorRequeridoMixin


class EncargosView(OperadorRequeridoMixin, ListView):
    template_name = "operator/encargos.html"
    context_object_name = "encargos"
    paginate_by = 20

    def get_queryset(self):
        return selectors.bandeja_operador(self.request.GET.get("estado", ""), self.request.GET.get("q", "").strip())

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["estados"] = EstadoEncargo.choices
        contexto["estado"] = self.request.GET.get("estado", "")
        contexto["q"] = self.request.GET.get("q", "").strip()
        return contexto


class EncargoDesdeCotizacionView(OperadorRequeridoMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        try:
            encargo = servicios.crear_desde_cotizacion(pk, request.user)
        except Cotizacion.DoesNotExist:
            raise Http404
        except (servicios.ErrorEncargo, ValidationError) as error:
            messages.error(request, mensaje_de(error))
            return redirect("operator:cotizacion", pk=pk)
        messages.success(request, f"Encargo {encargo.codigo} listo.")
        return redirect("operator:encargo", pk=encargo.pk)


class EncargoOperadorView(OperadorRequeridoMixin, View):
    template_name = "operator/encargo.html"

    def get(self, request, pk):
        encargo = selectors.obtener_para_operador(pk)
        if encargo is None:
            raise Http404
        permitidos = servicios.TRANSICIONES.get(encargo.estado, set())
        contexto = {
            "encargo": encargo,
            "form_estado": CambioEstadoForm(permitidos=permitidos) if permitidos else None,
            "form_asignar": AsignacionForm(initial={"empleado": encargo.empleado_responsable_id}),
            "form_archivo": SubirArchivoForm(encargo=encargo),
        }
        return render(request, self.template_name, contexto)


class EncargoAccionView(OperadorRequeridoMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk, accion):
        encargo = selectors.obtener_para_operador(pk)
        if encargo is None or accion not in ("estado", "asignar", "archivo"):
            raise Http404
        try:
            if accion == "estado":
                form = CambioEstadoForm(request.POST, permitidos=servicios.TRANSICIONES.get(encargo.estado, set()))
                if not form.is_valid():
                    raise ValidationError("Seleccione un estado válido.")
                servicios.cambiar_estado(pk, request.user, form.cleaned_data["estado"], form.cleaned_data["comentario"])
                messages.success(request, "Estado actualizado.")
            elif accion == "asignar":
                form = AsignacionForm(request.POST)
                if not form.is_valid():
                    raise ValidationError("Seleccione un empleado válido.")
                servicios.asignar_responsable(pk, request.user, form.cleaned_data["empleado"].pk)
                messages.success(request, "Responsable asignado.")
            else:
                form = SubirArchivoForm(request.POST, request.FILES, encargo=encargo)
                if not form.is_valid():
                    raise ValidationError(" ".join(m for errores in form.errors.values() for m in errores))
                servicios.subir_archivo(pk, form.cleaned_data["detalle"].pk, request.user, form.cleaned_data["archivo"])
                messages.success(request, "Archivo cargado.")
        except (servicios.ErrorEncargo, ValidationError) as error:
            messages.error(request, mensaje_de(error))
        return redirect("operator:encargo", pk=pk)


class EncargoArchivoView(OperadorRequeridoMixin, View):
    def get(self, request, pk, archivo_id):
        encargo = selectors.obtener_para_operador(pk)
        if encargo is None:
            raise Http404
        archivo = next((a for d in encargo.detalles.all() for a in d.archivos.all() if a.pk == archivo_id), None)
        if archivo is None:
            raise Http404
        return respuesta_descarga(almacenamiento_privado, archivo.ruta_archivo, archivo.nombre_archivo)
