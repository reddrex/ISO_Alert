"""Normas UNE a partir del BOE (PLAN.md fase 2): registro, cambios y estado por norma.

``data/une.json`` guarda solo las normas UNE (y proyectos PNE) cuyo número ISO
coincide con alguna norma vigilada. La clave de emparejamiento es la misma que
en ISO, ``(numero, parte)``, sacada del código UNE: ``UNE-EN ISO/IEC 27001:2023``
→ ``("27001", None)``.

El registro se construye leyendo las resoluciones del BOE en orden: las aprobadas
dan de alta la norma (y marcan como sustituidas las de «Sustituye a»); las
anuladas la dan de baja. Una UNE aprobada antes de que el BOE publicara los anexos
como tablas (~2004) solo se conoce si aparece después en «Sustituye a» o en una
anulación.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from .config import Config, Norma
from .fuentes import boe
from .referencias import parte_citada
from .vigilancia import Evento, _id

ESQUEMA = 1
DESDE = "2000-01-01"
# Si el BOE no ha publicado la relación de aprobadas del mismo mes pasados estos días,
# una anulación se evalúa igualmente.
DIAS_ESPERA_APROBADAS = 62
# Un día del BOE que falla se salta (y se anota) solo si tiene más de estos días.
DIAS_TOLERANCIA = 7
# Un proyecto en información pública se muestra como «en preparación» durante este tiempo como mucho.
DIAS_PROYECTO = 730

_ISO = re.compile(
    r"(?<![A-Za-z])(?:ISO|IEC)(?:/(?:ISO|IEC|IEEE|ASTM|TR|TS|PAS|DTR|DTS))*"
    r"(?:\s+(?:TR|TS|PAS|DTR|DTS|FDIS|DIS|CD|Guide|GUIDE))?"
    r"\s+(?P<numero>\d+)(?P<parte>(?:-[0-9A-Za-z]+)*)"
)
_ADOPTADA = re.compile(r"\(((?:ISO|IEC)[^()]*?:(\d{4})[^()]*)\)")


@dataclass(frozen=True)
class CodigoUNE:
    codigo: str
    numero: str
    parte: str | None
    anio: str | None
    suplemento: bool  # modificación (A1, 1M), corrección (AC) o erratum
    proyecto: bool  # PNE (en información pública)


def parse(codigo: str) -> CodigoUNE | None:
    """Número y parte ISO de un código UNE/PNE. None si no adopta una norma ISO o IEC."""
    m = _ISO.search(codigo)
    if not m or not re.match(r"^(?:UNE|PNE|EN)\b", codigo):
        return None
    resto = codigo[m.end():]
    anio = re.match(r"\s*:(\d{4})", resto)
    return CodigoUNE(
        codigo=codigo,
        numero=m["numero"],
        parte=m["parte"].lstrip("-") or None,
        anio=anio[1] if anio else None,
        suplemento="/" in resto or "ERRATUM" in resto.upper(),
        proyecto=codigo.startswith("PNE"),
    )


def iso_adoptada(titulo: str | None) -> tuple[str, str] | None:
    """(referencia, año) de la edición ISO que adopta, si el título la cita: «… (ISO/IEC 27001:2022)»."""
    m = _ADOPTADA.search(titulo or "")
    return (" ".join(m[1].split()), m[2]) if m else None


def vacio(desde: str = DESDE) -> dict:
    return {
        "version_esquema": ESQUEMA,
        "generado": None,
        "cobertura": {
            "desde": desde,
            "primera_tabla": None,
            "ultimo_dia": (date.fromisoformat(desde) - timedelta(days=1)).isoformat(),
        },
        "resoluciones": {},
        "normas": {},
        "proyectos": {},
    }


def numeros_vigilados(config: Config) -> set[str]:
    return {n.numero for n in config.normas}


def _entrada(codigo: str, c: CodigoUNE | None, titulo: str | None) -> dict:
    return {
        "codigo": codigo,
        "numero": c.numero if c else None,
        "parte": c.parte if c else None,
        "anio": c.anio if c else None,
        "suplemento": c.suplemento if c else False,
        "titulo": titulo,
        "iso_adoptada": None,
        "aprobada": None,
        "sustituye": [],
        "sustituida_por": [],
        "anulada": None,
        "anulacion_evaluada": False,
    }


def aplicar(datos: dict, res: boe.Resolucion, filas: list[dict] | None, numeros: set[str]) -> None:
    """Incorpora una resolución al registro."""
    datos["resoluciones"][res.id] = {
        "fecha": res.fecha, "tipo": res.tipo, "mes": res.mes,
        "filas": len(filas) if filas is not None else None,
    }
    if filas is None or res.tipo == "correccion":
        return
    cob = datos["cobertura"]
    if cob["primera_tabla"] is None or res.fecha < cob["primera_tabla"]:
        cob["primera_tabla"] = res.fecha
    ref = {"boe": res.id, "fecha": res.fecha, "mes": res.mes}
    normas = datos["normas"]

    def alta(codigo: str, c: CodigoUNE | None) -> dict:
        return normas.setdefault(codigo, _entrada(codigo, c, None))

    for fila in filas:
        codigo = fila["codigo"]
        c = parse(codigo)
        vigilada = bool(c and c.numero in numeros)
        if res.tipo == "aprobadas":
            sustituidas = [(s, parse(s)) for s in fila["sustituye"]]
            if not (vigilada or any(cs and cs.numero in numeros for _, cs in sustituidas)):
                continue
            e = alta(codigo, c)
            e["titulo"] = fila["titulo"] or e["titulo"]
            adoptada = iso_adoptada(fila["titulo"])
            e["iso_adoptada"] = adoptada[0] if adoptada else e["iso_adoptada"]
            e["aprobada"] = ref
            e["sustituye"] = fila["sustituye"]
            for s, cs in sustituidas:
                vieja = alta(s, cs)
                if codigo not in vieja["sustituida_por"]:
                    vieja["sustituida_por"].append(codigo)
        elif res.tipo == "anuladas":
            if vigilada or codigo in normas:
                e = alta(codigo, c)
                e["titulo"] = e["titulo"] or fila["titulo"]
                e["anulada"] = ref
        elif res.tipo == "info_publica" and vigilada:
            adoptada = iso_adoptada(fila["titulo"])
            datos["proyectos"][codigo] = {
                "codigo": codigo, "numero": c.numero, "parte": c.parte,
                "titulo": fila["titulo"], "iso_adoptada": adoptada[0] if adoptada else None,
                "plazo": fila["plazo"], **ref,
            }


def recorrer(datos: dict, hasta: date, numeros: set[str], cache: Path | None = None,
             hilos: int = 4, al_avanzar: Callable[[dict], None] | None = None,
             bloque: int = 31) -> list[boe.Resolucion]:
    """Lee los BOE desde el día siguiente a ``cobertura.ultimo_dia`` hasta ``hasta`` (incluido).

    Avanza por bloques de días y llama a ``al_avanzar`` tras cada uno, para poder
    reanudar una carga larga. Devuelve las resoluciones leídas.
    """
    leidas: list[boe.Resolucion] = []
    dia = date.fromisoformat(datos["cobertura"]["ultimo_dia"]) + timedelta(days=1)
    with ThreadPoolExecutor(hilos) as ex:
        while dia <= hasta:
            dias = [dia + timedelta(days=i) for i in range(bloque) if dia + timedelta(days=i) <= hasta]
            resoluciones = []
            for d, lista in zip(dias, ex.map(lambda d: _sumario(d, cache), dias)):
                if isinstance(lista, boe.FuenteError):
                    # Algunos días antiguos dan error 500 siempre en la API del BOE: se anotan y se sigue.
                    # Un día reciente, en cambio, detiene la lectura para reintentarlo en la siguiente ejecución.
                    if d > hasta - timedelta(days=DIAS_TOLERANCIA):
                        raise lista
                    fallidos = datos["cobertura"].setdefault("dias_fallidos", [])
                    if d.isoformat() not in fallidos:
                        fallidos.append(d.isoformat())
                    continue
                resoluciones += lista or []
            nuevas = [r for r in resoluciones if r.id not in datos["resoluciones"]]
            xmls = list(ex.map(lambda r: boe.documento(r.id, cache), nuevas))
            orden = {"aprobadas": 0, "anuladas": 1, "info_publica": 2, "correccion": 3}
            for r, xml in sorted(zip(nuevas, xmls), key=lambda p: (p[0].fecha, orden[p[0].tipo], p[0].id)):
                try:
                    filas = None if r.tipo == "correccion" else boe.tabla(xml)
                except boe.FuenteError as e:
                    raise boe.FuenteError(f"{e} ({r.id}, {r.url})") from e
                aplicar(datos, r, filas, numeros)
                leidas.append(r)
            datos["cobertura"]["ultimo_dia"] = dias[-1].isoformat()
            dia = dias[-1] + timedelta(days=1)
            if al_avanzar:
                al_avanzar(datos)
    return leidas


def _sumario(dia: date, cache: Path | None):
    try:
        return boe.sumario(dia, cache)
    except boe.FuenteError as e:
        return e


# ---- Emparejamiento con normas.yaml ----

def corresponde(e: dict, n: Norma) -> bool:
    """¿La UNE ``e`` es una versión de la norma ``n`` (o de una de sus partes citadas)?"""
    if e["numero"] != n.numero:
        return False
    if n.alcance == "norma":
        return e["parte"] == n.parte
    return not n.partes_citadas or parte_citada(e["parte"], list(n.partes_citadas))


def normas_de(e: dict, config: Config) -> list[str]:
    return [n.codigo for n in config.normas if e["numero"] == n.numero and (
        n.alcance == "serie" or e["parte"] == n.parte
    )]


def vigente(e: dict) -> bool:
    return e["anulada"] is None and not e["sustituida_por"]


# ---- Cambios (vigilancia diaria) ----

def _notificable(e: dict, config: Config) -> bool:
    return any(corresponde(e, n) for n in config.normas)


def eventos(anterior: dict, nuevo: dict, config: Config, detectado: str) -> list[Evento]:
    """Cambios entre dos registros UNE. Marca como evaluadas las anulaciones que ya se pueden juzgar.

    Una anulación con sustituta no avisa (avisa la UNE nueva). Como la relación de
    anuladas y la de aprobadas del mismo mes pueden salir en días distintos, la
    anulación espera a que se publique la de aprobadas de su mes.
    """
    resultado: list[Evento] = []
    meses_aprobadas = {r["mes"] for r in nuevo["resoluciones"].values() if r["tipo"] == "aprobadas"}
    hoy = date.fromisoformat(detectado)
    viejas = anterior["normas"]
    for codigo, e in sorted(nuevo["normas"].items()):
        normas = normas_de(e, config)
        if not normas:
            continue
        antes = viejas.get(codigo) or {}
        if e["aprobada"] and not antes.get("aprobada"):
            iso = f" (adopta la {e['iso_adoptada']})" if e["iso_adoptada"] else ""
            if e["suplemento"]:
                resumen = f"UNE publica la modificación {codigo}{iso}."
            elif e["sustituye"]:
                resumen = f"UNE publica {codigo}{iso}, que sustituye a {', '.join(e['sustituye'])}."
            else:
                resumen = f"UNE publica {codigo}{iso}."
            resultado.append(_evento("adopcion_une", e, normas, resumen, config, detectado, e["aprobada"]))
        if e["anulada"] and not e["anulacion_evaluada"]:
            espera = date.fromisoformat(e["anulada"]["fecha"]) + timedelta(days=DIAS_ESPERA_APROBADAS)
            if e["anulada"]["mes"] in meses_aprobadas or hoy >= espera:
                e["anulacion_evaluada"] = True
                if not e["sustituida_por"]:
                    resultado.append(_evento(
                        "anulacion", e, normas, f"UNE anula {codigo} sin sustituirla por otra norma.",
                        config, detectado, e["anulada"],
                    ))
    for codigo, p in sorted(nuevo["proyectos"].items()):
        if (anterior["proyectos"].get(codigo) or {}).get("boe") == p["boe"]:
            continue  # un mismo PNE puede volver a información pública en otra resolución
        normas = normas_de(p, config)
        if not normas:
            continue
        iso = f", que adopta la {p['iso_adoptada']}," if p["iso_adoptada"] else ""
        plazo = f" Plazo de alegaciones: {p['plazo']} días." if p.get("plazo") else ""
        resultado.append(Evento(
            id=_id("une", "proyecto_une_info_publica", codigo, p["boe"]),
            tipo="proyecto_une_info_publica",
            normas=normas,
            resumen=f"El proyecto {codigo}{iso} está en información pública.{plazo}",
            notificable=False,
            detectado=detectado,
            dato_fecha=p["fecha"],
            fuente="une",
            entregable={"referencia": codigo, "url": boe.HTML.format(p["boe"])},
        ))
    return sorted(resultado, key=lambda ev: (not ev.notificable, ev.normas, ev.id))


def _evento(tipo: str, e: dict, normas: list[str], resumen: str, config: Config,
            detectado: str, ref: dict) -> Evento:
    return Evento(
        id=_id("une", tipo, e["codigo"], ref["boe"]),
        tipo=tipo,
        normas=normas,
        resumen=resumen,
        notificable=_notificable(e, config),
        detectado=detectado,
        dato_fecha=ref["fecha"],
        fuente="une",
        entregable={"referencia": e["codigo"], "url": boe.HTML.format(ref["boe"])},
        sustituye=[{"referencia": s} for s in e["sustituye"]],
    )


def cerrar_anulaciones(datos: dict) -> None:
    """Tras una carga inicial: las anulaciones históricas no generan avisos."""
    for e in datos["normas"].values():
        if e["anulada"]:
            e["anulacion_evaluada"] = True


# ---- Estado por norma (web) ----

ESTADOS_UNE = {
    "al_dia": "Al día",
    "anterior": "Edición ISO anterior",
    "sin_dato": "Sin dato de edición",
    "sin_une": "Sin UNE conocida",
}


def _fecha(e: dict) -> str:
    return (e["aprobada"] or e["anulada"] or {}).get("fecha") or e["anio"] or ""


def _comparar(e: dict, iso_vigente: dict[tuple, str]) -> tuple[str, bool]:
    """¿La UNE adopta la edición ISO vigente? Devuelve (estado, deducido).

    Primero, por la edición que cita su título. Si no la cita, por fechas: una UNE
    aprobada antes del año de la ISO vigente no puede adoptarla, y una aprobada
    después de que ISO la publicara casi seguro que sí (``deducido``).
    ``iso_vigente`` da la fecha (AAAA-MM-DD o AAAA) de publicación de la ISO vigente.
    """
    iso_fecha = iso_vigente.get((e["numero"], e["parte"]))
    if not iso_fecha:
        return "sin_dato", False
    if e["iso_adoptada"]:
        adoptada = re.search(r":(\d{4})", e["iso_adoptada"])[1]
        return ("al_dia" if adoptada >= iso_fecha[:4] else "anterior"), False
    if e["aprobada"]:
        aprobada = e["aprobada"]["fecha"]
        if aprobada[:4] < iso_fecha[:4]:
            return "anterior", False
        if aprobada[:4] > iso_fecha[:4] or (len(iso_fecha) > 4 and aprobada > iso_fecha):
            return "al_dia", True
    return "sin_dato", False


def resumen(n: Norma, registro: dict | None, iso_vigente: dict[tuple, str]) -> dict | None:
    """UNE de una norma: vigentes (con su comparación con la ISO vigente), históricas y proyectos.

    ``iso_vigente`` da la fecha de publicación de la edición ISO vigente por (numero, parte).
    """
    if registro is None:
        return None
    propias = [e for e in registro["normas"].values() if corresponde(e, n)]
    vigentes = sorted((e for e in propias if vigente(e) and not e["suplemento"]), key=lambda e: (e["parte"] or "", _fecha(e), e["anio"] or ""))
    vig = [
        {**e, "estado": estado, "deducido": deducido, "url": _url(e["aprobada"])}
        for e in vigentes for estado, deducido in [_comparar(e, iso_vigente)]
    ]
    # Una modificación solo sigue vigente si lo sigue la edición a la que modifica.
    bases = {e["codigo"] for e in vigentes}
    suplementos = [
        {**e, "url": _url(e["aprobada"])} for e in propias
        if vigente(e) and e["suplemento"] and re.split(r"/| ERRATUM", e["codigo"])[0] in bases
    ]
    historicas = sorted(
        ({**e, "url": _url(e["aprobada"] or e["anulada"])} for e in propias if not vigente(e)),
        key=_fecha, reverse=True,
    )
    # Un proyecto deja de mostrarse cuando ya hay una UNE aprobada después de su información pública.
    ultima = {}
    for e in propias:
        if e["aprobada"]:
            clave = (e["numero"], e["parte"])
            ultima[clave] = max(ultima.get(clave, ""), e["aprobada"]["fecha"])
    # Tampoco los de hace más de dos años: seguramente se aprobaron en una relación que no se pudo leer.
    limite = (date.fromisoformat(registro["cobertura"]["ultimo_dia"]) - timedelta(days=DIAS_PROYECTO)).isoformat()
    proyectos = [
        {**p, "url": boe.HTML.format(p["boe"])} for p in registro["proyectos"].values()
        if corresponde(p, n) and p["fecha"] > max(ultima.get((p["numero"], p["parte"]), ""), limite)
    ]
    # Si el BOE no enlazó alguna sustitución, puede quedar más de una «vigente» por parte:
    # para el estado cuenta la más reciente.
    ultimas = {(v["numero"], v["parte"]): v for v in sorted(vig, key=lambda v: (_fecha(v), v["anio"] or ""))}
    estados = {v["estado"] for v in ultimas.values()}
    if not vig:
        estado = "sin_une"
    elif "anterior" in estados:
        estado = "anterior"
    elif estados == {"al_dia"}:
        estado = "al_dia"
    else:
        estado = "sin_dato"
    return {
        "vigentes": vig,
        "suplementos": suplementos,
        "historicas": historicas,
        "proyectos": sorted(proyectos, key=lambda p: p["fecha"], reverse=True),
        # Todas, de la más reciente a la más antigua, para la historia de la ficha.
        "historia": sorted(vig + suplementos + historicas, key=lambda e: (_fecha(e), e["codigo"]), reverse=True),
        "estado": estado,
        "etiqueta": ESTADOS_UNE[estado],
        "anios": {e["anio"]: e["codigo"] for e in propias if e["anio"] and not e["suplemento"]},
    }


def _url(ref: dict | None) -> str | None:
    return boe.HTML.format(ref["boe"]) if ref else None
