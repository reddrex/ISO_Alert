"""Genera las páginas del sitio a partir de data/ (PLAN.md §7)."""

from __future__ import annotations

import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from . import informe
from . import modelo as m
from .config import Config
from .modelo import Estado, Subestado

PLANTILLAS = Path(__file__).resolve().parents[2] / "plantillas"

# Orden de los estados en filtros, resúmenes y al ordenar la columna Estado.
ORDEN_ESTADOS = [Estado.VIGENTE, Estado.EN_REVISION, Estado.SUSTITUIDA, Estado.ANULADA, Estado.NO_PUBLICADA]
# En «Por temas», las normas en estos estados se muestran al final de su grupo.
HISTORICAS = {Estado.SUSTITUIDA, Estado.ANULADA, Estado.NO_PUBLICADA}


def ancla(codigo: str) -> str:
    """«ISO/IEC 27001» → «iso-iec-27001»."""
    return re.sub(r"[^a-z0-9]+", "-", codigo.lower()).strip("-")


def _entorno() -> Environment:
    env = Environment(
        loader=FileSystemLoader(PLANTILLAS),
        undefined=StrictUndefined,
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    return env


class Vista:
    """Datos de estado.json preparados para las plantillas."""

    def __init__(self, estado: dict, config: Config):
        self.estado = estado
        self.config = config
        self.ent = estado["entregables"]

    def e(self, i: int) -> dict:
        d = self.ent[str(i)]
        return {
            "id": i,
            "referencia": d["referencia"],
            "anio": (d["publicacion"] or "")[:4] or None,
            "url": f"https://www.iso.org/standard/{i}.html",
            "titulo_en": d["titulo_en"],
            "fase": m.fase_proyecto(d["etapa"]) if m.proyecto_activo(d["etapa"]) else None,
            "etapa": m.etapa_txt(d["etapa"]),
        }

    def filas(self) -> list[dict]:
        orden_familia = {f: i for i, f in enumerate(self.config.familias)}
        filas = []
        for n in self.config.normas:
            d = self.estado["normas"][n.codigo]
            estado = Estado(d["estado"])
            sub = Subestado(d["subestado"]) if d["subestado"] else None
            vigentes = [self.e(i) for i in d["vigentes"]]
            fam = self.config.familias.get(n.familia) if n.familia else None
            cat = self.config.categorias.get(n.categoria)
            ed = d["edicion_citada"]
            partes = None
            if d["partes"] is not None:
                todas = [self._parte(p) for p in d["partes"]]
                partes = {
                    "citadas": [p for p in todas if p["citada"]] if d["partes_citadas"] else todas,
                    "otras": [p for p in todas if not p["citada"]] if d["partes_citadas"] else [],
                    "vigentes": sum(1 for p in todas if p["citada"] and p["vigente"]),
                    "relevantes": sum(1 for p in todas if p["citada"]),
                }
            filas.append({
                "codigo": n.codigo,
                "codigo_orden": f"{int(n.numero):06d}-{n.parte or ''}",
                "ancla": ancla(n.codigo),
                "nombre": n.nombre,
                "descripcion": n.descripcion,
                "alcance": n.alcance,
                "titulo_en": d["titulo_en"],
                "familia": fam,
                "familia_orden": orden_familia.get(n.familia, len(orden_familia)),
                "categoria": cat,
                "estado": estado,
                "estado_orden": ORDEN_ESTADOS.index(estado) if estado in ORDEN_ESTADOS else 9,
                "subestado": sub,
                "vigentes": vigentes,
                "en_desarrollo": [self.e(i) for i in d["en_desarrollo"]],
                "sustituida_por": [self.e(i) for i in d["sustituida_por"]],
                "suplementos": [self.e(i) for i in d["suplementos"]],
                "partes": partes,
                "edicion_citada": ed,
                "superada": bool(ed and ed["resultado"] != "vigente"),
                "une": n.une,
                "contexto": n.contexto,
                "texto": " ".join(filter(None, [n.codigo, n.nombre, d["titulo_en"], n.contexto, n.une])).lower(),
            })
        return filas

    def _parte(self, p: dict) -> dict:
        ultima = self.e(p["ultima"]) if p["ultima"] else None
        return {
            "parte": p["parte"],
            "citada": p["citada"],
            "estado": Estado(p["estado"]),
            "subestado": Subestado(p["subestado"]) if p["subestado"] else None,
            "vigente": p["vigente"] is not None,
            "ultima": ultima,
            "proyectos": [self.e(i) for i in p["proyectos"]],
            "sustituida_por": [self.e(i) for i in p["sustituida_por"]],
        }

    def temas(self, filas: list[dict]) -> list[dict]:
        """Normas agrupadas por tema y, dentro de cada tema, por familia."""
        def tema_de(f: dict) -> str | None:
            if f["familia"] and f["familia"].categoria:
                return f["familia"].categoria
            return f["categoria"].id if f["categoria"] else None

        def ordenar(grupo: list[dict]) -> list[dict]:
            # De menor a mayor número, con las antecesoras e históricas al final.
            return sorted(grupo, key=lambda f: (f["estado"] in HISTORICAS, f["codigo_orden"]))

        temas = []
        for cat in self.config.categorias.values():
            del_tema = [f for f in filas if tema_de(f) == cat.id]
            grupos = []
            for fam in self.config.familias.values():
                normas = [f for f in del_tema if f["familia"] and f["familia"].id == fam.id]
                if normas:
                    grupos.append({"familia": fam, "normas": ordenar(normas)})
            sueltas = ordenar([f for f in del_tema if not f["familia"]])
            # Normas de este tema que se estudian en una familia de otro tema.
            ver_tambien = [
                f for f in filas
                if f["categoria"] and f["categoria"].id == cat.id and tema_de(f) != cat.id
            ]
            if grupos or sueltas:
                temas.append({"categoria": cat, "grupos": grupos, "sueltas": sueltas, "ver_tambien": ver_tambien})
        return temas

    def resumen(self, filas: list[dict]) -> dict:
        iso = self.estado["fuentes"]["iso"] or {}
        return {
            "total": len(filas),
            "por_estado": [(e, sum(1 for f in filas if f["estado"] == e)) for e in ORDEN_ESTADOS],
            "superadas": [f for f in filas if f["superada"]],
            "revision_periodica": sum(1 for f in filas if f["subestado"] == Subestado.REVISION_PERIODICA),
            "dato_fecha": (iso.get("last_modified") or "")[:10] or None,
            "comprobado": self.estado["generado"][:10],
        }


def generar(estado: dict, validacion: dict, config: Config, docs: Path) -> list[Path]:
    env = _entorno()
    vista = Vista(estado, config)
    filas = vista.filas()
    ctx = {
        "filas": filas,
        "resumen": vista.resumen(filas),
        "familias": list(config.familias.values()),
        "categorias": list(config.categorias.values()),
        "estados": ORDEN_ESTADOS,
        "temas": vista.temas(filas),
    }
    salidas = {
        docs / "index.md": env.get_template("index.md.j2").render(**ctx),
        docs / "estado.md": env.get_template("estado.md.j2").render(**ctx),
        docs / "temas.md": env.get_template("temas.md.j2").render(**ctx),
        docs / "validacion.md": informe.a_markdown(validacion),
    }
    for ruta, texto in salidas.items():
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(texto, encoding="utf-8")
    return list(salidas)
