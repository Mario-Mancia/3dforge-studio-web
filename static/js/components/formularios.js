(function ($) {
    "use strict";

    var ESPERA = 300;

    function grupo($campo) {
        var $g = $campo.closest("[data-campo]");
        return $g.length ? $g : $campo.parent();
    }

    function marcar($campo, errores) {
        var $g = grupo($campo);
        var $feedback = $g.find(".invalid-feedback").first();
        if (!$feedback.length) {
            $feedback = $('<div class="invalid-feedback"></div>').appendTo($g);
        }
        if (errores.length) {
            $campo.addClass("is-invalid").removeClass("is-valid");
            $feedback.addClass("d-block").text(errores.join(" "));
        } else {
            $campo.removeClass("is-invalid");
            if ($campo.val()) { $campo.addClass("is-valid"); }
            $feedback.removeClass("d-block").text("");
        }
    }

    function datosDelFormulario($form, nombreCampo) {
        var contrasenas = $form.find("input[type=password]").map(function () { return this.name; }).get();
        var datos = $form.serializeArray().filter(function (c) {
            return c.name !== "csrfmiddlewaretoken" && contrasenas.indexOf(c.name) === -1;
        });
        datos.push({ name: "campo", value: nombreCampo });
        var pk = $form.attr("data-validar-pk");
        if (pk) { datos.push({ name: "pk", value: pk }); }
        return datos;
    }

    function validar($campo) {
        var $form = $campo.closest("form[data-validar]");
        var nombre = $campo.attr("name");
        var tipo = ($campo.attr("type") || "").toLowerCase();
        if (!$form.length || !nombre || $campo.prop("disabled")) { return; }
        if (["password", "file", "hidden", "submit", "button"].indexOf(tipo) !== -1 || nombre === "csrfmiddlewaretoken") { return; }
        $.ajax({
            url: $form.attr("data-validar-url"),
            method: "POST",
            dataType: "json",
            data: $.param(datosDelFormulario($form, nombre)),
            headers: { "X-CSRFToken": $form.find("[name=csrfmiddlewaretoken]").val() }
        }).done(function (respuesta) {
            marcar($campo, respuesta.errores || []);
        });
    }

    $(document).on("blur change", "form[data-validar] :input", function () {
        var $campo = $(this);
        clearTimeout($campo.data("temporizador"));
        $campo.data("temporizador", setTimeout(function () { validar($campo); }, ESPERA));
    });

    $(document).on("submit", "form", function (evento) {
        var $form = $(this);
        var mensaje = $form.attr("data-confirmar");
        if (mensaje && !window.confirm(mensaje)) {
            evento.preventDefault();
            return;
        }
        if ($form.find(".is-invalid").length) {
            evento.preventDefault();
            window.Toast.mostrar("warning", "Corrija los campos marcados antes de continuar.");
            $form.find(".is-invalid").first().trigger("focus");
            return;
        }
        if (!evento.isDefaultPrevented()) {
            $form.find("button[type=submit]").prop("disabled", true);
        }
    });

    $(window).on("pageshow", function () {
        $("button[type=submit]").prop("disabled", false);
    });
})(jQuery);
