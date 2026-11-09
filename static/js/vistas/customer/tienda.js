$(function () {
    $("input[type=number][name=cantidad]").on("change", function () {
        var minimo = Number($(this).attr("min")) || 1;
        var maximo = Number($(this).attr("max")) || 99;
        var valor = parseInt($(this).val(), 10);
        if (isNaN(valor) || valor < minimo) { valor = minimo; }
        if (valor > maximo) { valor = maximo; }
        $(this).val(valor);
    });
});
