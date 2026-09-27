"""Casos reales del extracto del dataset ISO (septiembre de 2026).

Si se regenera el fixture, algunos de estos valores pueden cambiar porque ISO
publica ediciones nuevas: hay que revisarlos a mano, no ajustarlos a ciegas.
"""

import pytest

from iso_alert.modelo import Estado, Subestado
from iso_alert.resolver import resolver

from .conftest import norma


@pytest.fixture(scope="module")
def res(config, indice):
    por_codigo = {n.codigo: n for n in config.normas}
    return lambda codigo: resolver(por_codigo[codigo], indice)


def refs(entregables):
    return [e.referencia for e in entregables]


def test_vigente_simple(res):
    r = res("ISO/IEC 27001")
    assert r.estado == Estado.VIGENTE
    assert r.relevantes[0].vigente.referencia == "ISO/IEC 27001:2022"
    assert refs(r.relevantes[0].suplementos) == ["ISO/IEC 27001:2022/Amd 1:2024"]


def test_replacedby_con_proyecto_no_es_sustituida(res):
    # 22301:2019 tiene replacedBy=[ISO/CD 22301]: está en revisión, no sustituida.
    r = res("ISO 22301")
    assert r.estado == Estado.EN_REVISION
    linea = r.relevantes[0]
    assert linea.vigente.referencia == "ISO 22301:2019"
    assert refs(linea.proyectos) == ["ISO/CD 22301"]
    assert linea.sustituida_por == []
    assert r.edicion_citada == {"anio": "2012", "resultado": "superada", "vigentes": ["2019"]}


def test_sustitucion_que_cruza_numeros(res):
    r = res("ISO/IEC 9126")
    assert r.estado == Estado.SUSTITUIDA
    assert "ISO/IEC 25010:2023" in refs(r.relevantes[-1].sustituida_por)


def test_historica_sustituida_por_parte_de_otra_serie(res):
    r = res("ISO 13407")
    assert r.estado == Estado.SUSTITUIDA
    assert refs(r.relevantes[0].sustituida_por) == ["ISO 9241-210:2019"]


def test_cambio_de_tipo_y_prefijo(res, indice):
    r = res("ISO 15801")
    assert r.relevantes[0].vigente.referencia == "ISO 15801:2026"
    assert r.codigo_actual is None
    assert r.edicion_citada["resultado"] == "superada"  # el temario cita ISO/TR 15801:2004
    # Con el código antiguo se empareja igual y se sugiere el nuevo.
    assert resolver(norma("ISO/TR 15801"), indice).codigo_actual == "ISO 15801"
    assert resolver(norma("ISO/IEC 24766"), indice).codigo_actual == "ISO/IEC TR 24766"
    assert resolver(norma("ISO/IEC 15289"), indice).codigo_actual == "ISO/IEC/IEEE 15289"
    assert res("ISO/IEC/IEEE 15289").codigo_actual is None


def test_no_encontrada(indice):
    r = resolver(norma("ISO 30303"), indice)
    assert r.estado == Estado.NO_ENCONTRADA
    assert r.lineas == []


def test_no_publicada(res):
    r = res("ISO 26102")
    assert r.estado == Estado.NO_PUBLICADA
    assert "ISO/DTR 26102 (cancelado, 30.98)" in r.notas[0]


def test_subestados(res):
    assert res("ISO 21500").subestado == Subestado.REVISION_PERIODICA
    r = res("ISO/IEC 24708")
    assert (r.estado, r.subestado) == (Estado.VIGENTE, Subestado.ANULACION_PROPUESTA)


def test_serie_con_una_parte_vigente(res):
    r = res("ISO/IEC 14598")
    assert r.estado == Estado.VIGENTE
    assert r.recuento[Estado.VIGENTE] == 1
    assert r.recuento[Estado.SUSTITUIDA] == 5


def test_serie_limitada_a_partes_citadas(res):
    r = res("ISO 9241")
    assert [l.parte for l in r.relevantes] == ["210"]
    assert len(r.lineas) > 50


def test_rango_de_partes_citadas(res):
    r = res("ISO 8000")
    partes = {l.parte for l in r.relevantes}
    assert {"100", "150"} <= partes
    assert "200" not in partes


def test_parte_citada_que_es_un_grupo(indice):
    r = resolver(norma("ISO/IEC/IEEE 8802", "serie", partes_citadas=["1", "3"]), indice)
    assert any(n.startswith("Además de la parte 1 hay partes vigentes 1AB") for n in r.notas)


def test_partes_alfanumericas_citadas(res):
    r = res("ISO/IEC/IEEE 8802")
    assert [l.parte for l in r.relevantes] == ["1Q", "1X", "3"]
    assert r.estado == Estado.VIGENTE


def test_edicion_citada_que_no_existe_en_iso(res):
    # El temario cita 37120:2015, que es la UNE; la ISO es 2014/2018.
    assert res("ISO 37120").edicion_citada["resultado"] == "no_existe"


def test_serie_mixta_no_sugiere_cambio_de_codigo(res):
    assert res("ISO 31700").codigo_actual is None


def test_todas_se_resuelven(config, indice):
    from iso_alert.resolver import resolver_todo

    estados = [r.estado for r in resolver_todo(config, indice)]
    assert estados.count(Estado.NO_ENCONTRADA) == 0
