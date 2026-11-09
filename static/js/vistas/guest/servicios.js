$(function () {
    $("#filtro-servicios").on("input", function () {
        var texto = $(this).val().toLowerCase().trim();
        $(".servicio-item").each(function () {
            $(this).toggleClass("d-none", texto !== "" && String($(this).data("nombre")).indexOf(texto) === -1);
        });
    });
});
