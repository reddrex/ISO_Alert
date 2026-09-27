import re
from dataclasses import replace

import pytest

from iso_alert import estado, informe, web


@pytest.fixture(scope="module")
def paginas(config, indice, tmp_path_factory):
    docs = tmp_path_factory.mktemp("docs")
    web.generar(estado.construir(config, indice, None), informe.construir(config, indice, None), config, docs)
    paginas = {p.stem: p.read_text(encoding="utf-8") for p in docs.glob("*.md")}
    for carpeta in (web.FICHAS, web.FAMILIAS):
        paginas[carpeta if carpeta != web.FICHAS else "fichas"] = {
            p.stem: p.read_text(encoding="utf-8") for p in (docs / carpeta).glob("*.md")
        }
    return paginas


def test_paginas_generadas(paginas):
    assert set(paginas) == {"index", "estado", "temario", "comparativas", "validacion", "fichas", "familias"}
    assert len(paginas["familias"]) == 21
    for nombre, texto in paginas.items():
        if nombre not in ("fichas", "familias"):
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
    assert filtros.count("<option") == (
        1 + 5 + 1 + len(config.categorias) + 1 + len(config.temario) + 1 + len(config.familias) + 1
    )


def test_inicio(paginas):
    md = paginas["index"]
    assert "### Ediciones del temario que ya no son las vigentes" in md
    assert "| [ISO 22301](normas/iso-22301.md) · " in md
    assert "2015 (año de la UNE)" in md  # ISO 37120
    assert 'href="estado/?estado=en_revision"' in md


def test_escapado(config, indice, tmp_path):
    normas = [replace(n, contexto="<b>x</b>") if n.codigo == "ISO 22301" else n for n in config.normas]
    config = replace(config, normas=normas)
    web.generar(estado.construir(config, indice, None), informe.construir(config, indice, None), config, tmp_path)
    md = (tmp_path / "estado.md").read_text(encoding="utf-8")
    assert "&lt;b&gt;x&lt;/b&gt;" in md and "<b>x</b>" not in md


def test_mapa(paginas, config):
    md = paginas["index"]
    mapa = md[md.index('<div class="mapa">'):md.index("</div>", md.index('<div class="mapa">'))]
    assert "\n\n" not in mapa  # una línea en blanco rompería el bloque HTML
    assert mapa.count('<section class="mapa__area') == len(config.areas) == 9
    # Todas las familias, enlazadas a su página, y todas las normas, en familia o sueltas.
    assert mapa.count('class="mapa__familia"') == len(config.familias)
    assert 'href="familias/iso-27000/"' in mapa
    sueltas = mapa.count('<a href="normas/')
    en_familia = sum(1 for n in config.normas if n.familia)
    assert sueltas + en_familia == 99
    # 25012 es de la categoría de datos pero se estudia en SQuaRE (área Software).
    software = mapa[mapa.index("area--software"):mapa.index("area--datos")]
    assert "25012" in software


def test_familias(paginas):
    fam = paginas["familias"]["iso-27000"]
    assert fam.startswith('---\ntitle: "Familia ISO/IEC 27000')
    cadena = fam[fam.index('<p class="cadena-linea">'):]
    orden = ["27000", "27001", "27002", "27005", "27017", "27018", "27701", "13335"]
    posiciones = [cadena.index(f"<strong>{n}</strong>") for n in orden]
    assert posiciones == sorted(posiciones)  # por número, con la antecesora al final
    assert "<strong>27001</strong> = sistema (SGSI)" in cadena
    assert "| [ISO/IEC 27002](../normas/iso-iec-27002.md)<br>" in fam and "¿Qué controles puedo aplicar?" in fam
    ciclo = paginas["familias"]["ciclo-vida"]
    orden = ["12207", "14764", "15288", "15289"]
    posiciones = [ciclo.index(f"<strong>{n}</strong>") for n in orden]
    assert posiciones == sorted(posiciones)


def test_asociacion(paginas):
    md = paginas["temario"]
    tema47 = md[md.index("{ #tema-47 }"):md.index("{ #tema-48 }")]
    cadena = tema47[tema47.index('<ol class="cadena">'):tema47.index("</ol>")]
    assert "\n\n" not in cadena
    codigos = re.findall(r'<a href="normas/[^"]+">([^<]+)</a>', cadena)
    assert codigos == ["ISO 31000", "ISO/IEC 27005", "ISO/IEC 27001", "ISO/IEC 27002"]
    assert "riesgo en general" in cadena


def test_enlace_desde_la_tabla(paginas):
    assert '<a href="normas/iso-iec-27001/">Ficha completa</a>' in paginas["estado"]
    assert 'data-temas="38 43 47 48 71 82 105 125"' in paginas["estado"]


def test_fichas(paginas):
    fichas = paginas["fichas"]
    assert len(fichas) == 99
    f = fichas["iso-iec-27001"]
    assert f.startswith('---\ntitle: "ISO/IEC 27001 · SGSI: requisitos"')
    assert "## Claves para el examen" in f and "93 controles" in f
    assert "- [Tema 47](../temario.md#tema-47). Seguridad de sistemas (1)." in f
    assert "- **Desarrollada por:** [ISO/IEC 27002](iso-iec-27002.md)" in f
    assert "```mermaid\ngraph LR" in f
    assert "ISO/IEC 27001:2013</a> · Anulada" in f
    # Cada elemento de lista en su propia línea (trim_blocks no debe pegarlos).
    assert ")- **" not in f
    # Series: partes citadas con la descripción del temario.
    serie = fichas["iso-iec-20000"]
    assert "**Parte 1**" in serie and "Requisitos de un sistema de gestión de servicios de TI." in serie
    assert '??? note "Otras' in serie


def test_temario(paginas, config):
    md = paginas["temario"]
    assert md.count("{ #tema-") == len(config.temario) == 38
    tema47 = md[md.index("{ #tema-47 }"):md.index("{ #tema-48 }")]
    for codigo in ("iso-iec-27001", "iso-iec-27002", "iso-iec-27005", "iso-31000"):
        assert f"(normas/{codigo}.md)" in tema47
    assert "ISO/IEC 27017" not in tema47.split("```")[1]  # el diagrama solo usa las citadas una a una


def test_comparativas(paginas):
    md = paginas["comparativas"]
    assert "| [ISO/IEC 20000](normas/iso-iec-20000.md)-1 | SGS | Servicios de TI | 2018 |" in md
    assert "Activos de TI y licencias | 2017 |" in md
    # El contenido de los bloques plegables va sangrado.
    bloque = md[md.index('??? note "Norma de requisitos'):]
    assert bloque.split("\n")[1].startswith("    [ISO 9001]")
