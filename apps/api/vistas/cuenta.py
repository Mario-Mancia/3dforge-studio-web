from django.utils import timezone

from apps.api import serializadores as ser
from apps.api.autenticacion import api
from apps.api.respuestas import exito, fallo_formulario, leer_json
from apps.clientes.forms.clientes import PerfilClienteForm
from apps.clientes.services.clientes import guardar_perfil
from apps.core.models import ConfiguracionNegocio
from apps.reportes.selectors.panel_cliente import resumen_cliente

CAMPOS_PERFIL = ("tipo_cliente", "nombres", "apellidos", "nombre_empresa", "telefono", "identificacion_fiscal", "direccion")


@api(("GET",), requiere_sesion=False)
def salud(request):
    return exito({"ok": True, "servicio": "3DForge Studio API", "version": "1", "hora": ser.fecha(timezone.now())})


@api(("GET",), requiere_sesion=False)
def negocio(request):
    return exito(ser.negocio(ConfiguracionNegocio.objects.first(), request))


@api(("GET", "PUT", "PATCH"))
def perfil(request):
    if request.method == "GET":
        return exito(ser.cliente(request.cliente))
    datos = leer_json(request)
    entrada = {campo: getattr(request.cliente, campo) or "" for campo in CAMPOS_PERFIL}
    for campo in CAMPOS_PERFIL:
        if campo in datos:
            valor = datos[campo]
            entrada[campo] = "" if valor is None else str(valor)
    formulario = PerfilClienteForm(entrada, instance=request.cliente)
    if not formulario.is_valid():
        return fallo_formulario(formulario)
    return exito(ser.cliente(guardar_perfil(formulario)))


@api(("GET",))
def panel(request):
    resumen = resumen_cliente(request.cliente, request.usuario)
    kpis = resumen["kpis"]
    return exito(
        {
            "kpis": {
                "por_responder": kpis["por_responder"],
                "en_revision": kpis["en_revision"],
                "pedidos_en_curso": kpis["pedidos_en_curso"],
                "saldo_pendiente": ser.dinero(kpis["saldo_pendiente"]),
                "soporte_abierto": kpis["soporte_abierto"],
            },
            "cotizaciones": [ser.cotizacion_resumen(c) for c in resumen["cotizaciones"]],
            "pedidos": [ser.encargo_resumen(e) for e in resumen["pedidos"]],
            "facturas": [ser.factura_resumen(f) for f in resumen["facturas"]],
            "soporte": [ser.soporte(s) for s in resumen["soporte"]],
            "notificaciones": [ser.notificacion(n) for n, _destino in resumen["notificaciones"]],
        }
    )
