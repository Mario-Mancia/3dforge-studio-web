(function () {
  "use strict";

  var TIPOS = ["image/jpeg", "image/png", "image/webp"];

  function mostrarError(contenedor, mensaje) {
    var caja = contenedor.querySelector("[data-foto-error]");
    if (!caja) { return; }
    caja.textContent = mensaje || "";
    caja.hidden = !mensaje;
  }

  function mostrarVista(contenedor, url) {
    var imagen = contenedor.querySelector("[data-foto-vista]");
    if (!imagen) {
      var inicial = contenedor.querySelector("[data-foto-inicial]");
      imagen = document.createElement("img");
      imagen.alt = "Vista previa";
      imagen.className = (inicial && inicial.getAttribute("data-foto-clase")) || "avatar-grande-img";
      imagen.setAttribute("data-foto-vista", "");
      if (inicial) { inicial.replaceWith(imagen); }
    }
    imagen.src = url;
  }

  document.querySelectorAll("[data-foto-entrada]").forEach(function (entrada) {
    var contenedor = entrada.closest("[data-foto-contenedor]") || entrada.parentElement;
    var formulario = entrada.closest("form");
    var guardar = formulario ? formulario.querySelector("[data-foto-guardar]") : null;
    var maximo = parseInt(entrada.getAttribute("data-max-bytes"), 10) || 0;

    entrada.addEventListener("change", function () {
      var archivo = entrada.files && entrada.files[0];
      mostrarError(contenedor, "");
      if (guardar) { guardar.hidden = true; }
      if (!archivo) { return; }
      if (TIPOS.indexOf(archivo.type) === -1) {
        entrada.value = "";
        mostrarError(contenedor, "Formato no permitido. Use JPG, PNG o WEBP.");
        return;
      }
      if (maximo && archivo.size > maximo) {
        entrada.value = "";
        mostrarError(contenedor, "La imagen supera el tamaño máximo permitido.");
        return;
      }
      mostrarVista(contenedor, URL.createObjectURL(archivo));
      if (guardar) { guardar.hidden = false; }
    });
  });
})();
