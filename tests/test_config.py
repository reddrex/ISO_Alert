import pytest

from iso_alert.config import ConfigError, validar


def test_normas_yaml_real(config):
    assert len(config.normas) == 99
    assert not any(n.revisar for n in config.normas)
    assert len(config.familias) == 10
    assert config.familias["square"].corto == "SQuaRE"
    assert len(config.categorias) == 16
    assert {n.categoria for n in config.normas} == set(config.categorias)
    n = next(n for n in config.normas if n.codigo == "ISO/IEC 2382-37")
    assert (n.numero, n.parte) == ("2382", "37")


def _datos(**norma):
    base = {"codigo": "ISO 9001", "nombre": "x", "alcance": "norma", "categoria": "calidad"}
    return {
        "familias": [{"id": "f", "nombre": "F"}],
        "categorias": [{"id": "calidad", "nombre": "Calidad"}],
        "normas": [{**base, **norma}],
    }


@pytest.mark.parametrize("cambios,mensaje", [
    ({"alcance": "familia"}, "no es norma|serie"),
    ({"familia": "inexistente"}, "no existe"),
    ({"categoria": "inexistente"}, "categoría 'inexistente' no existe"),
    ({"edicion_citada": "15"}, "edicion_citada"),
    ({"codigo": "ISO 9001:2015"}, "no debe llevar año"),
    ({"codigo": "ISO/DIS 31700"}, "etapa de borrador"),
    ({"codigo": "UNE 9001"}, "no reconocible"),
    ({"partes_citadas": "1"}, "partes_citadas"),
    ({"otro": 1}, "campos desconocidos"),
    ({"nombre": None}, "falta 'nombre'"),
])
def test_errores(cambios, mensaje):
    with pytest.raises(ConfigError) as e:
        validar(_datos(**cambios))
    assert mensaje in str(e.value)


def test_duplicados():
    datos = _datos()
    datos["normas"].append(dict(datos["normas"][0]))
    with pytest.raises(ConfigError, match="duplicado"):
        validar(datos)
