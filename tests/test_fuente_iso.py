import json

import pytest

from iso_alert.fuentes.iso import FuenteError, leer

from .conftest import FIXTURES


def _registro(**cambios):
    with open(FIXTURES / "iso_subset.jsonl", encoding="utf-8") as f:
        r = json.loads(f.readline())
    r.update(cambios)
    return r


def _escribir(tmp_path, registros, extra=""):
    p = tmp_path / "d.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in registros) + extra, encoding="utf-8")
    return p


def test_lee_fixture_completo():
    assert sum(1 for _ in leer(FIXTURES / "iso_subset.jsonl", minimo=1000)) > 1000


def test_campo_que_falta(tmp_path):
    r = _registro()
    del r["currentStage"]
    with pytest.raises(FuenteError, match="faltan campos"):
        list(leer(_escribir(tmp_path, [r]), minimo=0))


def test_tipo_cambiado(tmp_path):
    with pytest.raises(FuenteError, match="currentStage"):
        list(leer(_escribir(tmp_path, [_registro(currentStage="60.60")]), minimo=0))


def test_json_invalido(tmp_path):
    with pytest.raises(FuenteError, match="JSON inválido"):
        list(leer(_escribir(tmp_path, [_registro()], extra="{roto\n"), minimo=0))


def test_dataset_demasiado_pequeno(tmp_path):
    with pytest.raises(FuenteError, match="se esperaban al menos"):
        list(leer(_escribir(tmp_path, [_registro()]), minimo=10))


def test_vacio_nunca_es_sin_cambios(tmp_path):
    p = tmp_path / "vacio.jsonl"
    p.write_text("", encoding="utf-8")
    with pytest.raises(FuenteError):
        list(leer(p))


def test_campos_nuevos_se_toleran(tmp_path):
    assert len(list(leer(_escribir(tmp_path, [_registro(nuevoCampo=1)]), minimo=0))) == 1
