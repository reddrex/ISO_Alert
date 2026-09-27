"""Informe de validación de normas.yaml contra el dataset ISO."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from . import modelo as m
from .config import Config
from .fuentes.iso import Descarga
from .modelo import Estado
from .resolver import Entregable, Indice, Resultado, resolver_todo

PLANTILLAS = Path(__file__).resolve().parents[2] / "plantillas"


def url_iso(e: Entregable) -> str:
    return f"https://www.iso.org/standard/{e.id}.html"


def _e(e: Entregable) -> dict:
    return {
        "iso_id": e.id,
        "referencia": e.referencia,
        "anio": e.anio,
        "etapa": m.etapa_txt(e.etapa),
        "titulo_en": e.titulo_en,
        "url": url_iso(e),
    }


def _unicos(es) -> list[dict]:
    return [_e(e) for e in {e.id: e for e in es}.values()]


def candidatos(res: Resultado, config: Config, indice: Indice, vigilados: set[str]) -> list[dict]:
    """Para una norma no encontrada: publicaciones cercanas del comité de su familia."""
    if not res.norma.familia:
        return []
    comites = {
        e.comite
        for n in config.normas
        if n.familia == res.norma.familia and n.numero != res.norma.numero
        for e in indice.por_numero.get(n.numero, [])
        if e.comite
    }
    objetivo = int(res.norma.numero)
    encontrados = [
        e
        for num, es in indice.por_numero.items()
        if num not in vigilados and abs(int(num) - objetivo) <= 20
        for e in es
        if e.comite in comites and not e.suplemento and (m.publicado(e.etapa) or m.proyecto_activo(e.etapa))
    ]
    return [_e(e) for e in sorted(encontrados, key=lambda e: (e.ref.numero, e.orden))][:10]


def _sugerencias(res: Resultado, cands: list[dict]) -> list[str]:
    s = []
    if res.estado == Estado.NO_ENCONTRADA:
        s.append("Quitarla de la fase 1 o marcarla como norma solo UNE para la fase 2.")
    elif res.estado == Estado.NO_PUBLICADA:
        s.append("Quitarla o dejarla con estado «No publicada».")
    if res.codigo_actual:
        s.append(f"Cambiar el código a «{res.codigo_actual}».")
    ed = res.edicion_citada
    if ed and ed["resultado"] == "no_existe":
        vig = ", ".join(ed["vigentes"]) or "ninguna"
        s.append(f"No hay edición ISO de {ed['anio']}; puede ser el año de la adopción UNE. Vigente: {vig}.")
    if res.partes_no_encontradas:
        s.append(
            "Las partes citadas " + ", ".join(res.partes_no_encontradas)
            + " no existen con ese número; revisar partes_citadas."
        )
    if res.norma.revisar and not s:
        s.append("Encontrada en el dataset. Si los datos de arriba resuelven la duda, borrar «revisar».")
    return s


def construir(config: Config, indice: Indice, descarga: Descarga | None) -> dict:
    resultados = resolver_todo(config, indice)
    vigilados = {n.numero for n in config.normas}
    entradas = []
    for res in resultados:
        n = res.norma
        cands = candidatos(res, config, indice, vigilados) if res.estado == Estado.NO_ENCONTRADA else []
        rel = res.relevantes
        entradas.append({
            "codigo": n.codigo,
            "nombre": n.nombre,
            "alcance": n.alcance,
            "categoria": n.categoria,
            "familia": n.familia,
            "encontrada": res.estado != Estado.NO_ENCONTRADA,
            "estado": res.estado.value,
            "estado_txt": res.estado.etiqueta,
            "subestado": res.subestado.value if res.subestado else None,
            "subestado_txt": res.subestado.etiqueta if res.subestado else None,
            "vigentes": _unicos(l.vigente for l in rel if l.vigente),
            "en_desarrollo": _unicos(p for l in rel for p in l.proyectos),
            "sustituida_por": _unicos(x for l in rel for x in l.sustituida_por),
            "suplementos": _unicos(s for l in rel for s in l.suplementos),
            "partes": None if n.alcance == "norma" else {
                "total": len(res.lineas),
                "relevantes": len(rel),
                "citadas": list(n.partes_citadas),
                "recuento": {e.value: c for e, c in res.recuento.items()},
                "detalle_citadas": [
                    {"parte": l.parte, "estado_txt": l.estado.etiqueta,
                     "referencia": l.ultima.referencia if l.ultima else None}
                    for l in rel
                ] if n.partes_citadas else [],
            },
            "edicion_citada": res.edicion_citada,
            "codigo_actual": res.codigo_actual,
            "partes_no_encontradas": res.partes_no_encontradas,
            "candidatos": cands,
            "notas": res.notas,
            "revisar": n.revisar,
            "sugerencias": _sugerencias(res, cands),
        })

    return {
        "generado": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "fuente": None if descarga is None else {
            "url": descarga.url,
            "last_modified": descarga.last_modified,
            "sha256": descarga.sha256,
            "registros": len(indice) + indice.no_reconocidas,
        },
        "resumen": {
            "total": len(entradas),
            "por_estado": dict(Counter(e["estado"] for e in entradas)),
            "con_revisar": sum(1 for e in entradas if e["revisar"]),
            "ediciones_superadas": sum(
                1 for e in entradas if e["edicion_citada"] and e["edicion_citada"]["resultado"] != "vigente"
            ),
            "con_sugerencias": sum(1 for e in entradas if e["sugerencias"]),
        },
        "normas": entradas,
    }


def a_markdown(informe: dict) -> str:
    env = Environment(
        loader=FileSystemLoader(PLANTILLAS),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    env.filters["celda"] = lambda s: (s or "").replace("|", "\\|")
    return env.get_template("validacion.md.j2").render(i=informe, etiquetas={e.value: e.etiqueta for e in Estado})
