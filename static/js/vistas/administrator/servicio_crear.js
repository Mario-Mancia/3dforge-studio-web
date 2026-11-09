$(function () {
    $("#id_sku, #id_codigo_empleado").on("input", function () {
        this.value = this.value.toUpperCase();
    });
});
