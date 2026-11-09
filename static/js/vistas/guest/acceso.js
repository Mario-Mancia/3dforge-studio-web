$(function () {
    $(".toggle-password").on("click", function () {
        var $campo = $($(this).data("objetivo"));
        var visible = $campo.attr("type") === "text";
        $campo.attr("type", visible ? "password" : "text");
        $(this).text(visible ? "Ver" : "Ocultar");
    });

    $("#form-registro").on("submit", function (evento) {
        if ($("#reg-clave1").val() !== $("#reg-clave2").val()) {
            evento.preventDefault();
            window.Toast.mostrar("warning", "Las contraseñas no coinciden.");
        }
    });
});
