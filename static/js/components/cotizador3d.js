(function ($) {
    "use strict";

    $(function () {
        var $primerError = $(".alert-danger, .is-invalid, .invalid-feedback.d-block").filter(":visible").first();
        if ($primerError.length) { $primerError[0].scrollIntoView({ behavior: "smooth", block: "center" }); }

        var $formulario = $("#form-3d");
        if (!$formulario.length) { return; }

        var urlEstimar = $formulario.data("estimar-url");
        var EXTENSIONES = ["stl", "obj", "3mf"];
        var MAXIMO_BYTES = 50 * 1024 * 1024;
        var CLASES_CONFIANZA = { alta: "text-bg-success", media: "text-bg-warning", baja: "text-bg-danger" };
        var $archivo = $formulario.find("input[type=file][name=archivo]");
        var $panel = $("#resumen-estimacion");
        var analisis = null;
        var peticion = null;
        var temporizador = null;

        function estado(nombre) {
            $panel.find("[data-estado]").prop("hidden", true);
            $panel.find("[data-estado=" + nombre + "]").prop("hidden", false);
        }

        function texto(clave, valor) {
            $panel.find("[data-res=" + clave + "]").text(valor);
        }

        function mostrar(datos) {
            var e = datos.estimacion;
            texto("dimensiones", e.dimensiones_texto);
            texto("gramos", e.gramos);
            texto("tiempo", e.tiempo_texto);
            texto("soportes", e.soportes_texto);
            texto("precio_unitario", e.precio_unitario);
            texto("cantidad", e.cantidad);
            texto("subtotal", e.subtotal);
            texto("impuesto", e.impuesto);
            texto("total", e.total);
            texto("aviso", e.aviso);
            $panel.find("[data-res=confianza]")
                .removeClass("text-bg-success text-bg-warning text-bg-danger")
                .addClass(CLASES_CONFIANZA[e.confianza] || "text-bg-secondary")
                .text(e.confianza_texto);
            var $lista = $panel.find("[data-res=advertencias]").empty();
            e.advertencias.forEach(function (mensaje) { $("<li>").text(mensaje).appendTo($lista); });
            $lista.prop("hidden", !e.advertencias.length);
            estado("resultado");
        }

        function datosFormulario() {
            var datos = new FormData();
            ["csrfmiddlewaretoken", "filamento", "relleno", "calidad", "escala", "unidades", "soportes", "cantidad"].forEach(function (nombre) {
                datos.append(nombre, $formulario.find("[name=" + nombre + "]").val());
            });
            return datos;
        }

        function pedir(conArchivo) {
            var datos = datosFormulario();
            if (conArchivo && $archivo[0].files.length) {
                datos.append("archivo", $archivo[0].files[0]);
            } else if (analisis) {
                datos.append("analisis", JSON.stringify(analisis));
            } else {
                estado("vacio");
                return;
            }
            if (peticion) { peticion.abort(); }
            estado("calculando");
            peticion = $.ajax({ url: urlEstimar, method: "POST", data: datos, processData: false, contentType: false })
                .done(function (respuesta) {
                    analisis = respuesta.analisis;
                    mostrar(respuesta);
                })
                .fail(function (xhr) {
                    if (xhr.statusText === "abort") { return; }
                    var mensaje = (xhr.responseJSON && xhr.responseJSON.mensaje) || "No se pudo calcular la estimación. Intente de nuevo.";
                    if (conArchivo) { analisis = null; }
                    texto("error", mensaje);
                    estado("error");
                });
        }

        $archivo.on("change", function () {
            analisis = null;
            var archivo = this.files[0];
            if (!archivo) { estado("vacio"); return; }
            var extension = archivo.name.split(".").pop().toLowerCase();
            if (EXTENSIONES.indexOf(extension) === -1) {
                this.value = "";
                $(this).closest(".zona-archivos").find(".archivos-elegidos").text("Ningún archivo seleccionado");
                window.Toast.mostrar("warning", "Formato no permitido. Use STL, OBJ o 3MF.");
                estado("vacio");
                return;
            }
            if (archivo.size > MAXIMO_BYTES) {
                this.value = "";
                $(this).closest(".zona-archivos").find(".archivos-elegidos").text("Ningún archivo seleccionado");
                window.Toast.mostrar("warning", "El archivo supera 50 MB.");
                estado("vacio");
                return;
            }
            pedir(true);
        });

        $formulario.find("select, input[name=cantidad]").on("change input", function () {
            if (!analisis) { return; }
            clearTimeout(temporizador);
            temporizador = setTimeout(function () { pedir(false); }, 300);
        });

        $formulario.on("submit", function () {
            $(this).find("button[type=submit]").prop("disabled", true).find(".texto-boton").text("Enviando…");
        });

        if ($archivo[0].files.length) { pedir(true); }
    });
})(jQuery);
