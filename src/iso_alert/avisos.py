"""Avisos por GitHub Issues (PLAN.md §8).

Cada evento notificable abre un Issue con un marcador ``<!-- evento:ID -->`` en
el cuerpo; antes de abrir uno se buscan los existentes con ese marcador, así que
repetir una ejecución no duplica avisos.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections import defaultdict

from .vigilancia import TIPOS, Evento

API = "https://api.github.com"
ETIQUETA_AVISO = "aviso"
# etiqueta: (color, descripción)
ETIQUETAS = {
    "aviso": ("1f4e5f", "Aviso automático de cambio en una norma vigilada"),
    "edicion-nueva": ("2e7d32", "ISO o UNE han publicado una edición nueva"),
    "modificacion": ("1f5fa8", "ISO ha publicado una modificación (Amd)"),
    "anulacion": ("b3261e", "ISO o UNE han anulado una norma sin sustituirla"),
    "parte-nueva": ("5b3fa8", "Parte nueva de una serie vigilada"),
    "fuente:iso": ("bfbfbf", "Detectado en ISO Open Data"),
    "fuente:une": ("bfbfbf", "Detectado en el BOE (normas UNE)"),
    "fallo-fuente": ("d93f0b", "La fuente de datos ha fallado o ha cambiado de formato"),
    "fallo-boe": ("d93f0b", "La lectura del BOE (normas UNE) ha fallado"),
    "fuente-desactualizada": ("fbca04", "La fuente de datos lleva días sin actualizarse"),
    "revision-manual": ("d93f0b", "Demasiados cambios a la vez: revisar antes de avisar"),
}
ETIQUETA_TIPO = {
    "edicion_nueva": "edicion-nueva",
    "modificacion_publicada": "modificacion",
    "anulacion": "anulacion",
    "parte_nueva": "parte-nueva",
    "adopcion_une": "edicion-nueva",
}
MAX_AVISOS = 15


class GuardaAntirruido(RuntimeError):
    """Demasiados avisos en una ejecución: probablemente un fallo, no cambios reales."""


class GitHub:
    """Cliente mínimo de la API de GitHub para Issues y etiquetas."""

    def __init__(self, token: str, repo: str):
        self.token = token
        self.repo = repo

    @classmethod
    def desde_entorno(cls) -> GitHub | None:
        token, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
        return cls(token, repo) if token and repo else None

    def _peticion(self, metodo: str, ruta: str, datos: dict | None = None):
        cuerpo = json.dumps(datos).encode() if datos is not None else None
        req = urllib.request.Request(
            f"{API}{ruta}", data=cuerpo, method=metodo,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
            },
        )
        for intento in range(3):
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    texto = resp.read()
                    return json.loads(texto) if texto else None
            except urllib.error.HTTPError as e:
                if e.code in (502, 503, 504) and intento < 2:
                    time.sleep(5 * (intento + 1))
                    continue
                raise

    def issues(self, etiqueta: str, estado: str = "all") -> list[dict]:
        resultado, pagina = [], 1
        while True:
            lote = self._peticion(
                "GET", f"/repos/{self.repo}/issues?labels={etiqueta}&state={estado}&per_page=100&page={pagina}"
            )
            resultado += [i for i in lote if "pull_request" not in i]
            if len(lote) < 100:
                return resultado
            pagina += 1

    def crear_issue(self, titulo: str, cuerpo: str, etiquetas: list[str]) -> int:
        return self._peticion("POST", f"/repos/{self.repo}/issues",
                              {"title": titulo, "body": cuerpo, "labels": etiquetas})["number"]

    def editar_issue(self, numero: int, **campos) -> None:
        self._peticion("PATCH", f"/repos/{self.repo}/issues/{numero}", campos)

    def comentar(self, numero: int, texto: str) -> None:
        self._peticion("POST", f"/repos/{self.repo}/issues/{numero}/comments", {"body": texto})

    def asegurar_etiquetas(self) -> None:
        existentes = {e["name"] for e in self._peticion("GET", f"/repos/{self.repo}/labels?per_page=100")}
        for nombre, (color, desc) in ETIQUETAS.items():
            if nombre not in existentes:
                self._peticion("POST", f"/repos/{self.repo}/labels",
                               {"name": nombre, "color": color, "description": desc})


def _marcador(id_: str) -> str:
    return f"<!-- evento:{id_} -->"


def _cuerpo(grupo: list[Evento], sitio: str) -> str:
    ev = grupo[0]
    lineas = []
    for e in grupo:
        lineas.append(f"**{e.resumen}**")
        if e.entregable:
            url = e.entregable.get("url") or f"https://www.iso.org/standard/{e.entregable['id']}.html"
            lineas.append(f"- {'Resolución del BOE' if e.fuente == 'une' else 'Documento'}: [{e.entregable['referencia']}]({url})")
        if e.sustituye:
            lineas.append("- Sustituye a: " + ", ".join(s["referencia"] for s in e.sustituye))
        lineas.append("")
    from .web import ancla  # evita importación circular al cargar el módulo
    normas = ", ".join(f"[{c}]({sitio}normas/{ancla(c)}/)" for c in ev.normas)
    lineas += [
        f"- Norma vigilada: {normas}",
        f"- Detectado el {ev.detectado}" + (
            f" en el BOE del {ev.dato_fecha}." if ev.fuente == "une"
            else f" con los datos de ISO del {ev.dato_fecha}." if ev.dato_fecha else "."
        ),
        "",
        f"Historial completo: {sitio}historial/",
        "",
        "*Aviso automático de una web no oficial: compruébalo en "
        + ("[une.org](https://www.une.org) o en el BOE" if ev.fuente == "une" else "[iso.org](https://www.iso.org)")
        + " antes de darlo por seguro.*",
        "",
        *(_marcador(e.id) for e in grupo),
    ]
    return "\n".join(lineas)


def _titulo(grupo: list[Evento]) -> str:
    ev = grupo[0]
    if len(grupo) > 1:
        return f"{TIPOS[ev.tipo]}: {len(grupo)} cambios en {', '.join(ev.normas)}"
    ref = ev.entregable["referencia"] if ev.entregable else ", ".join(ev.normas)
    return f"{TIPOS[ev.tipo]}: {ref}"


def agrupar(eventos: list[Evento]) -> list[list[Evento]]:
    """Un aviso por evento, salvo las partes nuevas: un aviso por serie y ejecución."""
    grupos: list[list[Evento]] = []
    partes: dict[tuple, list[Evento]] = defaultdict(list)
    for ev in eventos:
        if not ev.notificable:
            continue
        if ev.tipo == "parte_nueva":
            partes[tuple(ev.normas)].append(ev)
        else:
            grupos.append([ev])
    return grupos + list(partes.values())


def publicar(eventos: list[Evento], cliente: GitHub, sitio: str, maximo: int = MAX_AVISOS) -> dict[str, int]:
    """Abre un Issue por grupo de eventos notificables. Devuelve id de evento → número de Issue."""
    grupos = agrupar(eventos)
    if len(grupos) > maximo:
        raise GuardaAntirruido(f"{len(grupos)} avisos en una sola ejecución (máximo {maximo})")
    if not grupos:
        return {}
    cliente.asegurar_etiquetas()
    existentes: dict[str, int] = {}
    for issue in cliente.issues(ETIQUETA_AVISO):
        for linea in (issue.get("body") or "").splitlines():
            if linea.startswith("<!-- evento:"):
                existentes[linea[len("<!-- evento:"):-len(" -->")]] = issue["number"]
    numeros: dict[str, int] = {}
    for grupo in grupos:
        ya = next((existentes[e.id] for e in grupo if e.id in existentes), None)
        numero = ya or cliente.crear_issue(
            _titulo(grupo), _cuerpo(grupo, sitio),
            [ETIQUETA_AVISO, ETIQUETA_TIPO[grupo[0].tipo], f"fuente:{grupo[0].fuente}"],
        )
        for e in grupo:
            numeros[e.id] = numero
    return numeros


def issue_de_estado(cliente: GitHub, etiqueta: str, titulo: str, cuerpo: str, abierto: bool) -> None:
    """Mantiene un único Issue abierto por problema (fuente caída, desactualizada…).

    Mientras el problema dura no se comenta cada día, para no notificar en exceso.
    """
    cliente.asegurar_etiquetas()
    abiertos = cliente.issues(etiqueta, estado="open")
    if abierto:
        if not abiertos:
            cliente.crear_issue(titulo, cuerpo, [etiqueta])
    else:
        for issue in abiertos:
            cliente.comentar(issue["number"], "Resuelto: la última comprobación ha ido bien.")
            cliente.editar_issue(issue["number"], state="closed")
