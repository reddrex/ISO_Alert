import re
from dataclasses import replace

import pytest

from iso_alert import estado, informe, web


@pytest.fixture(scope="module")
def paginas(config, indice, tmp_path_factory):
    docs = tmp_path_factory.mktemp("docs")
    web.generar(estado.construir(config, indice, None), informe.construir(config, indice, None), config, docs)
    paginas = {p.stem: p.read_text(encoding="utf-8") for p in docs.glob("*.md")}
    for clave, carpeta in (("fichas", web.FICHAS), ("familias", web.FAMILIAS), ("temario", web.TEMARIO)):
        paginas[clave] = {p.stem: p.read_text(encoding="utf-8") for p in (docs / carpeta).glob("*.md")}
    return paginas


CARPETAS = ("fichas", "familias", "temario")


def test_paginas_generadas(paginas):
    assert set(paginas) == {"index", "estado", "comparativas", "historial", "validacion", *CARPETAS}
    assert len(paginas["familias"]) == 21
    assert len(paginas["temario"]) == 39  # índice + 38 temas
    for nombre, texto in paginas.items():
        if nombre not in CARPETAS:
            assert texto.startswith("---\n")
    for carpeta in CARPETAS:
        for texto in paginas[carpeta].values():
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
    anios = re.findall(r'<option value="(\d{4})">', filtros)
    assert anios and anios == sorted(anios, reverse=True)
    assert filtros.count("<option") == (
        1 + 5 + 1 + len(config.categorias) + 1 + len(config.temario) + 1 + len(config.familias) + 1
        + 1 + len(anios) + 3
    )


def test_aprobacion(paginas):
    tabla = paginas["estado"]
    # La fila lleva la fecha de aprobación de la edición vigente, para filtrar y ordenar por ella.
    fila = re.search(r'<tr [^>]*data-aprobacion="(\d{4}-\d{2}-\d{2})"[^>]*data-texto="iso/iec 27001 ', tabla)
    assert fila and fila.group(1).startswith("2022")
    assert re.search(r'<td class="vigente" data-sort="\d{4}-\d{2}-\d{2}">', tabla)
    # Las sustituidas no tienen edición vigente.
    assert re.search(r'<tr data-estado="sustituida"[^>]*data-aprobacion=""', tabla)


def test_inicio(paginas):
    md = paginas["index"]
    assert "# Estándares por ámbito" in md and 'aria-current="page">Por ámbito' in md
    assert "Ediciones del temario que ya no son las vigentes" not in md
    assert "Seguimiento de cambios" not in md and "md-button" not in md
    # La situación actual está ahora en Cambios.
    assert 'href="estado/?estado=en_revision"' in paginas["historial"]
    assert "## Situación actual" in paginas["historial"]


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
    assert "| [ISO/IEC 27002](../normas/iso-iec-27002.md) <br>" in fam and "¿Qué controles puedo aplicar?" in fam
    # Solo se destacan los estados que requieren atención.
    assert "estado--vigente" not in fam and "estado--sustituida" in fam
    assert fam.split("\n---\n", 1)[1].lstrip().startswith("[Por ámbito](../index.md) › [Seguridad y privacidad]")
    ciclo = paginas["familias"]["ciclo-vida"]
    orden = ["12207", "14764", "15288", "15289"]
    posiciones = [ciclo.index(f"<strong>{n}</strong>") for n in orden]
    assert posiciones == sorted(posiciones)


def test_asociacion(paginas):
    tema47 = paginas["temario"]["47"]
    cadena = tema47[tema47.index('<ol class="cadena">'):tema47.index("</ol>")]
    assert "\n\n" not in cadena
    codigos = re.findall(r'<a href="\.\./normas/[^"]+">([^<]+)</a>', cadena)
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
    assert '!!! example "Ejemplo"\n    Una agencia estatal implanta un SGSI' in f
    assert "- [Tema 47 · Seguridad de sistemas (1)](../temario/47.md)" in f
    assert "- **Desarrollada por:** [ISO/IEC 27002](iso-iec-27002.md) · controles" in f
    assert "```mermaid\ngraph LR" in f
    assert '??? note "Historia de ediciones"' in f and "ISO/IEC 27001:2013</a> · Anulada" in f
    assert '<p class="ficha__pregunta"><span>Pregunta que responde</span>¿Cómo gestiono la seguridad?</p>' in f
    # Enlaces HTML entre fichas: relativos a la carpeta normas/ (Zensical añade el «../»).
    assert '<a href="iso-iec-27000/"' in f and 'href="../iso-iec-27000/"' not in f
    assert '<a href="iso-iec-27000/" rel="prev">' in f and '<a href="iso-iec-27002/" rel="next">' in f
    assert "[Por ámbito](../index.md) › [Seguridad y privacidad](../index.md#area-seguridad) › [ISO/IEC 27000]" in f
    # Cada elemento de lista en su propia línea (trim_blocks no debe pegarlos).
    assert ")- **" not in f
    # Series: partes citadas con la descripción del temario.
    serie = fichas["iso-iec-20000"]
    assert "**Parte 1**" in serie and "Requisitos de un sistema de gestión de servicios de TI." in serie
    assert '??? note "Otras' in serie


def test_temario(paginas, config):
    indice = paginas["temario"]["index"]
    # Un solo enlace por tema, y las normas con su código completo.
    assert len(re.findall(r"^\| \[\d+ · [^]]+\]\(\d+\.md\) \|", indice, re.M)) == len(config.temario) == 38
    assert "[ISO/IEC 27001](../normas/iso-iec-27001.md)" in indice and "+ familia [ISO/IEC 27000]" in indice
    assert "[ASTIC](https://www.astic.es/)" in indice
    tema47 = paginas["temario"]["47"]
    lista = tema47[tema47.index("## Normas del tema"):tema47.index("```")]
    for codigo in ("iso-iec-27001", "iso-iec-27002", "iso-iec-27005", "iso-31000"):
        assert lista.count(f'href="../normas/{codigo}/"') == 1  # cada norma, una sola vez
    assert "¿Cómo gestiono los riesgos?" in tema47  # pregunta de cada norma en la lista
    assert "El color indica el área:" in lista
    assert "ISO/IEC 27017" not in tema47.split("```")[1]  # el diagrama solo usa las citadas una a una
    assert '<a href="46/" rel="prev">' in tema47 and '<a href="48/" rel="next">' in tema47
    assert "estado--vigente" not in tema47 and "estado--en_revision" in tema47  # ISO 31000


def test_comparativas(paginas):
    md = paginas["comparativas"]
    assert "| [ISO/IEC 20000](normas/iso-iec-20000.md)-1 | SGS | Servicios de TI | 2018 |" in md
    assert "Activos de TI y licencias | 2017 |" in md
    # El contenido de los bloques plegables va sangrado.
    bloque = md[md.index('??? note "Norma de requisitos'):]
    assert bloque.split("\n")[1].startswith("    [ISO 9001]")


def test_feeds_legibles_en_el_navegador(config, indice, tmp_path):
    web.generar(estado.construir(config, indice, None), informe.construir(config, indice, None), config, tmp_path)
    general = (tmp_path / "feed.xml").read_text(encoding="utf-8")
    assert '<?xml-stylesheet type="text/xsl" href="feed.xsl"?>' in general
    assert "Observatorio de estándares TIC · avisos" in general
    norma = (tmp_path / web.FEEDS / "iso-iec-27001.xml").read_text(encoding="utf-8")
    assert '<?xml-stylesheet type="text/xsl" href="../feed.xsl"?>' in norma
