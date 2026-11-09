(function ($) {
    "use strict";

    $(function () {
        $('[data-bs-toggle="tooltip"]').each(function () { new bootstrap.Tooltip(this); });

        $(".zona-archivos input[type=file]").on("change", function () {
            var nombres = Array.prototype.map.call(this.files, function (archivo) { return archivo.name; });
            $(this).closest(".zona-archivos").find(".archivos-elegidos").text(
                nombres.length ? nombres.join(", ") : "Ningún archivo seleccionado"
            );
        });
    });
})(jQuery);
