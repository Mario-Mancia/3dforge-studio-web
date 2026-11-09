(function (global, $) {
    "use strict";

    var TIPOS = {
        success: { icono: "check_circle", titulo: "Listo" },
        error: { icono: "error", titulo: "Error" },
        warning: { icono: "warning", titulo: "Atención" },
        info: { icono: "info", titulo: "Información" }
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
        var clave = TIPOS[tipo] ? tipo : "info";
        var datos = TIPOS[clave];
        var $toast = $('<div class="toast toast-md" role="alert" aria-live="assertive" aria-atomic="true"></div>').addClass("toast-" + clave);
        var $icono = $('<span class="material-symbols-rounded toast-icono" aria-hidden="true"></span>').text(datos.icono);
        var $texto = $('<div class="flex-grow-1"></div>')
            .append($('<strong class="d-block"></strong>').text(datos.titulo))
            .append($("<span></span>").text(mensaje));
        var $cerrar = $('<button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Cerrar"></button>');
        $toast.append($('<div class="d-flex align-items-start gap-3 p-3"></div>').append($icono).append($texto).append($cerrar));
        $toast.append('<div class="toast-progreso"></div>');
        contenedor().append($toast);
        $toast.on("hidden.bs.toast", function () { $toast.remove(); });
        activar($toast[0]);
    }

    $(function () {
        $("#contenedor-toasts .toast").each(function () { activar(this); });
    });

    global.Toast = { mostrar: mostrar };
})(window, jQuery);
