$(function () {
    $("select[name=rol], select[name=estado]").on("change", function () { this.form.requestSubmit(); });
});
