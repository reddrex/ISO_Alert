"""Detección de cambios, historial, avisos y feeds con transiciones simuladas sobre datos reales."""

import copy
from xml.etree import ElementTree as ET

import pytest

from iso_alert import avisos, estado, rss
from iso_alert.fuentes.iso import FuenteError
from iso_alert.vigilancia import comparar, registrar

HOY = "2026-10-14"


@pytest.fixture(scope="module")
def base(config, indice):
    return estado.construir(config, indice, None)


@pytest.fixture
def nuevo(base):
    return copy.deepcopy(base)


def eventos(base, nuevo, config):
    return comparar(base, nuevo, config, HOY)


def test_sin_cambios(base, nuevo, config):
    assert eventos(base, nuevo, config) == []


def test_edicion_nueva(base, nuevo, config):
    # El CD de la 22301 se publica y la edición de 2019 se anula: un solo aviso.
    nuevo["entregables"]["93606"].update(etapa=6060, referencia="ISO 22301:2026")
    nuevo["entregables"]["75106"]["etapa"] = 9599
    evs = eventos(base, nuevo, config)
    assert [(e.tipo, e.notificable) for e in evs] == [("edicion_nueva", True)]
    e = evs[0]
    assert e.normas == ["ISO 22301"]
    assert e.resumen == "ISO publica ISO 22301:2026, que sustituye a ISO 22301:2019 y sus modificaciones."


def test_anulacion_sin_sustituto(base, nuevo, config):
    i = next(k for k, e in nuevo["entregables"].items() if e["referencia"] == "ISO/IEC 24708:2008")
    nuevo["entregables"][i]["etapa"] = 9599
    evs = eventos(base, nuevo, config)
    assert [(e.tipo, e.notificable) for e in evs] == [("anulacion", True)]


def test_modificacion_publicada(base, nuevo, config):
    nuevo["entregables"]["999001"] = {
        **nuevo["entregables"]["82875"], "referencia": "ISO/IEC 27001:2022/Amd 2:2026",
        "suplemento": True, "replaces": [], "replaced_by": [],
    }
    evs = eventos(base, nuevo, config)
    assert [(e.tipo, e.notificable) for e in evs] == [("modificacion_publicada", True)]


def test_parte_no_citada_no_avisa(base, nuevo, config):
    # La serie 9241 solo cita las partes 11 y 210: una parte nueva se registra sin aviso.
    plantilla = next(e for e in nuevo["entregables"].values() if e["referencia"] == "ISO 9241-210:2019")
    nuevo["entregables"]["999002"] = {**plantilla, "referencia": "ISO 9241-999:2026", "parte": "999",
                                     "replaces": [], "replaced_by": []}
    evs = eventos(base, nuevo, config)
    assert [(e.tipo, e.notificable) for e in evs] == [("parte_nueva", False)]


def test_estados_sin_aviso(base, nuevo, config):
    nuevo["entregables"]["93606"]["etapa"] = 4020  # el CD de la 22301 pasa a DIS
    i = next(k for k, e in nuevo["entregables"].items() if e["referencia"] == "ISO 21500:2021")
    nuevo["entregables"][i]["etapa"] = 9093  # la revisión periódica acaba en confirmación
    tipos = {(e.tipo, e.notificable) for e in eventos(base, nuevo, config)}
    assert tipos == {("proyecto_avanza", False), ("confirmada", False)}


def test_sustituta_de_otro_numero_no_duplica(base, nuevo, config):
    # 25010:2023 está en el alcance de la 9126 como sustituta: su cambio se cuenta solo en la 25010.
    i = next(k for k, e in nuevo["entregables"].items() if e["referencia"] == "ISO/IEC 25010:2023")
    nuevo["entregables"][i]["etapa"] = 9092
    evs = eventos(base, nuevo, config)
    assert [e.normas for e in evs] == [["ISO/IEC 25010"]]


def test_desaparicion_es_un_error(base, nuevo, config):
    del nuevo["entregables"]["82875"]
    with pytest.raises(FuenteError, match="desaparecido"):
        eventos(base, nuevo, config)


def test_primera_ejecucion_es_linea_base(nuevo, config):
    vacio = {"entregables": {}, "normas": {}, "fuentes": {}}
    evs = comparar(vacio, nuevo, config, HOY)
    assert len(evs) == 99 and {e.tipo for e in evs} == {"alta_vigilancia"}
    assert not any(e.notificable for e in evs)


def test_historial_idempotente(base, nuevo, config):
    nuevo["entregables"]["93606"]["etapa"] = 6060
    historial = []
    assert len(registrar(historial, eventos(base, nuevo, config))) == 1
    assert registrar(historial, eventos(base, nuevo, config)) == []
    assert len(historial) == 1


class GitHubFalso:
    def __init__(self):
        self.issues_creados = []
        self.cerrados = []

    def asegurar_etiquetas(self):
        pass

    def issues(self, etiqueta, estado="all"):
        return [i for i in self.issues_creados if etiqueta in i["labels"]
                and (estado == "all" or i["state"] == estado)]

    def crear_issue(self, titulo, cuerpo, etiquetas):
        numero = len(self.issues_creados) + 1
        self.issues_creados.append({"number": numero, "title": titulo, "body": cuerpo,
                                    "labels": etiquetas, "state": "open"})
        return numero

    def editar_issue(self, numero, **campos):
        self.issues_creados[numero - 1].update(campos)
        self.cerrados.append(numero)

    def comentar(self, numero, texto):
        pass


def test_avisos_idempotentes(base, nuevo, config):
    nuevo["entregables"]["93606"].update(etapa=6060, referencia="ISO 22301:2026")
    evs = eventos(base, nuevo, config)
    gh = GitHubFalso()
    numeros = avisos.publicar(evs, gh, "https://ejemplo/")
    assert list(numeros.values()) == [1]
    issue = gh.issues_creados[0]
    assert issue["title"] == "Edición nueva: ISO 22301:2026"
    assert "https://ejemplo/normas/iso-22301/" in issue["body"]
    assert set(issue["labels"]) == {"aviso", "edicion-nueva", "fuente:iso"}
    # Repetir la ejecución no abre otro Issue.
    assert avisos.publicar(evs, gh, "https://ejemplo/") == numeros
    assert len(gh.issues_creados) == 1


def test_guarda_antirruido(base, nuevo, config):
    for e in nuevo["entregables"].values():
        if e["etapa"] == 6060 and not e["suplemento"] and e["replaced_by"] == []:
            e["etapa"] = 9599  # anulación masiva: huele a fallo, no a cambios reales
    evs = eventos(base, nuevo, config)
    with pytest.raises(avisos.GuardaAntirruido):
        avisos.publicar(evs, GitHubFalso(), "https://ejemplo/")


def test_issue_de_estado():
    gh = GitHubFalso()
    avisos.issue_de_estado(gh, "fallo-fuente", "Falla", "detalle", abierto=True)
    avisos.issue_de_estado(gh, "fallo-fuente", "Falla", "detalle", abierto=True)
    assert len(gh.issues_creados) == 1  # un solo Issue mientras dura el problema
    avisos.issue_de_estado(gh, "fallo-fuente", "", "", abierto=False)
    assert gh.issues_creados[0]["state"] == "closed"


def test_feed_atom(base, nuevo, config):
    nuevo["entregables"]["93606"].update(etapa=6060, referencia="ISO 22301:2026")
    historial = []
    registrar(historial, eventos(base, nuevo, config))
    xml = rss.feed("Avisos", "https://ejemplo/feed.xml", "https://ejemplo/historial/", historial,
                   "https://ejemplo/", "2026-10-14T06:00:00+00:00")
    raiz = ET.fromstring(xml)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    entradas = raiz.findall("a:entry", ns)
    assert len(entradas) == 1
    assert entradas[0].find("a:title", ns).text == "Edición nueva: ISO 22301:2026"
    assert entradas[0].find("a:link", ns).get("href") == "https://ejemplo/normas/iso-22301/"
