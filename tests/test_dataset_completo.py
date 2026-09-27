"""Tests sobre el dataset ISO completo: ``pytest -m lento`` (usa .cache/ o descarga)."""

import json

import pytest

from iso_alert.fuentes import iso
from iso_alert.referencias import try_parse

from .conftest import RAIZ

pytestmark = pytest.mark.lento


@pytest.fixture(scope="module")
def dataset():
    ruta = RAIZ / ".cache" / "iso_deliverables_metadata.jsonl"
    if not ruta.exists():
        iso.descargar(ruta)
    return ruta


def test_esquema(dataset):
    assert sum(1 for _ in iso.leer(dataset)) >= iso.MIN_REGISTROS


def test_todas_las_referencias_se_reconocen(dataset):
    fallos = []
    for linea in open(dataset, encoding="utf-8"):
        ref = json.loads(linea)["reference"]
        if try_parse(ref) is None and not ref.startswith("Withdrawn "):
            fallos.append(ref)
    assert fallos == []
