$(function () {
    $("input[type=date]").on("change", function () { this.form.requestSubmit(); });
});
