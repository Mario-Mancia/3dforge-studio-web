from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect, render
from django.views import View

from apps.core.models import ConfiguracionNegocio
from apps.pagos.models import MetodoPago
from apps.portal.administrator.forms.configuracion import ConfiguracionNegocioForm
from apps.portal.mixins import AdministradorRequeridoMixin


def _megabytes(valor):
    return f"{valor / 1048576:g} MB"


def parametros_del_sistema():
    """Valores de solo lectura que se cambian en el archivo .env (o en la configuracion)."""
    correo = settings.MAILERS.get("default", {}) if hasattr(settings, "MAILERS") else {}
    if "smtp" in str(correo.get("BACKEND", "")):
        saliente = f"SMTP ({correo.get('OPTIONS', {}).get('host', '')})"
    else:
        saliente = "Consola (desarrollo): los correos no se envían"
    filas = [
        ("Impuesto aplicado", f"{(settings.TASA_IMPUESTO * 100).normalize():f} %", "TASA_IMPUESTO"),
        ("Vigencia de las cotizaciones", f"{settings.COTIZACION_VIGENCIA_DIAS} días", "COTIZACION_VIGENCIA_DIAS"),
        ("Vencimiento de las facturas", f"{settings.FACTURA_VENCIMIENTO_DIAS} días", "FACTURA_VENCIMIENTO_DIAS"),
        (
            "Archivos por cotización",
            f"hasta {settings.COTIZACION_MAX_ARCHIVOS}, de {_megabytes(settings.MAX_ARCHIVO_BYTES)} cada uno",
            "COTIZACION_MAX_ARCHIVOS",
        ),
        ("Imágenes (productos, logo, fotos)", f"hasta {_megabytes(settings.IMAGEN_MAX_BYTES)}", "IMAGEN_MAX_BYTES"),
        ("Sesión única en la web", "Activada" if settings.SESION_UNICA else "Desactivada", "SESION_UNICA"),
        ("Correo saliente", saliente, "MAIL_HOST"),
    ]
    dias_api = getattr(settings, "API_TOKEN_DIAS", None)
    if dias_api:
        filas.append(("Sesión de la app móvil", f"{dias_api} días", "API_TOKEN_DIAS"))
    return [{"etiqueta": e, "valor": v, "variable": c} for e, v, c in filas]


class ConfiguracionView(AdministradorRequeridoMixin, View):
    template_name = "administrator/configuracion.html"

    def _instancia(self):
        return ConfiguracionNegocio.objects.first() or ConfiguracionNegocio(nombre_negocio="3DForge Studio")

    def _contexto(self, form, configuracion):
        return {
            "form": form,
            "configuracion": configuracion,
            "parametros": parametros_del_sistema(),
            "metodos_pago": MetodoPago.objects.order_by("nombre"),
        }

    def get(self, request):
        configuracion = self._instancia()
        return render(request, self.template_name, self._contexto(ConfiguracionNegocioForm(instance=configuracion), configuracion))

    def post(self, request):
        configuracion = self._instancia()
        form = ConfiguracionNegocioForm(request.POST, request.FILES, instance=configuracion)
        if form.is_valid():
            form.save()
            messages.success(request, "La configuración del negocio se guardó correctamente.")
            return redirect("administrator:configuracion")
        return render(request, self.template_name, self._contexto(form, configuracion))
