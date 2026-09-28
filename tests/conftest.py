from pathlib import Path

import pytest

from iso_alert.config import cargar, validar
from iso_alert.fuentes import iso
from iso_alert.resolver import Indice

RAIZ = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def config():
    return cargar(RAIZ / "normas.yaml")


def norma(codigo, alcance="norma", **campos):
    """Entrada sintética, validada igual que las de normas.yaml."""
    datos = {"codigo": codigo, "nombre": "x", "alcance": alcance, "categoria": "c", **campos}
    return validar({"familias": [{"id": "f", "nombre": "F", "tipo": "grupo"}], "normas": [datos]}).normas[0]


@pytest.fixture(scope="session")
def indice():
    """Extracto real del dataset ISO (scripts/actualizar_fixtures.py)."""
    return Indice(iso.leer(FIXTURES / "iso_subset.jsonl", minimo=0))
