import pytest

from iso_alert.config import ConfigError, validar


def test_normas_yaml_real(config):
    assert len(config.normas) == 99
    assert not any(n.revisar for n in config.normas)
    assert len(config.familias) == 21
    assert config.familias["square"].corto == "SQuaRE"
    assert all(f.categoria and f.descripcion for f in config.familias.values())
    assert all(n.descripcion for n in config.normas)
    assert config.familias["ciclo-vida"].categoria == "ingenieria-software"
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


def test_temario_y_relaciones(config):
    assert len(config.temario) == 38
    assert config.temario[47].titulo.startswith("Seguridad de sistemas (1)")
    n = next(n for n in config.normas if n.codigo == "ISO/IEC 27002")
    assert ("desarrolla", "ISO/IEC 27001") in [(r.tipo, r.norma) for r in n.relaciones]
    assert sum(n.certificable for n in config.normas) == 8
    assert all(n.naturaleza for n in config.normas)
    assert len(config.areas) == 9 and all(c.area for c in config.categorias.values())
    assert all(n.concepto for n in config.normas)
    assert config.temario[47].asociacion[0] == ("ISO 31000", "riesgo en general")


@pytest.mark.parametrize("cambios,mensaje", [
    ({"relaciones": [{"tipo": "inventada", "norma": "ISO 9001"}]}, "relación no válida"),
    ({"relaciones": [{"tipo": "amplia", "norma": "ISO 1"}]}, "no está en normas.yaml"),
    ({"temas": [999]}, "no está en temario.yaml"),
    ({"naturaleza": "otra"}, "naturaleza"),
])
def test_errores_didacticos(cambios, mensaje):
    datos = _datos(**cambios)
    datos["temario"] = [{"numero": 22, "titulo": "Calidad"}]
    with pytest.raises(ConfigError, match=mensaje):
        validar(datos)
