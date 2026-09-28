// Filtros, búsqueda, ordenación y agrupación de la tabla de estado.
// Sin dependencias salvo Tablesort. Los filtros se reflejan en la URL
// (?estado=en_revision&categoria=seguridad&anio=2022&orden=reciente) para poder compartir enlaces.

document$.subscribe(function () {
  var tabla = document.getElementById("tabla-normas");
  if (!tabla || tabla.dataset.listo) return;
  tabla.dataset.listo = "1";

  var filtros = document.getElementById("filtros");
  var cuerpo = tabla.tBodies[0];
  var filas = Array.prototype.slice.call(cuerpo.rows);
  filas.forEach(function (f, i) { f.dataset.orden = i; });

  var campos = {
    texto: document.getElementById("f-texto"),
    estado: document.getElementById("f-estado"),
    categoria: document.getElementById("f-categoria"),
    tema: document.getElementById("f-tema"),
    familia: document.getElementById("f-familia"),
    anio: document.getElementById("f-anio"),
    une: document.getElementById("f-une") || { value: "", addEventListener: function () {} },
    orden: document.getElementById("f-orden"),
    superada: document.getElementById("f-superada"),
    agrupar: document.getElementById("f-agrupar")
  };
  var contador = document.getElementById("f-contador");
  if (typeof Tablesort === "function") new Tablesort(tabla);

  // Estado inicial desde la URL.
  var params = new URLSearchParams(location.search);
  ["texto", "estado", "categoria", "tema", "familia", "une", "anio", "orden"].forEach(function (k) {
    if (params.has(k)) campos[k].value = params.get(k);
  });
  campos.superada.checked = params.get("superada") === "1";
  campos.agrupar.checked = params.get("agrupar") === "1";
  filtros.hidden = false;

  function normalizar(s) {
    return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  }

  // El detalle de cada norma está en un <details> dentro de la celda del nombre
  // (funciona sin JavaScript). Con JavaScript se abre en una fila a todo el ancho.
  var columnas = tabla.tHead.rows[0].cells.length;
  tabla.addEventListener("toggle", function (ev) {
    var d = ev.target;
    if (!d.parentElement || !d.parentElement.classList.contains("nombre")) return;
    var contenido = d._contenido || d.querySelector(":scope > dl");
    d._contenido = contenido;
    if (d.open) {
      var fila = document.createElement("tr");
      fila.className = "fila-detalle";
      var celda = document.createElement("td");
      celda.colSpan = columnas;
      celda.appendChild(contenido);
      fila.appendChild(celda);
      fila.hidden = d.closest("tr").hidden;
      d.closest("tr").after(fila);
      d._fila = fila;
    } else if (d._fila) {
      d.appendChild(contenido);
      d._fila.remove();
      d._fila = null;
    }
  }, true);

  function cerrarDetalles() {
    tabla.querySelectorAll("td.nombre > details[open]").forEach(function (d) {
      d.open = false;
      if (d._fila) { d.appendChild(d._contenido); d._fila.remove(); d._fila = null; }
    });
  }

  function aplicar() {
    cerrarDetalles();
    var texto = normalizar(campos.texto.value.trim());
    var visibles = 0;
    filas.forEach(function (f) {
      var ok =
        (!texto || normalizar(f.dataset.texto).indexOf(texto) !== -1) &&
        (!campos.estado.value || f.dataset.estado === campos.estado.value) &&
        (!campos.categoria.value || f.dataset.categoria === campos.categoria.value) &&
        (!campos.tema.value || (" " + f.dataset.temas + " ").indexOf(" " + campos.tema.value + " ") !== -1) &&
        (!campos.familia.value || f.dataset.familia === campos.familia.value) &&
        (!campos.une.value || f.dataset.une === campos.une.value) &&
        (!campos.anio.value || f.dataset.aprobacion.slice(0, 4) === campos.anio.value) &&
        (!campos.superada.checked || f.dataset.superada === "1");
      f.hidden = !ok;
      if (ok) visibles++;
    });
    ordenar();
    agrupar();
    contador.textContent = visibles === filas.length
      ? filas.length + " normas"
      : visibles + " de " + filas.length + " normas";
    guardarEnUrl();
  }

  // Orden por fecha de aprobación de la edición vigente; las que no tienen van al final.
  // "Por código" recupera el orden original, que es el de la página.
  function ordenar() {
    var modo = campos.orden.value;
    if (!modo && !ordenada) return;
    var ordenadas = filas.slice().sort(function (a, b) {
      var fa = a.dataset.aprobacion, fb = b.dataset.aprobacion;
      if (modo && fa !== fb) {
        if (!fa) return 1;
        if (!fb) return -1;
        return (fa < fb ? -1 : 1) * (modo === "reciente" ? -1 : 1);
      }
      return a.dataset.orden - b.dataset.orden;
    });
    ordenadas.forEach(function (f) { cuerpo.appendChild(f); });
    ordenada = !!modo;
  }
  var ordenada = false;

  function agrupar() {
    cuerpo.querySelectorAll("tr.grupo").forEach(function (g) { g.remove(); });
    if (!campos.agrupar.checked) return;
    // Dentro de cada familia se mantiene el orden que ya tenga la tabla.
    var pos = new Map(Array.prototype.map.call(cuerpo.rows, function (f, i) { return [f, i]; }));
    var ordenadas = filas.slice().sort(function (a, b) {
      return (a.dataset.familiaOrden - b.dataset.familiaOrden) || (pos.get(a) - pos.get(b));
    });
    ordenada = true;
    var actual = null;
    ordenadas.forEach(function (f) {
      if (!f.hidden && f.dataset.familia !== actual) {
        actual = f.dataset.familia;
        var g = document.createElement("tr");
        g.className = "grupo";
        var th = document.createElement("th");
        th.colSpan = columnas;
        th.scope = "colgroup";
        th.textContent = f.dataset.familiaNombre;
        g.appendChild(th);
        cuerpo.appendChild(g);
      }
      cuerpo.appendChild(f);
    });
  }

  function guardarEnUrl() {
    var p = new URLSearchParams();
    ["texto", "estado", "categoria", "tema", "familia", "une", "anio", "orden"].forEach(function (k) {
      if (campos[k].value) p.set(k, campos[k].value.trim());
    });
    if (campos.superada.checked) p.set("superada", "1");
    if (campos.agrupar.checked) p.set("agrupar", "1");
    var q = p.toString();
    history.replaceState(null, "", location.pathname + (q ? "?" + q : "") + location.hash);
  }

  // Ordenar por una columna deshace la agrupación y el orden por fecha.
  tabla.addEventListener("beforeSort", function () {
    cerrarDetalles();
    if (campos.orden.value) {
      campos.orden.value = "";
      ordenada = false;
      guardarEnUrl();
    }
    if (campos.agrupar.checked) {
      campos.agrupar.checked = false;
      cuerpo.querySelectorAll("tr.grupo").forEach(function (g) { g.remove(); });
      guardarEnUrl();
    }
  });

  campos.texto.addEventListener("input", aplicar);
  ["estado", "categoria", "tema", "familia", "une", "anio", "orden", "superada", "agrupar"].forEach(function (k) {
    campos[k].addEventListener("change", aplicar);
  });
  aplicar();
});
