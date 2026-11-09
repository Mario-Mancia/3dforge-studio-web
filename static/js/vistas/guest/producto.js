$(function () {
    $("#copiar-sku").on("click", function () {
        var sku = $(this).data("sku");
        navigator.clipboard.writeText(String(sku)).then(function () {
            window.Toast.mostrar("success", "SKU copiado: " + sku);
        }, function () {
            window.Toast.mostrar("error", "No se pudo copiar el SKU.");
        });
    });
});
