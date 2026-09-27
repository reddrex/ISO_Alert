"""Piezas de las páginas de estudio: relaciones, historia de ediciones y diagramas."""

from __future__ import annotations

import re
from collections import defaultdict

from . import modelo as m
from .config import TIPOS_RELACION, Config

# Etiqueta corta de cada relación en las flechas de los diagramas.
FLECHA = {
    "desarrolla": "desarrolla",
    "amplia": "amplía",
    "aplica": "aplica",
    "se_apoya_en": "se apoya en",
    "complementa": "complementa",
    "vocabulario_de": "vocabulario",
    "guia_de": "guía de",
    "mide": "mide",
    "evalua": "evalúa",
    "metodologia_de": "metodología",
    "metodo_conforme_a": "conforme a",
    "prueba": "prueba",
    "encapsula": "encapsula",
    "audita": "audita",
    "sustituye": "sustituye a",
    "se_situa_en": "se sitúa en",
}


def aristas(config: Config) -> list[tuple[str, str, str]]:
    """(origen, tipo, destino) de todas las relaciones declaradas."""
    return [(n.codigo, r.tipo, r.norma) for n in config.normas for r in n.relaciones]


def relaciones_de(codigo: str, todas: list[tuple[str, str, str]]) -> list[tuple[str, list[str]]]:
    """Relaciones de una norma en ambos sentidos, agrupadas por la frase que las describe."""
    grupos: dict[str, list[str]] = defaultdict(list)
    for o, t, d in todas:
        if o == codigo:
            grupos[TIPOS_RELACION[t][0]].append(d)
        elif d == codigo:
            grupos[TIPOS_RELACION[t][1]].append(o)
    return list(grupos.items())


def _nodo(codigo: str) -> str:
    return "n_" + re.sub(r"[^A-Za-z0-9]+", "_", codigo)


def diagrama(codigos: list[str], todas: list[tuple[str, str, str]], historicas: set[str],
             destacada: str | None = None) -> str | None:
    """Diagrama Mermaid con las relaciones entre las normas indicadas (None si no hay ninguna)."""
    incluidas = set(codigos)
    propias = [(o, t, d) for o, t, d in todas if o in incluidas and d in incluidas]
    if not propias:
        return None
    usados = [c for c in codigos if any(c in (o, d) for o, _, d in propias)]
    lineas = ["graph LR"]
    for c in usados:
        lineas.append(f'  {_nodo(c)}["{c}"]')
    for o, t, d in propias:
        lineas.append(f'  {_nodo(o)} -- "{FLECHA[t]}" --> {_nodo(d)}')
    hist = [c for c in usados if c in historicas]
    if hist:
        lineas.append("  classDef historica stroke-dasharray: 4 3,opacity:0.75")
        lineas.append(f"  class {','.join(_nodo(c) for c in hist)} historica")
    if destacada in usados:
        lineas.append("  classDef destacada stroke-width:3px")
        lineas.append(f"  class {_nodo(destacada)} destacada")
    return "\n".join(lineas)


def _estado_entregable(e: dict) -> str | None:
    etapa = e["etapa"]
    if etapa == m.ANULADA:
        return "Anulada"
    if m.publicado(etapa):
        return "Vigente"
    if m.proyecto_activo(etapa):
        return "En preparación: " + m.fase_proyecto(etapa)
    return None  # proyecto cancelado: no se muestra


def historia(codigo: str, numero: str, entregables: dict) -> dict[str | None, list[dict]]:
    """Ediciones y modificaciones de una norma, por parte y de más antigua a más reciente."""
    por_parte: dict[str | None, list[dict]] = defaultdict(list)
    for i, e in entregables.items():
        if codigo not in e["normas"] or e["numero"] != numero:
            continue
        estado = _estado_entregable(e)
        if estado is None:
            continue
        por_parte[e["parte"]].append({
            "id": int(i),
            "referencia": e["referencia"],
            "anio": (e["publicacion"] or "")[:4] or None,
            "estado": estado,
            "suplemento": e["suplemento"],
            "url": f"https://www.iso.org/standard/{i}.html",
            "orden": (e["publicacion"] or "9999", e["suplemento"], int(i)),
        })
    for lista in por_parte.values():
        lista.sort(key=lambda x: x["orden"])
    return dict(por_parte)
