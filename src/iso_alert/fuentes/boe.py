"""BOE: resoluciones mensuales de normas UNE (PLAN.md §1.5 y fase 2).

Cada mes el Ministerio de Industria publica en el BOE la relación de normas UNE
aprobadas (con la columna «Sustituye a»), la de anuladas y las de proyectos en
información pública. El sumario diario se lee con la API de datos abiertos y
cada resolución con su XML, que trae el anexo como una ``<table>`` HTML.

Hasta 2004, más o menos, los anexos se publicaban como imágenes escaneadas: esas
resoluciones se registran sin filas (``sin_tabla``).
"""

from __future__ import annotations

import html
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from .iso import USER_AGENT, FuenteError

SUMARIO = "https://www.boe.es/datosabiertos/api/boe/sumario/{:%Y%m%d}"
XML = "https://www.boe.es/diario_boe/xml.php?id={}"
HTML = "https://www.boe.es/diario_boe/txt.php?id={}"
PAGINA = "https://www.boe.es/datosabiertos/"

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
    "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}
_MES = re.compile(r"mes(?:es)? de (\w+)(?: de (\d{4}))?", re.I)
# Correcciones y modificaciones de resoluciones anteriores: se registran, pero no se leen.
_CORRECCION = re.compile(r"^Correcci[oó]n de (?:errores|erratas)|por la que se (?:modifica|corrige)", re.I)
# Entre 2015 y 2016 los títulos dicen «relación de normas aprobadas por la Asociación…», sin «UNE».
TIPOS = (
    ("aprobadas", re.compile(r"normas (?:UNE |españolas UNE )?aprobadas", re.I)),
    ("anuladas", re.compile(r"normas (?:UNE |españolas UNE )?anuladas", re.I)),
    ("info_publica", re.compile(r"proyectos de norma", re.I)),
)
# Títulos que pueden ser de normalización; el sumario en caché guarda todos estos, sin clasificar.
_CANDIDATA = re.compile(r"UNE\b|AENOR|Normalizaci[oó]n")
_CODIGO = re.compile(r"^(?:UNE|PNE|EN)[\s-]")
# Cabeceras de las columnas del anexo → campo.
COLUMNAS = {"código": "codigo", "título": "titulo", "sustituye a": "sustituye", "plazo": "plazo"}


@dataclass(frozen=True)
class Resolucion:
    id: str
    fecha: str  # publicación en el BOE (AAAA-MM-DD)
    tipo: str  # aprobadas, anuladas, info_publica, correccion
    mes: str | None  # mes al que corresponde la relación (AAAA-MM)
    titulo: str

    @property
    def url(self) -> str:
        return HTML.format(self.id)


def _get(url: str, json_: bool = False) -> bytes | None:
    """Descarga con reintentos. Devuelve None si el BOE responde 404 (día sin boletín)."""
    cabeceras = {"User-Agent": USER_AGENT}
    if json_:
        cabeceras["Accept"] = "application/json"
    for intento in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=cabeceras), timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code < 500 and e.code != 429:
                raise FuenteError(f"BOE: HTTP {e.code} en {url}") from e
            error = e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            error = e
        time.sleep(3 * (intento + 1))
    raise FuenteError(f"BOE: no se pudo descargar {url}: {error}")


def _items(nodo):
    if isinstance(nodo, dict):
        if "identificador" in nodo and "titulo" in nodo:
            yield nodo
        for v in nodo.values():
            yield from _items(v)
    elif isinstance(nodo, list):
        for v in nodo:
            yield from _items(v)


def clasificar(titulo: str) -> tuple[str, str | None] | None:
    """(tipo, mes) de una resolución de normas UNE, o None si el título no es de una."""
    tipo = next((t for t, patron in TIPOS if patron.search(titulo)), None)
    if tipo is None or not _CANDIDATA.search(titulo):
        return None
    if _CORRECCION.search(titulo):
        tipo = "correccion"
    mes = None
    # El mes de la relación es el último que se cita ("…modifica la de 18 de septiembre, … mes de julio de 2000").
    for nombre, anio in _MES.findall(titulo):
        if nombre.lower() in MESES and anio:
            mes = f"{anio}-{MESES[nombre.lower()]:02d}"
    return tipo, mes


def sumario(dia: date, cache: Path | None = None) -> list[Resolucion] | None:
    """Resoluciones de normas UNE del BOE de ese día. None si ese día no hubo boletín.

    Con ``cache`` se guardan los títulos candidatos (no el sumario entero) de los
    días ya cerrados, sin clasificar: si cambian los patrones, una carga nueva no
    tiene que volver a pedir miles de sumarios.
    """
    ruta = cache / "sumarios" / f"{dia:%Y%m%d}.json" if cache else None
    if ruta and ruta.exists():
        candidatos = json.loads(ruta.read_text(encoding="utf-8"))
    else:
        candidatos = _candidatos(dia)
        if ruta and dia < date.today() - timedelta(days=1):
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_text(json.dumps(candidatos, ensure_ascii=False), encoding="utf-8")
    if candidatos is None:
        return None
    resultado = []
    for id_, titulo in candidatos:
        clase = clasificar(titulo)
        if clase:
            resultado.append(Resolucion(id_, dia.isoformat(), clase[0], clase[1], titulo))
    return resultado


def _candidatos(dia: date) -> list[list[str]] | None:
    datos = _get(SUMARIO.format(dia), json_=True)
    if datos is None:
        return None
    try:
        sumario = json.loads(datos)["data"]["sumario"]
    except (ValueError, KeyError, TypeError) as e:
        raise FuenteError(f"BOE: sumario del {dia} con formato inesperado") from e
    return [[i["identificador"], i["titulo"]] for i in _items(sumario) if _CANDIDATA.search(i["titulo"])]


def documento(id_: str, cache: Path | None = None) -> str:
    """XML de una disposición, con caché en disco (las disposiciones no cambian)."""
    ruta = cache / f"{id_}.xml" if cache else None
    if ruta and ruta.exists():
        return ruta.read_text(encoding="utf-8")
    datos = _get(XML.format(id_))
    if datos is None:
        raise FuenteError(f"BOE: no existe {id_}")
    texto = datos.decode("utf-8")
    if "<documento" not in texto:
        raise FuenteError(f"BOE: {id_} no es un documento XML")
    if ruta:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(texto, encoding="utf-8")
    return texto


def _celda(c: str) -> str:
    c = re.sub(r"<br\s*/?>", "\n", c)
    c = html.unescape(re.sub(r"<[^>]+>", "", c)).replace("«", "").replace("»", "")
    return "\n".join(" ".join(linea.split()) for linea in c.splitlines() if linea.strip())


def limpiar_codigo(codigo: str) -> str:
    """Espacios normalizados: «UNE-ISO/IEC 27002: 2009.» → «UNE-ISO/IEC 27002:2009»."""
    codigo = re.sub(r"\s*([:/])\s*", r"\1", " ".join(codigo.split()))
    return codigo.rstrip(".").strip()


def tabla(xml: str) -> list[dict] | None:
    """Filas del anexo como dicts {codigo, titulo, sustituye: [...], plazo}.

    None si la resolución no tiene tabla (anexo escaneado). Si no se reconoce la
    cabecera (algunas de 2000 la tienen mal maquetada), se toman como código y
    título las dos primeras celdas de las filas que empiezan por un código UNE.
    Lanza FuenteError si hay tabla pero ninguna fila parece de normas.
    """
    texto = xml[xml.find("<texto"):]
    filas = re.findall(r"<tr[^>]*>(.*?)</tr>", texto, re.S)
    if not filas:
        return None
    columnas: list[str | None] | None = None
    resultado = []
    for fila in filas:
        celdas = [_celda(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", fila, re.S)]
        if not any(celdas):
            continue
        cabecera = [next((v for k, v in COLUMNAS.items() if c.lower().rstrip(":").startswith(k)), None) for c in celdas]
        if "codigo" in cabecera and "titulo" in cabecera:
            columnas = cabecera
            continue
        if columnas is None:
            if len(celdas) < 2 or not _CODIGO.match(celdas[0]):
                continue
            d = {"codigo": celdas[0], "titulo": celdas[1]}
        elif len(celdas) != len(columnas):
            continue  # títulos del anexo ("Normas editadas en el mes de…")
        else:
            d = dict(zip(columnas, celdas))
        codigo = limpiar_codigo(d.get("codigo") or "")
        if not codigo:
            continue
        # Varias normas en una celda: por líneas, comas o solo espacios ("UNE-EN 45003:1995 UNE-EN 45010:1998").
        sustituye = [limpiar_codigo(s) for s in re.split(r"[\n,;]|\s+(?=(?:UNE|EN|PNE)\b)", d.get("sustituye") or "")]
        resultado.append({
            "codigo": codigo,
            "titulo": " ".join((d.get("titulo") or "").split()) or None,
            "sustituye": [s for s in sustituye if s],
            "plazo": d.get("plazo"),
        })
    if not resultado and any(_CODIGO.search(f) for f in filas):
        raise FuenteError("BOE: tabla de normas UNE sin filas reconocibles")
    return resultado
