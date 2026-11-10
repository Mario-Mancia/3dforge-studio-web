import time

from django.contrib import messages
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views import View

from apps.clientes.services.clientes import asegurar_cliente
from apps.core.utiles import mensaje_de
from apps.cotizaciones.forms.automatica import Cotizacion3DForm, OpcionesEstimacionForm, validar_modelo_3d
from apps.cotizaciones.forms.cotizaciones import SolicitudCotizacionForm
from apps.cotizaciones.modelos3d.analisis import analisis_desde_json, analizar_archivo
from apps.cotizaciones.modelos3d.errores import ErrorAnalisis
from apps.cotizaciones.modelos3d.estimacion import AVISO, a_json, estimar
from apps.cotizaciones.models import ConfiguracionCotizador
from apps.cotizaciones.selectors.automatica import filamentos_activos
from apps.cotizaciones.services import automatica
from apps.cotizaciones.services import cotizaciones as servicios
from apps.portal.mixins import ClienteRequeridoMixin

LIMITE_ANALISIS_POR_MINUTO = 20


class CotizarView(ClienteRequeridoMixin, View):
    """Solicitar cotizacion: automatica de impresion 3D (arriba) y formulario general para otros servicios (abajo)."""

    template_name = "customer/cotizar.html"

    def _render(self, request, form=None, form3d=None):
        contexto = {
            "form": form or SolicitudCotizacionForm(),
            "form3d": form3d or Cotizacion3DForm(),
            "hay_filamentos": filamentos_activos().exists(),
            "aviso_estimacion": AVISO,
        }
        return render(request, self.template_name, contexto)

    def get(self, request):
        return self._render(request)

    def post(self, request):
        if request.POST.get("tipo_cotizacion") == "3d":
            return self._enviar_3d(request)
        return self._enviar_manual(request)

    def _enviar_manual(self, request):
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
        return self._render(request, form=form)

    def _enviar_3d(self, request):
        form3d = Cotizacion3DForm(request.POST, request.FILES)
        if form3d.is_valid():
            try:
                cotizacion = automatica.solicitar_cotizacion_automatica(
                    cliente=asegurar_cliente(request.user),
                    usuario=request.user,
                    archivo=form3d.cleaned_data["archivo"],
                    opciones=form3d.opciones(),
                    descripcion=form3d.cleaned_data["descripcion"],
                    comentarios=form3d.cleaned_data["comentarios"],
                )
            except (servicios.ErrorCotizacion, ValidationError) as error:
                form3d.add_error(None, mensaje_de(error))
            else:
                messages.success(
                    request,
                    f"Su solicitud {cotizacion.codigo} fue recibida. Un profesional revisará el precio estimado.",
                )
                return redirect("customer:cotizacion", pk=cotizacion.pk)
        return self._render(request, form3d=form3d)


class CotizarEstimarView(ClienteRequeridoMixin, View):
    """Estimacion en vivo (JSON): recibe el archivo una vez y despues solo el analisis y las opciones."""

    http_method_names = ["post"]

    def _error(self, mensaje, estado=400, errores=None):
        return JsonResponse({"ok": False, "mensaje": mensaje, "errores": errores or {}}, status=estado)

    def _limitado(self, usuario):
        clave = f"cotizador:estimar:{usuario.pk}:{int(time.time() // 60)}"
        cache.add(clave, 0, 120)
        try:
            usados = cache.incr(clave)
        except ValueError:
            cache.set(clave, 1, 120)
            usados = 1
        return usados > LIMITE_ANALISIS_POR_MINUTO

    def post(self, request):
        formulario = OpcionesEstimacionForm(request.POST)
        if not formulario.is_valid():
            errores = {campo: [str(e) for e in lista] for campo, lista in formulario.errors.items()}
            return self._error("Revise las opciones elegidas.", errores=errores)
        parametros = ConfiguracionCotizador.obtener()
        archivo = request.FILES.get("archivo")
        try:
            if archivo is not None:
                if self._limitado(request.user):
                    return self._error("Demasiados análisis seguidos. Espere un minuto.", 429)
                validar_modelo_3d(archivo)
                analisis = analizar_archivo(archivo, parametros.max_triangulos)
            else:
                analisis = analisis_desde_json(request.POST.get("analisis"))
        except ValidationError as error:
            return self._error(mensaje_de(error))
        except ErrorAnalisis as error:
            return self._error(str(error))
        resultado = estimar(analisis, formulario.cleaned_data["filamento"], formulario.opciones(), parametros)
        return JsonResponse({"ok": True, "analisis": analisis, "estimacion": a_json(resultado)})
