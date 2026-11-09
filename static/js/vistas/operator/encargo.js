$(function () {
    $("form[action$='/accion/estado/']").on("submit", function (evento) {
        if ($(this).find("[name=estado]").val() === "CANCELADO" && !window.confirm("¿Cancelar el encargo? Si es una compra, se repondrá el stock.")) {
            evento.preventDefault();
        }
    });
});
