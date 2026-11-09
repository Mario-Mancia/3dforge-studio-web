(function () {
    "use strict";

    var CLAVE = "tema";

    function actual() {
        return document.documentElement.getAttribute("data-bs-theme") || "light";
    }

    function guardado() {
        try { return localStorage.getItem(CLAVE); } catch (error) { return null; }
    }

    function aplicar(tema, guardar) {
        document.documentElement.setAttribute("data-bs-theme", tema);
        if (guardar) {
            try { localStorage.setItem(CLAVE, tema); } catch (error) { /* almacenamiento no disponible */ }
        }
        var oscuro = tema === "dark";
        document.querySelectorAll(".icono-tema").forEach(function (icono) {
            icono.textContent = oscuro ? "light_mode" : "dark_mode";
        });
        document.querySelectorAll("[data-alternar-tema]").forEach(function (boton) {
            boton.setAttribute("aria-pressed", oscuro ? "true" : "false");
            boton.setAttribute("aria-label", oscuro ? "Cambiar a tema claro" : "Cambiar a tema oscuro");
            boton.setAttribute("title", oscuro ? "Tema claro" : "Tema oscuro");
        });
        document.dispatchEvent(new CustomEvent("tema:cambio", { detail: { tema: tema } }));
    }

    document.addEventListener("DOMContentLoaded", function () {
        aplicar(actual(), false);
        document.querySelectorAll("[data-alternar-tema]").forEach(function (boton) {
            boton.addEventListener("click", function () {
                aplicar(actual() === "dark" ? "light" : "dark", true);
            });
        });
        var sistema = window.matchMedia("(prefers-color-scheme: dark)");
        sistema.addEventListener("change", function (evento) {
            if (!guardado()) { aplicar(evento.matches ? "dark" : "light", false); }
        });
    });
})();
