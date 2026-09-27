import pytest

from iso_alert.referencias import ReferenciaInvalida, parse, parte_citada, partes_en

# (referencia, organismos, borrador, tipo, numero, parte, anio, suplemento)
CASOS = [
    ("ISO/IEC 27001:2022", "ISO/IEC", None, "IS", "27001", None, "2022", None),
    ("ISO/CD 22301", "ISO", "CD", "IS", "22301", None, None, None),
    ("ISO/IEC CD 29115.2", "ISO/IEC", "CD", "IS", "29115", None, None, None),
    ("ISO/DTR 26102", "ISO", "DTR", "TR", "26102", None, None, None),
    ("ISO/IEC/IEEE 8802-1Q:2020", "ISO/IEC/IEEE", None, "IS", "8802", "1Q", "2020", None),
    ("ISO/IEC 29110-5-1-4", "ISO/IEC", None, "IS", "29110", "5-1-4", None, None),
    ("ISO/IEC TR 13335-3:1998", "ISO/IEC", None, "TR", "13335", "3", "1998", None),
    ("ISO 30301:2019/Amd 1:2024", "ISO", None, "IS", "30301", None, "2019", "Amd 1:2024"),
    ("ISO 30300:2011/CD Cor 1", "ISO", None, "IS", "30300", None, "2011", "CD Cor 1"),
    ("ISO 269:1985/DAmd 1", "ISO", None, "IS", "269", None, "1985", "DAmd 1"),
    ("ISO/IEC 8802-5:1995/PDAM 3", "ISO/IEC", None, "IS", "8802", "5", "1995", "PDAM 3"),
    ("ISO/IEC AWI TS 20000-19", "ISO/IEC", "AWI", "TS", "20000", "19", None, None),
    ("ISO/IEC FCD 14465", "ISO/IEC", "FCD", "IS", "14465", None, None, None),
    ("ISO/DIS 19005-4.2", "ISO", "DIS", "IS", "19005", "4", None, None),
    ("ISO/R 102:1959", "ISO", None, "R", "102", None, "1959", None),
    ("ISO Guide 2:1976", "ISO", None, "Guide", "2", None, "1976", None),
    ("ISO/IEC DGuide 81", "ISO/IEC", "DGuide", "Guide", "81", None, None, None),
    ("NP IWA 7", "", "NP", "IWA", "7", None, None, None),
    ("ISO/TR 13028", "ISO", None, "TR", "13028", None, None, None),
]


@pytest.mark.parametrize("ref,org,borrador,tipo,numero,parte,anio,supl", CASOS)
def test_parse(ref, org, borrador, tipo, numero, parte, anio, supl):
    r = parse(ref)
    assert "/".join(r.organismos) == org
    assert (r.borrador, r.tipo, r.numero, r.parte, r.anio, r.suplemento) == (borrador, tipo, numero, parte, anio, supl)


def test_iteracion():
    assert parse("ISO/IEC CD 29115.2").iteracion == 2


@pytest.mark.parametrize("ref,prefijo", [
    ("ISO/TR 13028", "ISO/TR"),
    ("ISO/IEC TR 24766:2009", "ISO/IEC TR"),
    ("ISO/IEC/IEEE 15289:2019", "ISO/IEC/IEEE"),
    ("ISO 15801:2026", "ISO"),
])
def test_prefijo(ref, prefijo):
    assert parse(ref).prefijo == prefijo


def test_clave_ignora_prefijo_y_tipo():
    assert parse("ISO/TR 15801:2004").clave == parse("ISO 15801:2026").clave
    assert parse("ISO/IEC 15289:2006").clave == parse("ISO/IEC/IEEE 15289:2019").clave


@pytest.mark.parametrize("ref", ["Withdrawn 4866/Amd 3", "", "ISO", "ISO/IEC abc", "UNE 12345"])
def test_invalidas(ref):
    with pytest.raises(ReferenciaInvalida):
        parse(ref)


def test_partes_citadas():
    assert partes_en("1") == ("1", None, None)
    assert partes_en("TR 2") == ("2", None, None)
    assert partes_en("100-150") == (None, 100, 150)
    citadas = ["1", "TR 2", "100-150"]
    assert parte_citada("2", citadas)
    assert parte_citada("120", citadas)
    assert not parte_citada("10", citadas)
    assert not parte_citada("1Q", citadas)
    assert not parte_citada(None, citadas)
