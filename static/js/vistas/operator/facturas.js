$(function () {
    $("select[name=estado]").on("change", function () { this.form.requestSubmit(); });
});
