$(function () {
    var temporizador;
    $("#q").on("input", function () {
        var formulario = this.form;
        clearTimeout(temporizador);
        temporizador = setTimeout(function () { formulario.requestSubmit(); }, 700);
    });
});
