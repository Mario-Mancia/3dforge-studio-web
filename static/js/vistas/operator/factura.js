$(function () {
    $("#usar-saldo").on("click", function () {
        var saldo = $(this).closest("form").data("saldo");
        $(this).closest("form").find("[name=monto]").val(saldo).trigger("blur");
    });
});
