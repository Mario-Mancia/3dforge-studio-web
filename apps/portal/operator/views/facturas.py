from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import ListView

from apps.core.utiles import mensaje_de
from apps.encargos.models import Encargo
from apps.facturacion.models import EstadoFactura, Factura
from apps.facturacion.selectors import facturacion as selectors
from apps.facturacion.services import facturacion as servicios
from apps.pagos.forms.pagos import AnulacionForm, PagoForm
from apps.pagos.models import EstadoPago, Pago
from apps.pagos.services import pagos as servicios_pagos
from apps.portal.mixins import OperadorRequeridoMixin


def _errores(form):
    return " ".join(m for errores in form.errors.values() for m in errores) or "Datos no válidos."


class FacturasView(OperadorRequeridoMixin, ListView):
    template_name = "operator/facturas.html"
    context_object_name = "facturas"
    paginate_by = 20

    def get_queryset(self):
        return selectors.bandeja(self.request.GET.get("estado", ""), self.request.GET.get("q", "").strip())

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["estados"] = EstadoFactura.choices
        contexto["estado"] = self.request.GET.get("estado", "")
        contexto["q"] = self.request.GET.get("q", "").strip()
        return contexto


class FacturaDesdeEncargoView(OperadorRequeridoMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        try:
            factura = servicios.crear_desde_encargo(pk, request.user)
        except Encargo.DoesNotExist:
            raise Http404
        except (servicios.ErrorFacturacion, ValidationError) as error:
            messages.error(request, mensaje_de(error))
            return redirect("operator:encargo", pk=pk)
        messages.success(request, f"Factura {factura.numero_factura} lista.")
        return redirect("operator:factura", pk=factura.pk)


class FacturaOperadorView(OperadorRequeridoMixin, View):
    template_name = "operator/factura.html"

    def get(self, request, pk):
        factura = selectors.obtener_para_operador(pk)
        if factura is None:
            raise Http404
        confirmados = [p for p in factura.pagos.all() if p.estado == EstadoPago.CONFIRMADO]
        contexto = {
            "factura": factura,
            "cobrable": factura.estado in servicios.ESTADOS_COBRABLES,
            "puede_anular": factura.estado != EstadoFactura.ANULADA and not confirmados,
            "form_pago": PagoForm(),
            "form_anulacion": AnulacionForm(),
        }
        return render(request, self.template_name, contexto)


class FacturaAccionView(OperadorRequeridoMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk, accion):
        if accion not in ("pagar", "anular", "anular_pago") or selectors.obtener_para_operador(pk) is None:
            raise Http404
        try:
            if accion == "pagar":
                form = PagoForm(request.POST)
                if not form.is_valid():
                    raise ValidationError(_errores(form))
                datos = form.cleaned_data
                servicios_pagos.registrar_pago(
                    pk, request.user, datos["metodo"].pk, datos["monto"], datos["referencia"], datos["observaciones"]
                )
                messages.success(request, "Pago registrado.")
            else:
                form = AnulacionForm(request.POST)
                if not form.is_valid():
                    raise ValidationError(_errores(form))
                if accion == "anular_pago":
                    pago_id = request.POST.get("pago", "")
                    if not pago_id.isdigit():
                        raise ValidationError("Pago no válido.")
                    servicios_pagos.anular_pago(int(pago_id), request.user, form.cleaned_data["motivo"])
                    messages.success(request, "Pago cancelado.")
                else:
                    servicios.anular_factura(pk, request.user, form.cleaned_data["motivo"])
                    messages.success(request, "Factura anulada.")
        except (servicios.ErrorFacturacion, ValidationError) as error:
            messages.error(request, mensaje_de(error))
        except (Pago.DoesNotExist, Factura.DoesNotExist):
            raise Http404
        return redirect("operator:factura", pk=pk)
