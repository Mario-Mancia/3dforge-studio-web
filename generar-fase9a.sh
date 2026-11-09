#!/usr/bin/env bash
set -Eeuo pipefail

readonly RAIZ_POR_DEFECTO="/home/mmancia/Projects/Web/3dforge-studio/3dforge-studio-web"

RAIZ=""
DIR_ACTUAL=""
RESPALDO=""
CREADOS=0
ACTUALIZADOS=0
SIN_CAMBIOS=0
OMITIDOS=0
AVISOS=()

info() { printf '[INFO] %s\n' "$*"; }
ok() { printf '[ OK ] %s\n' "$*"; }
advertir() { printf '[AVISO] %s\n' "$*" >&2; AVISOS+=("$*"); }
fallar() { printf '[ERROR] %s\n' "$*" >&2; exit 1; }

ayuda() {
    cat <<'__FIN__'
Uso: generar-proyecto.sh [opciones] [RAIZ_DEL_PROYECTO]

  --instalar          instala requirements.txt en el entorno activo (.venv)
  --sin-migraciones   no ejecuta makemigrations al final
  -h, --ayuda         muestra esta ayuda

Capa de datos y configuracion: se regeneran con respaldo en .respaldo/.
Vistas, plantillas, formularios, servicios y selectores: solo se crean si faltan.
__FIN__
}

validar_ruta() {
    local r="$1"
    [[ -n $r && $r != /* && $r != *..* && $r =~ ^[A-Za-z0-9_./-]+$ ]] || fallar "Ruta no permitida: '$r'"
}

rel_actual() { printf '%s' "${DIR_ACTUAL:+$DIR_ACTUAL/}$1"; }

ir_raiz() {
    DIR_ACTUAL=""
    cd -- "$RAIZ"
}

ir_a() {
    validar_ruta "$1"
    mkdir -p -- "$RAIZ/$1"
    cd -- "$RAIZ/$1"
    DIR_ACTUAL="$1"
}

leer() {
    local rel
    rel="$(rel_actual "$1")"
    validar_ruta "$rel"
    [[ -f "$RAIZ/$rel" ]] || return 1
    cat -- "$RAIZ/$rel"
}

respaldar() {
    local rel="$1"
    [[ -n $RESPALDO ]] || RESPALDO="$RAIZ/.respaldo/$(date +%Y%m%d-%H%M%S)"
    mkdir -p -- "$(dirname -- "$RESPALDO/$rel")"
    cp -p -- "$RAIZ/$rel" "$RESPALDO/$rel"
}

eliminar() {
    local rel
    rel="$(rel_actual "$1")"
    validar_ruta "$rel"
    [[ -f "$RAIZ/$rel" ]] || return 0
    respaldar "$rel"
    rm -f -- "$RAIZ/$rel"
}

escribir() {
    local rel destino tmp
    rel="$(rel_actual "$1")"
    validar_ruta "$rel"
    destino="$RAIZ/$rel"
    tmp="$(mktemp)"
    cat >"$tmp"
    mkdir -p -- "$(dirname -- "$destino")"
    if [[ -e $destino ]]; then
        if cmp -s -- "$tmp" "$destino"; then
            rm -f -- "$tmp"
            SIN_CAMBIOS=$((SIN_CAMBIOS + 1))
            return 0
        fi
        respaldar "$rel"
        rm -f -- "$destino"
        ACTUALIZADOS=$((ACTUALIZADOS + 1))
    else
        CREADOS=$((CREADOS + 1))
    fi
    mv -- "$tmp" "$destino"
    chmod 0644 -- "$destino"
}

crear_si_falta() {
    local rel destino
    rel="$(rel_actual "$1")"
    validar_ruta "$rel"
    destino="$RAIZ/$rel"
    if [[ -e $destino ]]; then
        cat >/dev/null
        OMITIDOS=$((OMITIDOS + 1))
        return 0
    fi
    escribir "$1"
}

vacio() { escribir "$1" </dev/null; }
vacio_si_falta() { crear_si_falta "$1" </dev/null; }

asegurar_lineas() {
    local archivo="$1" contenido="" linea
    shift
    [[ -f "$RAIZ/$archivo" ]] && contenido="$(<"$RAIZ/$archivo")"
    for linea in "$@"; do
        grep -qxF -- "$linea" <<<"$contenido" || contenido+=$'\n'"$linea"
    done
    printf '%s\n' "${contenido#$'\n'}" | escribir "$archivo"
}

asegurar_claves() {
    local archivo="$1" contenido="" clave
    shift
    [[ -f "$RAIZ/$archivo" ]] && contenido="$(<"$RAIZ/$archivo")"
    for clave in "$@"; do
        grep -q -- "^${clave}=" <<<"$contenido" || contenido+=$'\n'"${clave}="
    done
    printf '%s\n' "${contenido#$'\n'}" | escribir "$archivo"
}

resolver_raiz() {
    local candidato="${1:-}" aqui
    if [[ -z $candidato ]]; then
        aqui="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
        if [[ -f "$aqui/manage.py" ]]; then
            candidato="$aqui"
        elif [[ -f "$PWD/manage.py" ]]; then
            candidato="$PWD"
        else
            candidato="$RAIZ_POR_DEFECTO"
        fi
    fi
    [[ -d $candidato ]] || fallar "No existe el directorio raiz: $candidato"
    RAIZ="$(cd -- "$candidato" && pwd -P)"
    [[ -f "$RAIZ/manage.py" && -d "$RAIZ/config" ]] || fallar "No parece la raiz del proyecto Django: $RAIZ"
}


ayuda() {
    cat <<'__FIN__'
Uso: generar-fase9a.sh [opciones] [RAIZ_DEL_PROYECTO]

  -h, --ayuda    muestra esta ayuda

Fase 9A: app reportes (consultas agregadas, cache de 60 s), Chart.js solo en los
dashboards, dashboard del administrador y panel del operador con datos reales.
  - Venta = factura no anulada por fecha de emision; cobrado = pago confirmado por
    fecha de pago. KPIs del mes actual; graficos con presets 30 dias / 6 meses / 12 meses.
  - El operador no ve ventas ni cobros globales, solo conteos y su trabajo pendiente.
No cambia el esquema: no genera migraciones nuevas.
__FIN__
}

PROPUESTAS=()

declare -A HASHES_STUB=(
    [apps/portal/administrator/views/dashboard.py]=cd4a81c10218d2e67863863e5a34f9641f5161d8dbf3e7cec76ce978fde5430f
    [apps/portal/operator/views/panel.py]=37baafb277098bc8ca4f32189e076049d71afb9849eff39dc36daf68ece478ef
    [templates/administrator/dashboard.html]=bd9f9b83aaf3bcb6361dd682b0fb27cbe9a9acf6dd4db967aada82c479af7eb9
    [templates/operator/panel.html]=aded11370b3db072a26c931a8df999ef3aadefa9eba1873dcdcbce88fee9a2de
    [static/js/vistas/administrator/dashboard.js]=79bb5e1324794c0894a13c3359a19cb3d2da5604f8a070782e77fe7f1950f7d7
)

escribir_stub() {
    local rel destino tmp actual
    rel="$(rel_actual "$1")"
    validar_ruta "$rel"
    destino="$RAIZ/$rel"
    tmp="$(mktemp)"
    cat >"$tmp"
    if [[ ! -e $destino ]]; then
        mkdir -p -- "$(dirname -- "$destino")"
        mv -- "$tmp" "$destino"
        chmod 0644 -- "$destino"
        CREADOS=$((CREADOS + 1))
        return 0
    fi
    if cmp -s -- "$tmp" "$destino"; then
        rm -f -- "$tmp"
        SIN_CAMBIOS=$((SIN_CAMBIOS + 1))
        return 0
    fi
    actual="$(sha256sum -- "$destino" | cut -d' ' -f1)"
    if [[ ${HASHES_STUB[$rel]:-} == "$actual" ]]; then
        respaldar "$rel"
        rm -f -- "$destino"
        mv -- "$tmp" "$destino"
        chmod 0644 -- "$destino"
        ACTUALIZADOS=$((ACTUALIZADOS + 1))
    else
        mv -- "$tmp" "$destino.propuesta"
        PROPUESTAS+=("$rel")
        OMITIDOS=$((OMITIDOS + 1))
    fi
}

inyectar_bloque() {
    local archivo="$1" nombre="$2" ini fin contenido actual nuevo
    ini="# >>> ${nombre}"
    fin="# <<< ${nombre}"
    contenido="$(cat)"
    actual="$(leer "$archivo")" || fallar "No existe $(rel_actual "$archivo")"
    if [[ $actual == *"$ini"* ]]; then
        nuevo="${actual%%"$ini"*}${ini}"$'\n'"${contenido}"$'\n'"${fin}${actual#*"$fin"}"
    else
        nuevo="${actual}"$'\n\n'"${ini}"$'\n'"${contenido}"$'\n'"${fin}"
    fi
    printf '%s\n' "$nuevo" | escribir "$archivo"
}


verificar_base() {
    [[ -f "$RAIZ/apps/notificaciones/eventos.py" && -f "$RAIZ/apps/portal/notificaciones.py" ]] \
        || fallar "Faltan los archivos de la fase 8. Ejecute primero generar-fase8.sh."
}

# ============================================================
# APP REPORTES (consultas agregadas)
# ============================================================

paso_reportes() {
    info "Reportes: consultas agregadas con cache"
    ir_a "apps/reportes"
    vacio_si_falta "__init__.py"
    ir_a "apps/reportes/selectors"
    vacio_si_falta "__init__.py"
    escribir "reportes.py" <<'__FIN__'
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.core.cache import cache
from django.db.models import Count, F, Q, Sum, Value
from django.db.models.functions import Coalesce, TruncDay, TruncMonth, TruncWeek
from django.utils import timezone

from apps.catalogo.models import Producto
from apps.clientes.models import Cliente
from apps.cotizaciones.models import Cotizacion
from apps.crm.models import SolicitudSoporte
from apps.encargos.models import Encargo, EstadoEncargo
from apps.facturacion.models import EstadoFactura, Factura, FacturaDetalle
from apps.pagos.models import EstadoPago, Pago

RANGOS = {"30d": "Últimos 30 días", "6m": "Últimos 6 meses", "12m": "Últimos 12 meses"}
CACHE_SEGUNDOS = 60
ESTADOS_COBRO = (
    EstadoFactura.PENDIENTE.value,
    EstadoFactura.PARCIALMENTE_PAGADA.value,
    EstadoFactura.VENCIDA.value,
)
ESTADOS_CERRADOS = (EstadoEncargo.ENTREGADO.value, EstadoEncargo.CANCELADO.value)


def rango_valido(valor):
    return valor if valor in RANGOS else "6m"


def _cero(valor):
    return valor or Decimal("0.00")


def _inicio_dia(fecha):
    return timezone.make_aware(datetime.combine(fecha, time.min))


def _sumar_meses(fecha, meses):
    indice = fecha.year * 12 + fecha.month - 1 + meses
    return date(indice // 12, indice % 12 + 1, 1)


def periodo(rango, ahora=None):
    rango = rango_valido(rango)
    hoy = timezone.localtime(ahora or timezone.now()).date()
    if rango == "30d":
        pasos = [hoy - timedelta(days=29 - i) for i in range(30)]
        return {"rango": rango, "pasos": pasos, "trunc": TruncDay, "formato": "%d/%m", "inicio": _inicio_dia(pasos[0])}
    meses = 6 if rango == "6m" else 12
    primero = _sumar_meses(hoy.replace(day=1), -(meses - 1))
    pasos = [_sumar_meses(primero, i) for i in range(meses)]
    return {"rango": rango, "pasos": pasos, "trunc": TruncMonth, "formato": "%m/%Y", "inicio": _inicio_dia(pasos[0])}


def periodo_semanal(semanas=8, ahora=None):
    hoy = timezone.localtime(ahora or timezone.now()).date()
    lunes = hoy - timedelta(days=hoy.weekday())
    pasos = [lunes - timedelta(weeks=semanas - 1 - i) for i in range(semanas)]
    return {"pasos": pasos, "trunc": TruncWeek, "formato": "%d/%m", "inicio": _inicio_dia(pasos[0])}


def _serie(consulta, campo, agregado, per):
    filas = (
        consulta.filter(**{f"{campo}__gte": per["inicio"]})
        .annotate(bucket=per["trunc"](campo))
        .values("bucket")
        .annotate(valor=agregado)
        .order_by("bucket")
    )
    datos = {}
    for fila in filas:
        clave = fila["bucket"]
        clave = timezone.localtime(clave).date() if isinstance(clave, datetime) else clave
        datos[clave] = float(fila["valor"] or 0)
    return [datos.get(paso, 0.0) for paso in per["pasos"]]


def _grafico(etiquetas, series, dinero=False):
    return {"etiquetas": etiquetas, "series": [{"nombre": n, "valores": v} for n, v in series], "dinero": dinero}


def _facturas_vencidas(ahora):
    return Factura.objects.filter(
        Q(estado=EstadoFactura.VENCIDA)
        | Q(
            estado__in=[EstadoFactura.PENDIENTE, EstadoFactura.PARCIALMENTE_PAGADA],
            saldo_pendiente__gt=0,
            fecha_vencimiento__lt=ahora,
        )
    )


def _encargos_por_estado():
    conteos = dict(Encargo.objects.values_list("estado").annotate(total=Count("pk")))
    etiquetas = [etiqueta for _, etiqueta in EstadoEncargo.choices]
    return _grafico(etiquetas, [("Encargos", [conteos.get(valor, 0) for valor, _ in EstadoEncargo.choices])])


def kpis_admin(ahora=None):
    ahora = ahora or timezone.now()
    inicio_mes = _inicio_dia(timezone.localtime(ahora).date().replace(day=1))
    facturas = Factura.objects.exclude(estado=EstadoFactura.ANULADA)
    return {
        "ventas_mes": _cero(facturas.filter(fecha_emision__gte=inicio_mes).aggregate(t=Sum("total"))["t"]),
        "cobrado_mes": _cero(
            Pago.objects.filter(estado=EstadoPago.CONFIRMADO, fecha_pago__gte=inicio_mes).aggregate(t=Sum("monto"))["t"]
        ),
        "por_cobrar": _cero(
            Factura.objects.filter(estado__in=ESTADOS_COBRO).aggregate(t=Sum("saldo_pendiente"))["t"]
        ),
        "facturas_vencidas": _facturas_vencidas(ahora).count(),
        "productos_bajo_stock": Producto.objects.filter(activo=True, stock__lte=F("stock_minimo")).count(),
        "clientes_nuevos": Cliente.objects.filter(creado_en__gte=inicio_mes).count(),
    }


def conversion_cotizaciones(per):
    cotizaciones = Cotizacion.objects.filter(fecha_emision__gte=per["inicio"])
    cerradas = cotizaciones.filter(estado__in=["ACEPTADA", "RECHAZADA", "VENCIDA"]).count()
    if not cerradas:
        return None
    return round(cotizaciones.filter(estado="ACEPTADA").count() * 100 / cerradas, 1)


def graficos_admin(per):
    etiquetas = [paso.strftime(per["formato"]) for paso in per["pasos"]]
    ventas = _serie(Factura.objects.exclude(estado=EstadoFactura.ANULADA), "fecha_emision", Sum("total"), per)
    cobros = _serie(Pago.objects.filter(estado=EstadoPago.CONFIRMADO), "fecha_pago", Sum("monto"), per)
    lineas = FacturaDetalle.objects.exclude(factura__estado=EstadoFactura.ANULADA).filter(
        factura__fecha_emision__gte=per["inicio"]
    )
    por_tipo = lineas.aggregate(
        servicios=Sum("subtotal", filter=Q(servicio__isnull=False)),
        productos=Sum("subtotal", filter=Q(producto__isnull=False)),
        otros=Sum("subtotal", filter=Q(servicio__isnull=True, producto__isnull=True)),
    )
    top = (
        lineas.annotate(nombre=Coalesce("producto__nombre", "servicio__nombre", Value("Sin catálogo")))
        .values("nombre")
        .annotate(total=Sum("subtotal"))
        .order_by("-total")[:5]
    )
    return {
        "ventas_cobros": _grafico(etiquetas, [("Ventas", ventas), ("Cobros", cobros)], dinero=True),
        "ingresos_tipo": _grafico(
            ["Servicios", "Productos", "Otros"],
            [("Ingresos", [float(_cero(por_tipo[c])) for c in ("servicios", "productos", "otros")])],
            dinero=True,
        ),
        "top_ventas": _grafico(
            [fila["nombre"] for fila in top], [("Ingresos", [float(fila["total"] or 0) for fila in top])], dinero=True
        ),
        "encargos_estado": _encargos_por_estado(),
    }


def _calcular_admin(rango):
    per = periodo(rango)
    ahora = timezone.now()
    return {
        "rango": per["rango"],
        "kpis": kpis_admin(ahora),
        "conversion": conversion_cotizaciones(per),
        "graficos": graficos_admin(per),
        "stock_bajo": [
            {"pk": p.pk, "sku": p.sku, "nombre": p.nombre, "stock": p.stock, "minimo": p.stock_minimo}
            for p in Producto.objects.filter(activo=True, stock__lte=F("stock_minimo")).order_by("stock", "nombre")[:8]
        ],
        "vencidas": [
            {"pk": f.pk, "numero": f.numero_factura, "cliente": f.nombre_facturacion, "saldo": f.saldo_pendiente, "vence": f.fecha_vencimiento}
            for f in _facturas_vencidas(ahora).order_by("fecha_vencimiento")[:8]
        ],
    }


def datos_admin(rango="6m"):
    rango = rango_valido(rango)
    return cache.get_or_set(f"reportes:admin:{rango}", lambda: _calcular_admin(rango), CACHE_SEGUNDOS)


def _calcular_operador():
    ahora = timezone.now()
    per = periodo_semanal()
    etiquetas = [paso.strftime(per["formato"]) for paso in per["pasos"]]
    return {
        "kpis": {
            "cotizaciones_por_atender": Cotizacion.objects.filter(estado__in=["SOLICITADA", "BORRADOR"]).count(),
            "encargos_activos": Encargo.objects.exclude(estado__in=ESTADOS_CERRADOS).count(),
            "facturas_vencidas": _facturas_vencidas(ahora).count(),
            "soporte_abierto": SolicitudSoporte.objects.filter(estado__in=["ABIERTA", "EN_PROCESO"]).count(),
        },
        "graficos": {
            "encargos_estado": _encargos_por_estado(),
            "carga_semanal": _grafico(
                etiquetas,
                [
                    ("Encargos nuevos", _serie(Encargo.objects.all(), "fecha_solicitud", Count("pk"), per)),
                    ("Cotizaciones nuevas", _serie(Cotizacion.objects.all(), "fecha_emision", Count("pk"), per)),
                ],
            ),
        },
    }


def datos_operador():
    return cache.get_or_set("reportes:operador", _calcular_operador, CACHE_SEGUNDOS)


def trabajo_operador(usuario):
    sin_cerrar = Encargo.objects.exclude(estado__in=ESTADOS_CERRADOS)
    propios = sin_cerrar.filter(empleado_responsable__usuario=usuario)
    mio_o_libre = Q(usuario_responsable__isnull=True) | Q(usuario_responsable=usuario)
    return {
        "mis_encargos_total": propios.count(),
        "mis_encargos": list(
            propios.select_related("cliente").order_by("fecha_entrega_estimada", "fecha_solicitud")[:8]
        ),
        "cotizaciones": list(
            Cotizacion.objects.filter(estado__in=["SOLICITADA", "BORRADOR"])
            .filter(mio_o_libre)
            .select_related("cliente")
            .order_by("fecha_emision")[:8]
        ),
        "soporte": list(
            SolicitudSoporte.objects.filter(estado__in=["ABIERTA", "EN_PROCESO"])
            .filter(mio_o_libre)
            .select_related("cliente")
            .order_by("creado_en")[:8]
        ),
    }
__FIN__
}

# ============================================================
# CHART.JS (solo en los dashboards) Y COMPONENTES
# ============================================================

paso_graficos() {
    info "Graficos: graficos.js y tarjeta de indicador"
    ir_a "static/js/components"
    escribir "graficos.js" <<'__FIN__'
(function ($) {
    "use strict";

    var PALETA = ["primary", "success", "warning", "danger", "info", "secondary", "purple"];

    function color(nombre) {
        var valor = getComputedStyle(document.documentElement).getPropertyValue("--bs-" + nombre).trim();
        return valor || "#0d6efd";
    }

    function colores(cantidad) {
        var lista = [];
        for (var i = 0; i < cantidad; i++) { lista.push(color(PALETA[i % PALETA.length])); }
        return lista;
    }

    function formato(valor, dinero) {
        return dinero ? "$" + Number(valor).toFixed(2) : String(valor);
    }

    function sinDatos(datos) {
        return datos.series.every(function (serie) {
            return serie.valores.every(function (valor) { return !valor; });
        });
    }

    function construir(canvas, datos) {
        var tipo = canvas.getAttribute("data-tipo") || "bar";
        var circular = tipo === "doughnut" || tipo === "pie";
        var horizontal = canvas.getAttribute("data-eje") === "y";
        var paleta = colores(circular ? datos.etiquetas.length : datos.series.length);
        var conjuntos = datos.series.map(function (serie, i) {
            return {
                label: serie.nombre,
                data: serie.valores,
                backgroundColor: circular ? paleta : paleta[i],
                borderColor: circular ? paleta : paleta[i],
                tension: 0.25
            };
        });
        var escalas = {};
        if (!circular) {
            escalas[horizontal ? "x" : "y"] = {
                beginAtZero: true,
                ticks: { callback: function (valor) { return datos.dinero ? "$" + valor : valor; } }
            };
        }
        new Chart(canvas, {
            type: tipo,
            data: { labels: datos.etiquetas, datasets: conjuntos },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: horizontal ? "y" : "x",
                plugins: {
                    legend: { display: conjuntos.length > 1 || circular },
                    tooltip: {
                        callbacks: {
                            label: function (contexto) {
                                var valor = circular ? contexto.parsed : (horizontal ? contexto.parsed.x : contexto.parsed.y);
                                return (contexto.dataset.label || "") + ": " + formato(valor, datos.dinero);
                            }
                        }
                    }
                },
                scales: escalas
            }
        });
    }

    $(function () {
        var origen = document.getElementById("datos-graficos");
        if (!origen || typeof Chart === "undefined") { return; }
        var todos = JSON.parse(origen.textContent);
        $("canvas[data-grafico]").each(function () {
            var datos = todos[this.getAttribute("data-grafico")];
            if (!datos) { return; }
            if (sinDatos(datos)) {
                $(this).closest(".ratio").replaceWith($('<p class="text-body-secondary mb-0"></p>').text("Sin datos en este período."));
                return;
            }
            construir(this, datos);
        });
    });
})(jQuery);
__FIN__

    ir_a "templates/components"
    escribir "kpi.html" <<'__FIN__'
<div class="col">
  <div class="card h-100">
    <div class="card-body">
      <div class="small text-body-secondary">{{ titulo }}</div>
      <div class="h3 mb-0">{{ prefijo }}{% if decimales %}{{ valor|floatformat:decimales }}{% else %}{{ valor }}{% endif %}{{ sufijo }}</div>
      {% if ayuda %}<div class="small text-body-secondary">{{ ayuda }}</div>{% endif %}
    </div>
  </div>
</div>
__FIN__
}

# ============================================================
# DASHBOARDS
# ============================================================

paso_dashboards() {
    info "Dashboards: administrador y operador"

    ir_a "apps/portal/administrator/views"
    escribir_stub "dashboard.py" <<'__FIN__'
from django.views.generic import TemplateView

from apps.portal.mixins import AdministradorRequeridoMixin
from apps.reportes.selectors import reportes as selectors


class DashboardView(AdministradorRequeridoMixin, TemplateView):
    template_name = "administrator/dashboard.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        datos = selectors.datos_admin(self.request.GET.get("rango", "6m"))
        contexto.update(datos)
        contexto["rangos"] = list(selectors.RANGOS.items())
        return contexto
__FIN__

    ir_a "apps/portal/operator/views"
    escribir_stub "panel.py" <<'__FIN__'
from django.views.generic import TemplateView

from apps.portal.mixins import OperadorRequeridoMixin
from apps.reportes.selectors import reportes as selectors


class PanelView(OperadorRequeridoMixin, TemplateView):
    template_name = "operator/panel.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(selectors.datos_operador())
        contexto["trabajo"] = selectors.trabajo_operador(self.request.user)
        return contexto
__FIN__

    ir_a "templates/administrator"
    escribir_stub "dashboard.html" <<'__FIN__'
{% extends "layouts/dashboard.html" %}
{% load static %}

{% block titulo %}Dashboard{% endblock %}

{% block contenido %}
<div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
  <h1 class="h3 mb-0">Dashboard administrativo</h1>
  <form method="get">
    <select name="rango" class="form-select" aria-label="Período de los gráficos">
      {% for clave, texto in rangos %}<option value="{{ clave }}"{% if clave == rango %} selected{% endif %}>{{ texto }}</option>{% endfor %}
    </select>
  </form>
</div>

<div class="row row-cols-2 row-cols-lg-3 row-cols-xl-6 g-3 mb-4">
  {% include "components/kpi.html" with titulo="Ventas del mes" valor=kpis.ventas_mes prefijo="$" decimales=2 %}
  {% include "components/kpi.html" with titulo="Cobrado del mes" valor=kpis.cobrado_mes prefijo="$" decimales=2 %}
  {% include "components/kpi.html" with titulo="Por cobrar" valor=kpis.por_cobrar prefijo="$" decimales=2 %}
  {% include "components/kpi.html" with titulo="Facturas vencidas" valor=kpis.facturas_vencidas %}
  {% include "components/kpi.html" with titulo="Productos bajo stock" valor=kpis.productos_bajo_stock %}
  {% include "components/kpi.html" with titulo="Clientes nuevos (mes)" valor=kpis.clientes_nuevos %}
</div>
<div class="row row-cols-1 row-cols-md-2 g-3 mb-4">
  {% if conversion is not None %}{% include "components/kpi.html" with titulo="Conversión de cotizaciones" valor=conversion sufijo=" %" ayuda="Aceptadas sobre cotizaciones cerradas en el período" %}{% else %}{% include "components/kpi.html" with titulo="Conversión de cotizaciones" valor="-" ayuda="Aún no hay cotizaciones cerradas en el período" %}{% endif %}
</div>

<div class="row g-3 mb-4">
  <div class="col-lg-8"><div class="card h-100"><div class="card-body">
    <h2 class="h6">Ventas frente a cobros</h2>
    <div class="ratio ratio-16x9"><canvas data-grafico="ventas_cobros" data-tipo="line"></canvas></div>
  </div></div></div>
  <div class="col-lg-4"><div class="card h-100"><div class="card-body">
    <h2 class="h6">Ingresos por servicios y productos</h2>
    <div class="ratio ratio-1x1"><canvas data-grafico="ingresos_tipo" data-tipo="doughnut"></canvas></div>
  </div></div></div>
  <div class="col-lg-6"><div class="card h-100"><div class="card-body">
    <h2 class="h6">Lo más vendido (top 5)</h2>
    <div class="ratio ratio-16x9"><canvas data-grafico="top_ventas" data-tipo="bar" data-eje="y"></canvas></div>
  </div></div></div>
  <div class="col-lg-6"><div class="card h-100"><div class="card-body">
    <h2 class="h6">Encargos por estado</h2>
    <div class="ratio ratio-16x9"><canvas data-grafico="encargos_estado" data-tipo="bar"></canvas></div>
  </div></div></div>
</div>

<div class="row g-3">
  <div class="col-lg-6">
    <h2 class="h6">Productos con stock bajo</h2>
    <ul class="list-group">
      {% for p in stock_bajo %}<li class="list-group-item d-flex justify-content-between"><a href="{% url 'administrator:producto_editar' p.pk %}">{{ p.sku }} · {{ p.nombre }}</a><span>{{ p.stock }} / mín. {{ p.minimo }}</span></li>{% empty %}<li class="list-group-item text-body-secondary">Ningún producto bajo el mínimo.</li>{% endfor %}
    </ul>
  </div>
  <div class="col-lg-6">
    <h2 class="h6">Facturas vencidas</h2>
    <ul class="list-group">
      {% for f in vencidas %}<li class="list-group-item d-flex justify-content-between"><a href="{% url 'operator:factura' f.pk %}">{{ f.numero }} · {{ f.cliente }}</a><span>${{ f.saldo|floatformat:2 }} · {{ f.vence|date:"d/m/Y" }}</span></li>{% empty %}<li class="list-group-item text-body-secondary">No hay facturas vencidas.</li>{% endfor %}
    </ul>
  </div>
</div>
<p class="small text-body-secondary mt-3">Los datos se actualizan cada minuto.</p>
{% endblock %}

{% block scripts %}
{{ graficos|json_script:"datos-graficos" }}
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script src="{% static 'js/components/graficos.js' %}"></script>
{% endblock %}
__FIN__

    ir_a "templates/operator"
    escribir_stub "panel.html" <<'__FIN__'
{% extends "layouts/dashboard.html" %}
{% load static bootstrap %}

{% block titulo %}Panel operativo{% endblock %}

{% block contenido %}
<h1 class="h3 mb-3">Panel operativo</h1>
<div class="row row-cols-2 row-cols-lg-5 g-3 mb-4">
  {% include "components/kpi.html" with titulo="Cotizaciones por atender" valor=kpis.cotizaciones_por_atender %}
  {% include "components/kpi.html" with titulo="Encargos activos" valor=kpis.encargos_activos %}
  {% include "components/kpi.html" with titulo="Mis encargos" valor=trabajo.mis_encargos_total %}
  {% include "components/kpi.html" with titulo="Facturas vencidas" valor=kpis.facturas_vencidas %}
  {% include "components/kpi.html" with titulo="Soporte abierto" valor=kpis.soporte_abierto %}
</div>

<div class="row g-3 mb-4">
  <div class="col-lg-6"><div class="card h-100"><div class="card-body">
    <h2 class="h6">Encargos por estado</h2>
    <div class="ratio ratio-16x9"><canvas data-grafico="encargos_estado" data-tipo="bar"></canvas></div>
  </div></div></div>
  <div class="col-lg-6"><div class="card h-100"><div class="card-body">
    <h2 class="h6">Carga de las últimas 8 semanas</h2>
    <div class="ratio ratio-16x9"><canvas data-grafico="carga_semanal" data-tipo="line"></canvas></div>
  </div></div></div>
</div>

<h2 class="h5">Mi trabajo pendiente</h2>
<div class="row g-3">
  <div class="col-lg-4">
    <h3 class="h6">Cotizaciones por atender</h3>
    <ul class="list-group">
      {% for c in trabajo.cotizaciones %}<li class="list-group-item"><a href="{% url 'operator:cotizacion' c.pk %}">{{ c.codigo }}</a> {{ c.estado|badge:c.get_estado_display }}<br><small class="text-body-secondary">{{ c.cliente }}</small></li>{% empty %}<li class="list-group-item text-body-secondary">Nada pendiente.</li>{% endfor %}
    </ul>
  </div>
  <div class="col-lg-4">
    <h3 class="h6">Mis encargos activos</h3>
    <ul class="list-group">
      {% for e in trabajo.mis_encargos %}<li class="list-group-item"><a href="{% url 'operator:encargo' e.pk %}">{{ e.codigo }}</a> {{ e.estado|badge:e.get_estado_display }}<br><small class="text-body-secondary">{{ e.cliente }}{% if e.fecha_entrega_estimada %} · entrega {{ e.fecha_entrega_estimada|date:"d/m/Y" }}{% endif %}</small></li>{% empty %}<li class="list-group-item text-body-secondary">No tiene encargos asignados.</li>{% endfor %}
    </ul>
  </div>
  <div class="col-lg-4">
    <h3 class="h6">Soporte</h3>
    <ul class="list-group">
      {% for s in trabajo.soporte %}<li class="list-group-item"><a href="{% url 'operator:soporte_detalle' s.pk %}">#{{ s.pk }} · {{ s.asunto }}</a><br><small class="text-body-secondary">{{ s.cliente }}</small></li>{% empty %}<li class="list-group-item text-body-secondary">Sin solicitudes pendientes.</li>{% endfor %}
    </ul>
  </div>
</div>
<p class="small text-body-secondary mt-3">Los indicadores generales se actualizan cada minuto.</p>
{% endblock %}

{% block scripts %}
{{ graficos|json_script:"datos-graficos" }}
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script src="{% static 'js/components/graficos.js' %}"></script>
{% endblock %}
__FIN__

    ir_a "static/js/vistas/administrator"
    escribir_stub "dashboard.js" <<'__FIN__'
$(function () {
    $("select[name=rango]").on("change", function () { this.form.requestSubmit(); });
});
__FIN__
}

# ============================================================
# PRUEBAS
# ============================================================

paso_pruebas() {
    info "Pruebas de reportes y dashboards"
    ir_a "apps/reportes/tests"
    vacio_si_falta "__init__.py"
    crear_si_falta "test_reportes.py" <<'__FIN__'
import uuid
from datetime import timedelta
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.catalogo.models import Producto
from apps.cotizaciones.tests.utiles import crear_cliente, crear_personal, crear_servicio
from apps.encargos.models import Encargo
from apps.facturacion.models import EstadoFactura, Factura, FacturaDetalle
from apps.pagos.models import EstadoPago, MetodoPago, Pago
from apps.reportes.selectors import reportes as sel
from apps.usuarios.constants import GRUPO_ADMINISTRADOR
from apps.usuarios.models import Empleado
from apps.usuarios.tests.utiles import crear_usuario, iniciar_sesion


def factura(cliente, total="100.00", estado=EstadoFactura.PENDIENTE, saldo=None, emision=None, vence=None):
    return Factura.objects.create(
        cliente=cliente, numero_factura=f"FAC-T{uuid.uuid4().hex[:8].upper()}", nombre_facturacion="Cliente",
        subtotal=Decimal(total), total=Decimal(total),
        saldo_pendiente=Decimal(saldo if saldo is not None else (total if estado != EstadoFactura.ANULADA else "0.00")),
        estado=estado, fecha_emision=emision or timezone.now(), fecha_vencimiento=vence,
    )


def detalle(f, monto, servicio=None, producto=None):
    return FacturaDetalle.objects.create(
        factura=f, servicio=servicio, producto=producto, descripcion="Linea", cantidad=Decimal("1"),
        precio_unitario=Decimal(monto), subtotal=Decimal(monto),
    )


class BaseReportes(TestCase):
    def setUp(self):
        cache.clear()
        self.usuario, self.cliente = crear_cliente("cliente@example.com")
        self.metodo, _ = MetodoPago.objects.get_or_create(nombre="Efectivo")


class IndicadoresTests(BaseReportes):
    def test_kpis_excluyen_anuladas_y_suman_cobros(self):
        f = factura(self.cliente, "100.00")
        factura(self.cliente, "50.00", estado=EstadoFactura.ANULADA)
        Pago.objects.create(factura=f, metodo_pago=self.metodo, monto=Decimal("40.00"), estado=EstadoPago.CONFIRMADO)
        Pago.objects.create(factura=f, metodo_pago=self.metodo, monto=Decimal("10.00"), estado=EstadoPago.CANCELADO)
        kpis = sel.kpis_admin()
        self.assertEqual(kpis["ventas_mes"], Decimal("100.00"))
        self.assertEqual(kpis["cobrado_mes"], Decimal("40.00"))
        self.assertEqual(kpis["por_cobrar"], Decimal("100.00"))

    def test_facturas_vencidas_y_stock_bajo_y_clientes_nuevos(self):
        factura(self.cliente, emision=timezone.now() - timedelta(days=10), vence=timezone.now() - timedelta(days=2))
        factura(self.cliente, vence=timezone.now() + timedelta(days=5))
        Producto.objects.create(sku="BAJ-001", nombre="Bajo", precio=Decimal("1.00"), stock=1, stock_minimo=3)
        Producto.objects.create(sku="OK-001", nombre="Bien", precio=Decimal("1.00"), stock=9, stock_minimo=3)
        kpis = sel.kpis_admin()
        self.assertEqual(kpis["facturas_vencidas"], 1)
        self.assertEqual(kpis["productos_bajo_stock"], 1)
        self.assertEqual(kpis["clientes_nuevos"], 1)

    def test_valores_en_cero_sin_datos(self):
        kpis = sel.kpis_admin()
        self.assertEqual((kpis["ventas_mes"], kpis["cobrado_mes"], kpis["por_cobrar"]), (Decimal("0.00"),) * 3)
        self.assertIsNone(sel.conversion_cotizaciones(sel.periodo("6m")))


class GraficosTests(BaseReportes):
    def test_cantidad_de_periodos_por_rango(self):
        for rango, cantidad in (("30d", 30), ("6m", 6), ("12m", 12), ("invalido", 6)):
            self.assertEqual(len(sel.periodo(rango)["pasos"]), cantidad, rango)

    def test_serie_mensual_ubica_la_venta_en_su_mes(self):
        hace_mes_y_medio = timezone.now() - timedelta(days=45)
        factura(self.cliente, "70.00", emision=hace_mes_y_medio)
        factura(self.cliente, "30.00")
        graficos = sel.graficos_admin(sel.periodo("6m"))["ventas_cobros"]
        ventas = graficos["series"][0]["valores"]
        etiqueta = timezone.localtime(hace_mes_y_medio).strftime("%m/%Y")
        self.assertEqual(ventas[graficos["etiquetas"].index(etiqueta)], 70.0)
        self.assertEqual(ventas[-1], 30.0)
        self.assertEqual(sum(ventas), 100.0)

    def test_ingresos_por_tipo_y_top(self):
        servicio = crear_servicio("Impresión X")
        producto = Producto.objects.create(sku="TOP-001", nombre="Producto Top", precio=Decimal("1.00"), stock=5)
        f = factura(self.cliente, "100.00")
        detalle(f, "60.00", servicio=servicio)
        detalle(f, "30.00", producto=producto)
        detalle(f, "10.00")
        graficos = sel.graficos_admin(sel.periodo("6m"))
        self.assertEqual(graficos["ingresos_tipo"]["series"][0]["valores"], [60.0, 30.0, 10.0])
        self.assertEqual(graficos["top_ventas"]["etiquetas"], ["Impresión X", "Producto Top", "Sin catálogo"])

    def test_encargos_por_estado_cubre_todos_los_estados(self):
        Encargo.objects.create(cliente=self.cliente, codigo="ENC-R-1", descripcion="x")
        grafico = sel.graficos_admin(sel.periodo("6m"))["encargos_estado"]
        self.assertEqual(len(grafico["etiquetas"]), 8)
        self.assertEqual(sum(grafico["series"][0]["valores"]), 1)

    def test_carga_semanal_del_operador(self):
        Encargo.objects.create(cliente=self.cliente, codigo="ENC-R-2", descripcion="x")
        semanal = sel.datos_operador()["graficos"]["carga_semanal"]
        self.assertEqual(len(semanal["etiquetas"]), 8)
        self.assertEqual(semanal["series"][0]["valores"][-1], 1)


class CacheYTrabajoTests(BaseReportes):
    def test_segunda_lectura_usa_cache(self):
        sel.datos_admin("6m")
        with self.assertNumQueries(0):
            sel.datos_admin("6m")

    def test_trabajo_del_operador_solo_incluye_lo_suyo(self):
        operador = crear_personal("operador@example.com")
        empleado = Empleado.objects.create(usuario=operador, codigo_empleado="EMP-R1", cargo="Operador")
        Encargo.objects.create(cliente=self.cliente, codigo="ENC-MIO", descripcion="x", empleado_responsable=empleado)
        Encargo.objects.create(cliente=self.cliente, codigo="ENC-OTRO", descripcion="x")
        trabajo = sel.trabajo_operador(operador)
        self.assertEqual([e.codigo for e in trabajo["mis_encargos"]], ["ENC-MIO"])
        self.assertEqual(trabajo["mis_encargos_total"], 1)


class VistasDashboardTests(BaseReportes):
    def test_dashboard_admin_con_y_sin_datos(self):
        admin = crear_usuario("admin@example.com", GRUPO_ADMINISTRADOR, is_staff=True)
        iniciar_sesion(self.client, admin)
        respuesta = self.client.get(reverse("administrator:dashboard"))
        self.assertEqual(respuesta.status_code, 200)
        contenido = respuesta.content.decode()
        self.assertIn("datos-graficos", contenido)
        self.assertIn("chart.js@4.4.1", contenido)
        self.assertNotIn(" style=", contenido)
        f = factura(self.cliente, "80.00")
        detalle(f, "80.00")
        cache.clear()
        for rango in ("30d", "6m", "12m", "otro"):
            self.assertEqual(self.client.get(reverse("administrator:dashboard"), {"rango": rango}).status_code, 200)

    def test_operador_no_ve_dinero_global_ni_el_dashboard_admin(self):
        operador = crear_personal("operador@example.com")
        iniciar_sesion(self.client, operador)
        self.assertEqual(self.client.get(reverse("administrator:dashboard")).status_code, 403)
        respuesta = self.client.get(reverse("operator:panel"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, "Ventas del mes")
        self.assertNotContains(respuesta, "Cobrado del mes")
        self.assertContains(respuesta, "Mi trabajo pendiente")

    def test_cliente_no_accede_a_los_paneles_del_personal(self):
        iniciar_sesion(self.client, self.usuario)
        self.assertEqual(self.client.get(reverse("operator:panel")).status_code, 403)
        self.assertEqual(self.client.get(reverse("administrator:dashboard")).status_code, 403)

    def test_chart_js_solo_se_carga_en_los_dashboards(self):
        admin = crear_usuario("admin2@example.com", GRUPO_ADMINISTRADOR, is_staff=True)
        iniciar_sesion(self.client, admin)
        self.assertNotContains(self.client.get(reverse("administrator:inventario")), "chart.js")
__FIN__
}

paso_tasklist() {
    ir_raiz
    [[ -f TASKLIST_USUARIO.txt ]] || return 0
    inyectar_bloque "TASKLIST_USUARIO.txt" "fase-9a" <<'__FIN__'

=== L. FASE 9A: DASHBOARDS (generar-fase9a.sh) ===
Definiciones: venta = factura no anulada por fecha de emision; cobrado = pago confirmado
por fecha de pago; KPIs del mes actual; graficos con 30 dias / 6 meses / 12 meses.
Los datos se cachean 60 segundos (cache local: con varios procesos cada uno tiene la suya).
[ ] L1. python manage.py test   (envieme el resumen). No hay migraciones nuevas.
[ ] L2. Administrador > Dashboard con la base del demo: tarjetas, 4 graficos y 2 listas.
        Cambie el periodo (30 dias / 6 / 12 meses): los graficos cambian; la consola sin errores.
[ ] L3. Cree una factura y un pago: tras ~1 minuto los totales del mes y el grafico cambian.
[ ] L4. Compruebe un total a mano: ventas del mes = suma de facturas del mes no anuladas;
        cobrado = suma de pagos confirmados del mes. SQL en Supabase para confirmarlo.
[ ] L5. Anule una factura y cancele un pago: deben dejar de contar en sus totales.
[ ] L6. Operador > Panel: sin ventas ni cobros; "Mi trabajo pendiente" muestra solo lo
        asignado a el (cotizaciones libres o suyas, sus encargos, soporte libre o suyo).
[ ] L7. Con base casi vacia: los graficos muestran "Sin datos en este periodo", sin errores.
[ ] L8. Chart.js solo se descarga en el dashboard y el panel del operador (pestaña Red del
        navegador en otras paginas: no debe aparecer).
[ ] L9. Pantalla movil: las tarjetas pasan a 2 columnas y los graficos se ajustan al ancho.
__FIN__
}

paso_verificacion() {
    ir_raiz
    local py="python3"
    if [[ -x "$RAIZ/.venv/bin/python" ]]; then
        py="$RAIZ/.venv/bin/python"
    elif [[ -x "$RAIZ/.venv/Scripts/python.exe" ]]; then
        py="$RAIZ/.venv/Scripts/python.exe"
    elif [[ -n ${VIRTUAL_ENV:-} && -x "$VIRTUAL_ENV/bin/python" ]]; then
        py="$VIRTUAL_ENV/bin/python"
    fi
    info "Verificando sintaxis"
    if "$py" -m compileall -q apps config >/dev/null; then
        ok "Sintaxis correcta"
    else
        advertir "Errores de sintaxis: $py -m compileall apps config"
        return 0
    fi
    [[ -f .env ]] || return 0
    if "$py" -c "import django" >/dev/null 2>&1; then
        "$py" manage.py check >/dev/null 2>&1 && ok "manage.py check sin problemas" \
            || advertir "manage.py check reporto problemas; ejecutelo para ver el detalle."
        "$py" manage.py makemigrations --check --dry-run >/dev/null 2>&1 && ok "Sin cambios de esquema pendientes" \
            || advertir "makemigrations --check detecta diferencias; ejecute: python manage.py makemigrations --dry-run"
    fi
}

resumen() {
    echo
    echo "============================================================"
    echo " RESUMEN"
    echo "============================================================"
    echo "Raiz:               $RAIZ"
    echo "Archivos creados:   $CREADOS"
    echo "Actualizados:       $ACTUALIZADOS"
    echo "Sin cambios:        $SIN_CAMBIOS"
    echo "Omitidos/propuestas: $OMITIDOS"
    [[ -n $RESPALDO ]] && echo "Respaldos en:       $RESPALDO"
    if ((${#PROPUESTAS[@]})); then
        echo
        echo "Archivos que usted ya habia editado (version nueva en <archivo>.propuesta):"
        printf '  - %s\n' "${PROPUESTAS[@]}"
    fi
    if ((${#AVISOS[@]})); then
        echo
        echo "Avisos:"
        printf '  - %s\n' "${AVISOS[@]}"
    fi
    echo
    echo "Siguiente: python manage.py test   y la seccion L de TASKLIST_USUARIO.txt."
    echo "============================================================"
}

main() {
    local arg
    for arg in "$@"; do
        case "$arg" in
            -h | --ayuda) ayuda; exit 0 ;;
            -*) fallar "Opcion desconocida: $arg" ;;
            *) RAIZ="$arg" ;;
        esac
    done
    resolver_raiz "$RAIZ"
    verificar_base
    info "Raiz del proyecto: $RAIZ"
    ir_raiz

    paso_reportes
    paso_graficos
    paso_dashboards
    paso_pruebas
    paso_tasklist
    paso_verificacion
    resumen
}

main "$@"
