"""Feeds Atom: uno general con los avisos y uno por norma con todos sus cambios."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from .vigilancia import TIPOS

ATOM = "http://www.w3.org/2005/Atom"
ET.register_namespace("", ATOM)
MAX_ENTRADAS = 50


def _sub(padre, etiqueta: str, texto: str | None = None, **atributos) -> ET.Element:
    el = ET.SubElement(padre, f"{{{ATOM}}}{etiqueta}", atributos)
    if texto is not None:
        el.text = texto
    return el


def feed(titulo: str, url_feed: str, url_web: str, eventos: list[dict], sitio: str,
         generado: str) -> str:
    """Feed Atom con los eventos (dicts del historial), del más reciente al más antiguo."""
    from .web import ancla

    raiz = ET.Element(f"{{{ATOM}}}feed")
    _sub(raiz, "title", titulo)
    _sub(raiz, "id", url_feed)
    _sub(raiz, "link", rel="self", href=url_feed)
    _sub(raiz, "link", rel="alternate", href=url_web)
    _sub(raiz, "updated", (eventos[0]["detectado"] + "T00:00:00Z") if eventos else generado)
    autor = _sub(raiz, "author")
    _sub(autor, "name", "Vigilancia de normas TIC (no oficial)")
    for ev in eventos[:MAX_ENTRADAS]:
        entrada = _sub(raiz, "entry")
        ref = ev["entregable"]["referencia"] if ev.get("entregable") else ", ".join(ev["normas"])
        _sub(entrada, "title", f"{TIPOS.get(ev['tipo'], ev['tipo'])}: {ref}")
        _sub(entrada, "id", f"tag:reddrex.github.io,2026:evento/{ev['id']}")
        _sub(entrada, "updated", ev["detectado"] + "T00:00:00Z")
        _sub(entrada, "link", href=f"{sitio}normas/{ancla(ev['normas'][0])}/")
        _sub(entrada, "category", term=ev["tipo"], label=TIPOS.get(ev["tipo"], ev["tipo"]))
        _sub(entrada, "summary", ev["resumen"])
    ET.indent(raiz)
    return '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(raiz, encoding="unicode") + "\n"
