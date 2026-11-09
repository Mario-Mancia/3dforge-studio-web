$(function () {
    $(".toggle-password").on("click", function () {
        var $campo = $($(this).data("objetivo"));
        var visible = $campo.attr("type") === "text";
        $campo.attr("type", visible ? "password" : "text");
        $(this).find(".material-symbols-rounded").text(visible ? "visibility" : "visibility_off");
        $(this).attr("aria-label", visible ? "Mostrar contraseña" : "Ocultar contraseña");
    });

    $("#form-registro").on("submit", function (evento) {
        var errores = [];
        var clave = $("#reg-clave1").val();
        if (clave.length < 10) { errores.push("La contraseña debe tener al menos 10 caracteres."); }
        if (clave !== $("#reg-clave2").val()) { errores.push("Las contraseñas no coinciden."); }
        if (!$("#reg-terminos").is(":checked")) { errores.push("Debe aceptar los términos y condiciones."); }
        if (errores.length) {
            evento.preventDefault();
            window.Toast.mostrar("warning", errores.join(" "));
        }
    });

    if (window.location.hash === "#registro") {
        bootstrap.Tab.getOrCreateInstance(document.querySelector("#tab-registro")).show();
    }
});
