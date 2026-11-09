$(function () {
    $("input[type=number][name=cantidad]").on("change", function () {
        var valor = parseInt($(this).val(), 10);
        if (isNaN(valor) || valor < 0) { valor = 0; }
        if (valor > 99) { valor = 99; }
        $(this).val(valor);
    });
});
