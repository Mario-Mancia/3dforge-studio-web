$(function () {
    $("select[name=rango]").on("change", function () { this.form.requestSubmit(); });
});
