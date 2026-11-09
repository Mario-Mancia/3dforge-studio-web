$(function () {
    function numero(texto) {
        var valor = parseFloat(String(texto).replace(",", "."));
        return isNaN(valor) ? 0 : valor;
    }
    function recalcular($fila) {
        var cantidad = numero($fila.find("[name$='-cantidad']").val());
        var precio = numero($fila.find("[name$='-precio_unitario']").val());
        var descuento = numero($fila.find("[name$='-descuento']").val());
        $fila.find(".subtotal-previo").text("$" + (cantidad * precio - descuento).toFixed(2));
    }
    $("tr[data-linea]").each(function () { recalcular($(this)); });
    $("tr[data-linea] input").on("input", function () { recalcular($(this).closest("tr")); });
});
