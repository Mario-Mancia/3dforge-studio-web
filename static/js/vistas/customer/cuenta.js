$(function () {
    function alternar() {
        var esEmpresa = $("#id_tipo_cliente").val() === "EMPRESA";
        $("[data-campo=nombre_empresa]").toggleClass("d-none", !esEmpresa);
    }
    $("#id_tipo_cliente").on("change", alternar);
    alternar();
});
