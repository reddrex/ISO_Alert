import json

import pytest

from iso_alert import estado


@pytest.fixture(scope="module")
def datos(config, indice):
    return estado.construir(config, indice, None)


def test_esquema(datos):
    json.dumps(datos)
    assert datos["version_esquema"] == estado.VERSION_ESQUEMA
    assert len(datos["normas"]) == 99


def test_referencias_resueltas(datos):
    """Todo id que usa la web existe en la vista plana de entregables."""
    ids = set(datos["entregables"])
    for codigo, n in datos["normas"].items():
        usados = n["vigentes"] + n["en_desarrollo"] + n["sustituida_por"] + n["suplementos"]
        for p in n["partes"] or []:
            usados += [p["vigente"], p["ultima"]] + p["proyectos"] + p["suplementos"] + p["sustituida_por"]
        faltan = {str(i) for i in usados if i is not None} - ids
        assert not faltan, (codigo, faltan)


def test_norma(datos):
    n = datos["normas"]["ISO 22301"]
    assert n["estado"] == "en_revision"
    assert n["en_desarrollo"] == [93606]
    assert n["titulo_en"] == "Security and resilience — Business continuity management systems — Requirements"
    assert datos["entregables"]["93606"]["normas"] == ["ISO 22301"]


def test_serie(datos):
    n = datos["normas"]["ISO/IEC/IEEE 8802"]
    assert n["titulo_en"].endswith("local and metropolitan area networks")  # sin «— Part N: …»
    citadas = [p["parte"] for p in n["partes"] if p["citada"]]
    assert citadas == ["1Q", "1X", "3"]
    assert len(n["partes"]) > 30


def test_sustituta_de_otro_numero(datos):
    n = datos["normas"]["ISO/IEC 9126"]
    refs = [datos["entregables"][str(i)]["referencia"] for i in n["sustituida_por"]]
    assert "ISO/IEC 25010:2023" in refs
