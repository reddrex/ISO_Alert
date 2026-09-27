import re
from dataclasses import replace

import pytest

from iso_alert import estado, informe, web


@pytest.fixture(scope="module")
def paginas(config, indice, tmp_path_factory):
    docs = tmp_path_factory.mktemp("docs")
    web.generar(estado.construir(config, indice, None), informe.construir(config, indice, None), config, docs)
    return {p.stem: p.read_text(encoding="utf-8") for p in docs.glob("*.md")}


def test_paginas_generadas(paginas):
    assert set(paginas) == {"index", "estado", "validacion"}
    for texto in paginas.values():
        assert texto.startswith("---\n")


def test_tabla_de_estado(paginas):
    md = paginas["estado"]
    tabla = md[md.index('<table id="tabla-normas">'):md.index("</table>")]
    assert tabla.count("<tr data-estado=") == 99
    # Una línea en blanco cortaría el bloque HTML y Markdown lo rompería.
    assert "\n\n" not in tabla
    fila = re.search(r'<tr data-estado="en_revision"[^>]*data-texto="iso 22301 [^"]*"', tabla)
    assert fila and 'data-superada="1"' in fila.group(0)
    assert "ISO/CD 22301</a>, fase de comité (30.60)" in tabla


def test_filtros(paginas, config):
    md = paginas["estado"]
    filtros = md[md.index('<div class="filtros"'):md.index("</div>")]
    assert "\n\n" not in filtros
    assert filtros.count("<option") == 1 + 5 + 1 + len(config.categorias) + 1 + len(config.familias) + 1


def test_inicio(paginas):
    md = paginas["index"]
    assert "## Ediciones del temario que ya no son las vigentes" in md
    assert "| ISO 22301 · " in md
    assert "2015 (año de la UNE)" in md  # ISO 37120
    assert 'href="estado/?estado=en_revision"' in md


def test_escapado(config, indice, tmp_path):
    normas = [replace(n, contexto="<b>x</b>") if n.codigo == "ISO 22301" else n for n in config.normas]
    config = replace(config, normas=normas)
    web.generar(estado.construir(config, indice, None), informe.construir(config, indice, None), config, tmp_path)
    md = (tmp_path / "estado.md").read_text(encoding="utf-8")
    assert "&lt;b&gt;x&lt;/b&gt;" in md and "<b>x</b>" not in md
