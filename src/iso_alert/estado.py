"""data/estado.json: estado actual de las normas vigiladas (PLAN.md §6).

``entregables`` es una vista plana por id de todo lo que está en el alcance
de alguna norma; sobre ella se calcularán los cambios de un día a otro.
``normas`` es la vista que usa la web, con referencias a esos ids.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from .config import Config
from .fuentes.iso import Descarga
from .resolver import Entregable, Indice, Linea, Resultado, resolver_todo

VERSION_ESQUEMA = 1

_SUFIJO_PARTE = re.compile(r"\s+[—–-]\s+Part\s+[\w-]+\s*:.*$")


def _entregable(e: Entregable, normas: list[str]) -> dict:
    return {
        "referencia": e.referencia,
        "numero": e.ref.numero,
        "parte": e.ref.parte,
        "tipo": e.tipo,
        "suplemento": e.suplemento,
        "etapa": e.etapa,
        "edicion": e.edicion,
        "publicacion": e.publicacion,
        "titulo_en": e.titulo_en,
        "replaces": list(e.replaces),
        "replaced_by": list(e.replaced_by),
        "normas": normas,
    }


def _ids(es) -> list[int]:
    return list(dict.fromkeys(e.id for e in es))


def titulo_oficial(res: Resultado) -> str | None:
    """Título ISO en inglés; en series, sin el sufijo «— Part N: …»."""
    lineas = res.relevantes or res.lineas
    if not lineas:
        return None
    if res.norma.alcance == "norma":
        e = lineas[0].ultima
        return e.titulo_en if e else None
    for linea in lineas:
        e = linea.ultima
        if e and e.titulo_en:
            return _SUFIJO_PARTE.sub("", e.titulo_en)
    return None


def _parte(l: Linea) -> dict:
    return {
        "parte": l.parte,
        "citada": l.citada,
        "estado": l.estado.value,
        "subestado": l.subestado.value if l.subestado else None,
        "vigente": l.vigente.id if l.vigente else None,
        "ultima": l.ultima.id if l.ultima else None,
        "proyectos": _ids(l.proyectos),
        "suplementos": _ids(l.suplementos),
        "sustituida_por": _ids(l.sustituida_por),
    }


def construir(config: Config, indice: Indice, descarga: Descarga | None) -> dict:
    resultados = resolver_todo(config, indice)
    entregables: dict[int, tuple[Entregable, list[str]]] = {}

    def registrar(e: Entregable, codigo: str) -> int:
        _, normas = entregables.setdefault(e.id, (e, []))
        if codigo not in normas:
            normas.append(codigo)
        return e.id

    normas = {}
    for res in resultados:
        n = res.norma
        for e in res.entregables:
            registrar(e, n.codigo)
        rel = res.relevantes
        sustitutos = [x for l in rel for x in l.sustituida_por]
        # Sustitutos y proyectos pueden ser de otro número (9126 → 25010).
        for l in res.lineas:
            for x in l.sustituida_por + l.proyectos:
                registrar(x, n.codigo)
        normas[n.codigo] = {
            "nombre": n.nombre,
            "alcance": n.alcance,
            "categoria": n.categoria,
            "familia": n.familia,
            "estado": res.estado.value,
            "subestado": res.subestado.value if res.subestado else None,
            "titulo_en": titulo_oficial(res),
            "vigentes": _ids(l.vigente for l in rel if l.vigente),
            "en_desarrollo": _ids(p for l in rel for p in l.proyectos),
            "sustituida_por": _ids(sustitutos),
            "suplementos": _ids(s for l in rel for s in l.suplementos),
            "partes": [_parte(l) for l in res.lineas] if n.alcance == "serie" else None,
            "recuento": {e.value: c for e, c in res.recuento.items()},
            "edicion_citada": res.edicion_citada,
            "codigo_actual": res.codigo_actual,
            "partes_citadas": list(n.partes_citadas),
            "une": n.une,
            "contexto": n.contexto,
        }

    return {
        "version_esquema": VERSION_ESQUEMA,
        "generado": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "fuentes": {
            "iso": None if descarga is None else {
                "url": descarga.url,
                "last_modified": descarga.last_modified,
                "etag": descarga.etag,
                "sha256": descarga.sha256,
                "registros": len(indice) + indice.no_reconocidas,
            },
        },
        "entregables": {
            str(i): _entregable(e, ns) for i, (e, ns) in sorted(entregables.items())
        },
        "normas": normas,
    }
