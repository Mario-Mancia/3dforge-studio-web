$(function () {
    var MAXIMO_ARCHIVOS = 5;
    var MAXIMO_BYTES = 50 * 1024 * 1024;
    var EXTENSIONES = ["stl", "obj", "3mf", "step", "stp", "png", "jpg", "jpeg", "pdf"];

    $("input[type=file][name=archivos]").on("change", function () {
        var errores = [];
        var archivos = Array.prototype.slice.call(this.files);
        if (archivos.length > MAXIMO_ARCHIVOS) { errores.push("Máximo " + MAXIMO_ARCHIVOS + " archivos."); }
        archivos.forEach(function (archivo) {
            var extension = archivo.name.split(".").pop().toLowerCase();
            if (EXTENSIONES.indexOf(extension) === -1) { errores.push(archivo.name + ": formato no permitido."); }
            if (archivo.size > MAXIMO_BYTES) { errores.push(archivo.name + ": supera 50 MB."); }
        });
        if (errores.length) {
            this.value = "";
            window.Toast.mostrar("warning", errores.join(" "));
        }
    });
});
