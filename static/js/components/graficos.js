(function ($) {
    "use strict";

    var PALETA = ["primary", "success", "warning", "danger", "info", "secondary", "purple"];
    var instancias = [];

    function variable(nombre) {
        return getComputedStyle(document.documentElement).getPropertyValue(nombre).trim();
    }

    function color(nombre) {
        return variable("--bs-" + nombre) || "#167C80";
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

    function configurarBase() {
        Chart.defaults.color = variable("--md-text-secondary") || "#52686A";
        Chart.defaults.borderColor = variable("--md-border") || "#D8E1E1";
        Chart.defaults.font.family = "Roboto, system-ui, sans-serif";
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
                borderColor: circular ? variable("--md-surface") : paleta[i],
                borderRadius: circular ? 0 : 6,
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
        return new Chart(canvas, {
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

    function dibujar() {
        var origen = document.getElementById("datos-graficos");
        if (!origen || typeof Chart === "undefined") { return; }
        instancias.forEach(function (grafico) { grafico.destroy(); });
        instancias = [];
        configurarBase();
        var todos = JSON.parse(origen.textContent);
        $("canvas[data-grafico]").each(function () {
            var datos = todos[this.getAttribute("data-grafico")];
            if (!datos) { return; }
            if (sinDatos(datos)) {
                $(this).closest(".ratio").replaceWith($('<p class="text-body-secondary mb-0"></p>').text("Sin datos en este período."));
                return;
            }
            instancias.push(construir(this, datos));
        });
    }

    $(dibujar);
    document.addEventListener("tema:cambio", dibujar);
})(jQuery);
