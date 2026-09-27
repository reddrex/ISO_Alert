import json
from dataclasses import replace

from iso_alert import informe

from .conftest import norma


def test_informe(config, indice):
    datos = informe.construir(config, indice, None)
    json.dumps(datos)  # serializable
    assert datos["resumen"]["total"] == 99
    por = {n["codigo"]: n for n in datos["normas"]}
    assert por["ISO 22301"]["vigentes"][0]["url"] == "https://www.iso.org/standard/75106.html"
    assert por["ISO/IEC 39794"]["encontrada"]
    assert any("adopción UNE" in s for s in por["ISO 37120"]["sugerencias"])

    md = informe.a_markdown(datos)
    assert md.startswith("---\ntitle: Informe de validación")
    for texto in ("## Requieren atención", "### ISO 37120", "| ISO 22301 | 2012 | 2019 | **Superada** |"):
        assert texto in md


def test_informe_con_incidencias(config, indice):
    extra = [norma("ISO 30303", familia="f"), norma("ISO/TR 15801")]
    datos = informe.construir(replace(config, normas=config.normas + extra), indice, None)
    por = {n["codigo"]: n for n in datos["normas"]}
    assert por["ISO 30303"]["encontrada"] is False
    assert any("solo UNE" in s for s in por["ISO 30303"]["sugerencias"])
    assert por["ISO/TR 15801"]["codigo_actual"] == "ISO 15801"
    assert "### ISO 30303" in informe.a_markdown(datos)
