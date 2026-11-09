(function (global, $) {
    "use strict";

    var TIPOS = {
        success: { clase: "text-bg-success", titulo: "Listo" },
        error: { clase: "text-bg-danger", titulo: "Error" },
        warning: { clase: "text-bg-warning", titulo: "Atención" },
        info: { clase: "text-bg-info", titulo: "Información" }
    };

    function contenedor() {
        var $c = $("#contenedor-toasts");
        if (!$c.length) {
            $c = $('<div id="contenedor-toasts" class="toast-container position-fixed top-0 end-0 p-3" aria-live="polite" aria-atomic="true"></div>');
            $c.appendTo("body");
        }
        return $c;
    }

    function activar(elemento) {
        new bootstrap.Toast(elemento, { delay: 5000 }).show();
    }

    function mostrar(tipo, mensaje) {
        var datos = TIPOS[tipo] || TIPOS.info;
        var $toast = $('<div class="toast align-items-center border-0" role="alert"></div>').addClass(datos.clase);
        var $cuerpo = $('<div class="toast-body"></div>')
            .append($('<strong class="d-block"></strong>').text(datos.titulo))
            .append($("<span></span>").text(mensaje));
        var $cerrar = $('<button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Cerrar"></button>');
        $toast.append($('<div class="d-flex"></div>').append($cuerpo).append($cerrar));
        contenedor().append($toast);
        $toast.on("hidden.bs.toast", function () { $toast.remove(); });
        activar($toast[0]);
    }

    $(function () {
        $("#contenedor-toasts .toast").each(function () { activar(this); });
    });

    global.Toast = { mostrar: mostrar };
})(window, jQuery);
