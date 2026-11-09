import csv

from django.contrib import messages
from django.http import Http404, HttpResponse
from django.views import View
from django.views.generic import TemplateView

from apps.portal.mixins import AdministradorRequeridoMixin
from apps.reportes.forms import fechas_filtro
from apps.reportes.selectors import ventas as selectors

LIMITE_TABLA = 50


class VentasView(AdministradorRequeridoMixin, TemplateView):
    template_name = "administrator/ventas.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        desde, hasta, errores = fechas_filtro(self.request.GET)
        for error in errores:
            messages.error(self.request, error)
        facturas = selectors.facturas_en_rango(desde, hasta)
        pagos = selectors.pagos_en_rango(desde, hasta)
        contexto.update(
            {
                "desde": desde,
                "hasta": hasta,
                "resumen": selectors.resumen_ventas(desde, hasta),
                "facturas": list(facturas[:LIMITE_TABLA]),
                "total_facturas": facturas.count(),
                "pagos": list(pagos[:LIMITE_TABLA]),
                "total_pagos": pagos.count(),
                "limite": LIMITE_TABLA,
            }
        )
        return contexto


class VentasExportarView(AdministradorRequeridoMixin, View):
    def get(self, request, tipo):
        if tipo not in ("facturas", "pagos"):
            raise Http404
        desde, hasta, _ = fechas_filtro(request.GET)
        encabezados, filas = selectors.filas_exportacion(tipo, desde, hasta)
        respuesta = HttpResponse(content_type="text/csv; charset=utf-8")
        respuesta["Content-Disposition"] = f'attachment; filename="{tipo}_{desde:%Y%m%d}_{hasta:%Y%m%d}.csv"'
        respuesta.write("\ufeff")
        escritor = csv.writer(respuesta)
        escritor.writerow(encabezados)
        escritor.writerows(filas)
        return respuesta
