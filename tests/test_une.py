"""Normas UNE desde el BOE: parser de resoluciones, registro, cambios y estado por norma."""

import copy
from pathlib import Path

import pytest

from iso_alert import estado, une, web
from iso_alert.fuentes import boe

FIXTURES = Path(__file__).parent / "fixtures" / "boe"
HOY = "2026-10-14"


def xml(id_):
    return (FIXTURES / f"{id_}.xml").read_text(encoding="utf-8")


def res(id_, tipo, fecha="2026-08-13", mes="2026-07"):
    return boe.Resolucion(id_, fecha, tipo, mes, "")


@pytest.mark.parametrize("codigo, esperado", [
    ("UNE-EN ISO/IEC 27001:2023", ("27001", None, "2023", False, False)),
    ("UNE-ISO/IEC 20000-1:2018", ("20000", "1", "2018", False, False)),
    ("UNE-ISO/TR 13028:2011 IN", ("13028", None, "2011", False, False)),
    ("UNE-EN ISO 9001:2015/A1:2024", ("9001", None, "2015", True, False)),
    ("UNE-EN ISO/IEC 17011:2004 ERRATUM", ("17011", None, "2004", True, False)),
    ("PNE-prEN ISO/IEC 29100", ("29100", None, None, False, True)),
    ("PNE-ISO/IEC DTS 17021-16", ("17021", "16", None, False, True)),
    ("UNE-EN ISO/IEC/IEEE 8802-1Q:2022", ("8802", "1Q", "2022", False, False)),
])
def test_parse(codigo, esperado):
    c = une.parse(codigo)
    assert (c.numero, c.parte, c.anio, c.suplemento, c.proyecto) == esperado


def test_parse_sin_iso():
    assert une.parse("UNE 23035-1:2026") is None
    assert une.parse("UNE-EN 45003:1995") is None


def test_iso_adoptada():
    assert une.iso_adoptada("Sistemas de gestión. (ISO/IEC 27001:2022).") == ("ISO/IEC 27001:2022", "2022")
    assert une.iso_adoptada("Marco de privacidad. (ISO/IEC FDIS 17065:2026).")[1] == "2026"
    assert une.iso_adoptada("Sin referencia") is None


def test_clasificar():
    t = "Resolución de 2 de agosto de 2026, … por la que se publica la relación de normas UNE aprobadas por la Asociación Española de Normalización, durante el mes de julio de 2026."
    assert boe.clasificar(t) == ("aprobadas", "2026-07")
    t = "Resolución de 22 de enero de 2001, … por la que se modifica la Resolución de 18 de septiembre de 2000, por la que se publica la relación de normas UNE anuladas por AENOR, correspondientes al mes de julio de 2000."
    assert boe.clasificar(t) == ("correccion", "2000-07")
    assert boe.clasificar("Corrección de erratas de la Resolución … normas UNE anuladas durante el mes de mayo de 2003.")[0] == "correccion"
    assert boe.clasificar("Resolución … por la que se publica el Convenio con la UNE") is None


def test_tabla_aprobadas():
    filas = boe.tabla(xml("BOE-A-2005-2855"))
    assert len(filas) == 195
    e = next(f for f in filas if f["codigo"] == "UNE-EN ISO/IEC 17011:2004 ERRATUM")
    # Dos normas sustituidas en la misma celda, separadas solo por espacios.
    assert e["sustituye"] == ["UNE-EN 45003:1995", "UNE-EN 45010:1998"]


def test_tabla_otras_epocas():
    assert boe.tabla(xml("BOE-A-2001-3379")) is None  # anexo escaneado
    viejo = boe.tabla(xml("BOE-A-2000-18828"))  # cabecera mal maquetada
    assert viejo and viejo[0]["codigo"] == "UNE 53196:1988"
    anuladas = boe.tabla(xml("BOE-A-2012-3031"))
    assert anuladas[0] == {"codigo": "EN ISP 10607-1:1993", "titulo": anuladas[0]["titulo"], "sustituye": [], "plazo": None}
    proyectos = boe.tabla(xml("BOE-A-2026-17711"))
    assert any(p["codigo"] == "PNE-prEN ISO/IEC 29100" and p["plazo"] == "30" for p in proyectos)


@pytest.fixture
def registro(config):
    """Registro con dos meses reales: ISO 14721 (aprobada en julio) y los proyectos de julio."""
    datos = une.vacio("2026-08-01")
    numeros = une.numeros_vigilados(config)
    une.aplicar(datos, res("BOE-A-2026-17710", "aprobadas"), boe.tabla(xml("BOE-A-2026-17710")), numeros)
    une.aplicar(datos, res("BOE-A-2026-17711", "info_publica"), boe.tabla(xml("BOE-A-2026-17711")), numeros)
    return datos


def test_registro(registro):
    nueva, vieja = registro["normas"]["UNE-ISO 14721:2026"], registro["normas"]["UNE-ISO 14721:2015"]
    assert nueva["aprobada"]["boe"] == "BOE-A-2026-17710" and nueva["sustituye"] == ["UNE-ISO 14721:2015"]
    assert vieja["sustituida_por"] == ["UNE-ISO 14721:2026"] and not une.vigente(vieja)
    # Solo las UNE de normas vigiladas: la 17020 no está en el temario.
    assert not any("17020" in c for c in registro["normas"])
    assert {"PNE-prEN ISO/IEC 29100", "PNE-prEN ISO/IEC 27018"} <= set(registro["proyectos"])
    assert registro["cobertura"]["primera_tabla"] == "2026-08-13"


def test_eventos_adopcion_y_proyectos(registro, config):
    evs = une.eventos(une.vacio("2026-08-01"), registro, config, HOY)
    adopcion = [e for e in evs if e.tipo == "adopcion_une"]
    assert [(e.entregable["referencia"], e.notificable) for e in adopcion] == [("UNE-ISO 14721:2026", True)]
    assert adopcion[0].normas == ["ISO 14721"] and adopcion[0].fuente == "une"
    assert "sustituye a UNE-ISO 14721:2015" in adopcion[0].resumen
    assert adopcion[0].entregable["url"].endswith("BOE-A-2026-17710")
    proyectos = [e for e in evs if e.tipo == "proyecto_une_info_publica"]
    assert proyectos and not any(e.notificable for e in proyectos)
    assert une.eventos(registro, copy.deepcopy(registro), config, HOY) == []


def test_anulacion_espera_a_las_aprobadas(config):
    anterior = une.vacio("2026-08-01")
    anterior["normas"]["UNE-ISO 30301:2019"] = une._entrada("UNE-ISO 30301:2019", une.parse("UNE-ISO 30301:2019"), None)
    nuevo = copy.deepcopy(anterior)
    numeros = une.numeros_vigilados(config)
    une.aplicar(nuevo, res("BOE-X-1", "anuladas", "2026-08-12"), [
        {"codigo": "UNE-ISO 30301:2019", "titulo": "x", "sustituye": [], "plazo": None},
    ], numeros)
    # Aún no se ha publicado la relación de aprobadas de julio: no se sabe si tiene sustituta.
    assert une.eventos(anterior, nuevo, config, "2026-08-12") == []
    assert not nuevo["normas"]["UNE-ISO 30301:2019"]["anulacion_evaluada"]
    une.aplicar(nuevo, res("BOE-X-2", "aprobadas", "2026-08-13"), [], numeros)
    evs = une.eventos(anterior, nuevo, config, "2026-08-13")
    assert [(e.tipo, e.notificable) for e in evs] == [("anulacion", True)]
    assert nuevo["normas"]["UNE-ISO 30301:2019"]["anulacion_evaluada"]


def test_anulacion_con_sustituta_no_avisa(registro, config):
    anterior = copy.deepcopy(registro)
    une.aplicar(registro, res("BOE-X-3", "anuladas", "2026-08-13"), [
        {"codigo": "UNE-ISO 14721:2015", "titulo": "x", "sustituye": [], "plazo": None},
    ], une.numeros_vigilados(config))
    assert une.eventos(anterior, registro, config, HOY) == []


def test_resumen(registro, config):
    n = next(n for n in config.normas if n.codigo == "ISO 14721")
    r = une.resumen(n, registro, {("14721", None): "2025-11-03"})
    assert [e["codigo"] for e in r["vigentes"]] == ["UNE-ISO 14721:2026"]
    # El título no cita la edición ISO, pero se aprobó después de que ISO la publicara.
    assert r["estado"] == "al_dia" and r["vigentes"][0]["deducido"]
    # Mismo año y sin fecha exacta: no se puede saber.
    assert une.resumen(n, registro, {("14721", None): "2026"})["estado"] == "sin_dato"
    assert r["historicas"][0]["codigo"] == "UNE-ISO 14721:2015"
    # Una UNE aprobada antes del año de la ISO vigente no puede adoptarla.
    assert une.resumen(n, registro, {("14721", None): "2027"})["estado"] == "anterior"
    privacidad = next(n for n in config.normas if n.codigo == "ISO/IEC 29100")
    r = une.resumen(privacidad, registro, {})
    assert r["estado"] == "sin_une" and r["proyectos"][0]["codigo"] == "PNE-prEN ISO/IEC 29100"


def test_resumen_al_dia(config):
    datos = une.vacio("2026-08-01")
    une.aplicar(datos, res("BOE-X-4", "aprobadas"), [
        {"codigo": "UNE-EN ISO/IEC 27001:2023", "titulo": "Seguridad (ISO/IEC 27001:2022).", "sustituye": [], "plazo": None},
    ], une.numeros_vigilados(config))
    n = next(n for n in config.normas if n.codigo == "ISO/IEC 27001")
    assert une.resumen(n, datos, {("27001", None): "2022"})["estado"] == "al_dia"
    assert une.resumen(n, datos, {("27001", None): "2026"})["estado"] == "anterior"


def test_sumario_desde_cache(tmp_path, monkeypatch):
    from datetime import date
    (tmp_path / "sumarios").mkdir()
    (tmp_path / "sumarios" / "20260813.json").write_text(
        '[["BOE-A-2026-17710", "Resolución … relación de normas UNE aprobadas durante el mes de julio de 2026."],'
        ' ["BOE-A-2026-1", "Convenio con la Asociación Española de Normalización"]]',
        encoding="utf-8",
    )
    (tmp_path / "sumarios" / "20260816.json").write_text("null", encoding="utf-8")
    monkeypatch.setattr(boe, "_get", lambda *a, **k: pytest.fail("no debe ir a la red"))
    [r] = boe.sumario(date(2026, 8, 13), tmp_path)  # los candidatos se clasifican al leer
    assert (r.id, r.tipo, r.mes) == ("BOE-A-2026-17710", "aprobadas", "2026-07")
    assert boe.sumario(date(2026, 8, 16), tmp_path) is None


def test_web_con_une(registro, config, indice, tmp_path):
    from iso_alert import informe
    web.generar(estado.construir(config, indice, None), informe.construir(config, indice, None),
                config, tmp_path, [], registro)
    md = (tmp_path / "estado.md").read_text(encoding="utf-8")
    assert "<th>UNE</th>" in md and 'id="f-une"' in md
    assert 'data-une="sin_une"' in md
    ficha = (tmp_path / web.FICHAS / "iso-14721.md").read_text(encoding="utf-8")
    assert "UNE-ISO 14721:2026" in ficha and "Historia de las normas UNE" in ficha
    assert "PNE-prEN ISO/IEC 29100" in (tmp_path / web.FICHAS / "iso-iec-29100.md").read_text(encoding="utf-8")
    une_md = (tmp_path / "une.md").read_text(encoding="utf-8")
    assert "| [ISO 14721](normas/iso-14721.md) |" in une_md and "UNE-ISO 14721:2026" in une_md
    assert "## UNE en preparación" in une_md and "PNE-prEN ISO/IEC 29100" in une_md
    assert 'href="estado/?une=sin_une"' in une_md


def test_aviso_une(registro, config):
    from iso_alert import avisos
    from tests.test_vigilancia import GitHubFalso

    evs = une.eventos(une.vacio("2026-08-01"), registro, config, HOY)
    gh = GitHubFalso()
    avisos.publicar(evs, gh, "https://ejemplo/")
    [issue] = gh.issues_creados
    assert issue["title"] == "Norma UNE nueva: UNE-ISO 14721:2026"
    assert set(issue["labels"]) == {"aviso", "edicion-nueva", "fuente:une"}
    assert "Resolución del BOE: [UNE-ISO 14721:2026](https://www.boe.es/diario_boe/txt.php?id=BOE-A-2026-17710)" in issue["body"]
    assert "en el BOE del 2026-08-13" in issue["body"] and "une.org" in issue["body"]


def test_resumen_suplementos_y_duplicadas(config):
    datos = une.vacio("2026-08-01")
    numeros = une.numeros_vigilados(config)
    fila = lambda c, t="x", s=(): {"codigo": c, "titulo": t, "sustituye": list(s), "plazo": None}  # noqa: E731
    une.aplicar(datos, res("BOE-X-5", "aprobadas", "2015-10-01", "2015-09"), [
        fila("UNE-EN ISO 9001:2015", "Sistemas de gestión de la calidad. (ISO 9001:2015)."),
        fila("UNE-EN ISO 9001:2008", "Sistemas de gestión de la calidad. (ISO 9001:2008)."),
    ], numeros)
    une.aplicar(datos, res("BOE-X-6", "aprobadas", "2024-05-01", "2024-04"), [
        fila("UNE-EN ISO 9001:2015/A1:2024"),
        fila("UNE-EN ISO 9001:2008/1M:2009"),
    ], numeros)
    n = next(n for n in config.normas if n.codigo == "ISO 9001")
    r = une.resumen(n, datos, {("9001", None): "2015"})
    # La 2008 sigue "vigente" porque el BOE no la enlazó, pero el estado lo decide la más reciente.
    assert r["estado"] == "al_dia"
    assert [e["codigo"] for e in r["suplementos"]] == ["UNE-EN ISO 9001:2015/A1:2024", "UNE-EN ISO 9001:2008/1M:2009"]
    une.aplicar(datos, res("BOE-X-7", "aprobadas", "2025-05-01", "2025-04"), [
        fila("UNE-EN ISO 9001:2025", "(ISO 9001:2025).", ["UNE-EN ISO 9001:2015", "UNE-EN ISO 9001:2008"]),
    ], numeros)
    r = une.resumen(n, datos, {("9001", None): "2025"})
    assert [e["codigo"] for e in r["vigentes"]] == ["UNE-EN ISO 9001:2025"] and r["suplementos"] == []


def test_clasificar_sin_une_en_el_titulo():
    # 2015-2016: «relación de normas aprobadas por la Asociación Española de Normalización…».
    t = ("Resolución de 1 de septiembre de 2015, … por la que se publica la relación de normas aprobadas por la "
         "Asociación Española de Normalización y Certificación durante el mes de julio de 2015.")
    assert boe.clasificar(t) == ("aprobadas", "2015-07")


def test_limpiar_codigo():
    assert boe.limpiar_codigo("UNE-ISO/IEC 27002: 2009.") == "UNE-ISO/IEC 27002:2009"
    assert boe.limpiar_codigo("UNE-EN ISO 9001:2015 / A1:2024") == "UNE-EN ISO 9001:2015/A1:2024"


def test_proyecto_que_vuelve_a_informacion_publica(registro, config):
    anterior = copy.deepcopy(registro)
    une.aplicar(registro, res("BOE-X-8", "info_publica", "2026-10-10", "2026-09"), [
        {"codigo": "PNE-prEN ISO/IEC 29100", "titulo": "Marco de privacidad. (ISO/IEC 29100:2024).", "sustituye": [], "plazo": "30"},
    ], une.numeros_vigilados(config))
    [ev] = une.eventos(anterior, registro, config, HOY)
    assert ev.tipo == "proyecto_une_info_publica" and ev.entregable["url"].endswith("BOE-X-8")
    assert ev.resumen.startswith("El proyecto PNE-prEN ISO/IEC 29100, que adopta la ISO/IEC 29100:2024, está")
