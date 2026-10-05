"""Genera las páginas del sitio a partir de data/ (PLAN.md §7)."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from . import didactico, informe, rss, une
from . import modelo as m
from .config import NATURALEZAS, Config
from .modelo import Estado, Subestado

PLANTILLAS = Path(__file__).resolve().parents[2] / "plantillas"

# Orden de los estados en filtros, resúmenes y al ordenar la columna Estado.
ORDEN_ESTADOS = [Estado.VIGENTE, Estado.EN_REVISION, Estado.SUSTITUIDA, Estado.ANULADA, Estado.NO_PUBLICADA]
# En las páginas de estudio, las normas en estos estados se muestran al final de su grupo.
HISTORICAS = {Estado.SUSTITUIDA, Estado.ANULADA, Estado.NO_PUBLICADA}
# Carpetas de docs/ con una página por norma y por familia; se regeneran enteras en cada build.
FICHAS = "normas"
FAMILIAS = "familias"
TEMARIO = "temario"
FEEDS = "feeds"
SITIO = "https://reddrex.github.io/ISO_Alert/"


def ancla(codigo: str) -> str:
    """«ISO/IEC 27001» → «iso-iec-27001»."""
    return re.sub(r"[^a-z0-9]+", "-", codigo.lower()).strip("-")


def titulo_corto(titulo: str) -> str:
    """Primera frase del título de un tema del temario."""
    return re.split(r"(?<=[a-z\)])\.\s", titulo, maxsplit=1)[0].rstrip(".")


def _entorno() -> Environment:
    env = Environment(
        loader=FileSystemLoader(PLANTILLAS),
        undefined=StrictUndefined,
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    env.filters["titulo_corto"] = titulo_corto
    return env


class Vista:
    """Datos de estado.json y normas.yaml preparados para las plantillas."""

    def __init__(self, estado: dict, config: Config, registro_une: dict | None = None):
        self.estado = estado
        self.config = config
        self.une = registro_une
        self.ent = estado["entregables"]
        self.aristas = didactico.aristas(config)

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
        temario = self.config.temario
        filas = []
        for n in self.config.normas:
            d = self.estado["normas"][n.codigo]
            estado = Estado(d["estado"])
            sub = Subestado(d["subestado"]) if d["subestado"] else None
            vigentes = [self.e(i) for i in d["vigentes"]]
            # Aprobación de la edición vigente más reciente (en una serie, la última parte publicada).
            aprobacion = max((self.ent[str(i)]["publicacion"] or "" for i in d["vigentes"]), default="") or None
            fam = self.config.familias.get(n.familia) if n.familia else None
            cat = self.config.categorias.get(n.categoria)
            # Área del mapa: la de la familia si la tiene (25012 se estudia en SQuaRE, área Software).
            cat_mapa = self.config.categorias.get(fam.categoria) if fam and fam.categoria else cat
            area = self.config.areas.get(cat_mapa.area) if cat_mapa and cat_mapa.area else None
            ed = d["edicion_citada"]
            # Fecha de la edición ISO vigente por (número, parte), para saber si la UNE la adopta.
            iso_vigente: dict[tuple, str] = {}
            for i in d["vigentes"]:
                x = self.ent[str(i)]
                if not x["suplemento"] and x["publicacion"]:
                    clave = (x["numero"], x["parte"])
                    iso_vigente[clave] = max(iso_vigente.get(clave, ""), x["publicacion"])
            une_boe = une.resumen(n, self.une, iso_vigente)
            partes = None
            if d["partes"] is not None:
                desc_partes = dict(n.partes_descripcion)
                todas = [self._parte(p, desc_partes) for p in d["partes"]]
                partes = {
                    "citadas": [p for p in todas if p["citada"]] if d["partes_citadas"] else todas,
                    "otras": [p for p in todas if not p["citada"]] if d["partes_citadas"] else [],
                    "vigentes": sum(1 for p in todas if p["citada"] and p["vigente"]),
                    "relevantes": sum(1 for p in todas if p["citada"]),
                }
            temas_familia = [t for t in (fam.temas if fam else ()) if t not in n.temas]
            filas.append({
                "codigo": n.codigo,
                "codigo_orden": f"{int(n.numero):06d}-{n.parte or ''}",
                "ancla": ancla(n.codigo),
                "ficha": f"{FICHAS}/{ancla(n.codigo)}/",
                "nombre": n.nombre,
                "resumen": n.resumen,
                "concepto": n.concepto,
                "pregunta": n.pregunta,
                "area": area,
                "descripcion": n.descripcion,
                "ejemplo": n.ejemplo,
                "naturaleza": NATURALEZAS.get(n.naturaleza) if n.naturaleza else None,
                "certificable": n.certificable,
                "claves": list(n.claves),
                "temas": [temario[t] for t in sorted(n.temas) if t in temario],
                "temas_familia": [temario[t] for t in sorted(temas_familia) if t in temario],
                "alcance": n.alcance,
                "numero": n.numero,
                "titulo_en": d["titulo_en"],
                "familia": fam,
                "familia_pagina": f"{FAMILIAS}/{fam.id}/" if fam else None,
                "familia_orden": orden_familia.get(n.familia, len(orden_familia)),
                "categoria": cat,
                "estado": estado,
                "estado_orden": ORDEN_ESTADOS.index(estado) if estado in ORDEN_ESTADOS else 9,
                "subestado": sub,
                "historica": estado in HISTORICAS,
                "vigentes": vigentes,
                "aprobacion": aprobacion,
                "anio_aprobacion": aprobacion[:4] if aprobacion else None,
                "en_desarrollo": [self.e(i) for i in d["en_desarrollo"]],
                "sustituida_por": [self.e(i) for i in d["sustituida_por"]],
                "suplementos": [self.e(i) for i in d["suplementos"]],
                "partes": partes,
                "edicion_citada": ed,
                "superada": bool(ed and ed["resultado"] != "vigente"),
                "une": n.une,
                "une_boe": une_boe,
                "contexto": n.contexto,
                "texto": " ".join(filter(None, [
                    n.codigo, n.nombre, n.resumen, d["titulo_en"], n.contexto, n.une,
                    *(e["codigo"] for e in (une_boe["vigentes"] if une_boe else [])),
                ])).lower(),
            })
        return filas

    def _parte(self, p: dict, descripciones: dict[str, str]) -> dict:
        ultima = self.e(p["ultima"]) if p["ultima"] else None
        return {
            "parte": p["parte"],
            "citada": p["citada"],
            "estado": Estado(p["estado"]),
            "subestado": Subestado(p["subestado"]) if p["subestado"] else None,
            "vigente": p["vigente"] is not None,
            "ultima": ultima,
            "titulo_parte": _titulo_parte(ultima["titulo_en"]) if ultima else None,
            "descripcion": descripciones.get(p["parte"]),
            "proyectos": [self.e(i) for i in p["proyectos"]],
            "sustituida_por": [self.e(i) for i in p["sustituida_por"]],
        }

    def _historicas(self, filas: list[dict]) -> set[str]:
        return {f["codigo"] for f in filas if f["historica"]}

    def diagrama(self, codigos: list[str], filas: list[dict], destacada: str | None = None) -> str | None:
        return didactico.diagrama(codigos, self.aristas, self._historicas(filas), destacada)

    def miembros(self, fam, filas: list[dict]) -> list[dict]:
        return ordenar([f for f in filas if f["familia"] and f["familia"].id == fam.id])

    def familia(self, fam, filas: list[dict]) -> dict:
        normas = self.miembros(fam, filas)
        cat = self.config.categorias.get(fam.categoria) if fam.categoria else None
        numeros = set(fam.temas) | {t.numero for f in normas for t in f["temas"]}
        return {
            "familia": fam,
            "area": self.config.areas.get(cat.area) if cat and cat.area else None,
            "normas": normas,
            "diagrama": self.diagrama([f["codigo"] for f in normas], filas),
            "temas": [self.config.temario[t] for t in sorted(numeros) if t in self.config.temario],
            "temas_familia": set(fam.temas),
        }

    def mapa(self, filas: list[dict]) -> list[dict]:
        """Áreas del mapa de estudio con sus familias y sus normas sin familia."""
        bloques = []
        for area in self.config.areas.values():
            familias = []
            for fam in self.config.familias.values():
                cat = self.config.categorias.get(fam.categoria) if fam.categoria else None
                if cat and cat.area == area.id:
                    familias.append({"familia": fam, "normas": self.miembros(fam, filas)})
            sueltas = ordenar([f for f in filas if not f["familia"] and f["area"] and f["area"].id == area.id])
            if familias or sueltas:
                bloques.append({"area": area, "familias": familias, "sueltas": sueltas})
        return bloques

    def temario(self, filas: list[dict]) -> list[dict]:
        """Temas del temario con las familias y normas que citan."""
        resultado = []
        for tema in sorted(self.config.temario.values(), key=lambda t: t.numero):
            familias = []
            for fam in self.config.familias.values():
                if tema.numero in fam.temas:
                    familias.append({"familia": fam, "normas": ordenar([
                        f for f in filas if f["familia"] and f["familia"].id == fam.id
                    ])})
            # Normas citadas una a una (aunque su familia también se cite en conjunto).
            normas = ordenar([f for f in filas if any(t.numero == tema.numero for t in f["temas"])])
            codigos = [f["codigo"] for f in normas]
            if len(codigos) < 2:  # el tema solo cita familias: el diagrama las muestra enteras
                codigos += [f["codigo"] for g in familias for f in g["normas"] if f["codigo"] not in codigos]
            por_codigo = {f["codigo"]: f for f in filas}
            asociacion = [(por_codigo[c], idea) for c, idea in tema.asociacion if c in por_codigo]
            # Una sola lista: primero la cadena de asociación (de lo general a lo específico),
            # después las normas citadas que no están en ella.
            en_cadena = {x["codigo"] for x, _ in asociacion}
            lista = [{"norma": x, "idea": idea} for x, idea in asociacion]
            lista += [{"norma": x, "idea": None} for x in normas if x["codigo"] not in en_cadena]
            areas = []
            for fila in lista:
                area = fila["norma"]["area"]
                if area and area not in areas:
                    areas.append(area)
            corto = titulo_corto(tema.titulo)
            resultado.append({
                "tema": tema,
                "corto": corto,
                # El enunciado sin repetir la primera frase, que ya es el título de la página.
                "resto_titulo": tema.titulo[len(corto):].lstrip(". ").strip() if tema.titulo.startswith(corto) else tema.titulo,
                "familias": familias,
                "normas": normas,
                "asociacion": asociacion,
                "lista": lista,
                "areas": areas,
                "diagrama": self.diagrama(codigos, filas),
            })
        return resultado

    def ficha(self, f: dict, por_codigo: dict[str, dict], filas: list[dict]) -> dict:
        relaciones = [
            (frase, [por_codigo[c] for c in codigos])
            for frase, codigos in didactico.relaciones_de(f["codigo"], self.aristas)
        ]
        vecinas = [f["codigo"]] + [c["codigo"] for _, cs in relaciones for c in cs]
        historia = didactico.historia(f["codigo"], f["numero"], self.ent)
        if f["alcance"] == "serie" and f["partes"]:
            relevantes = [p["parte"] for p in f["partes"]["citadas"]]
            historia = {p: historia[p] for p in relevantes if p in historia}
        hermanas = []
        if f["familia"]:
            hermanas = [x for x in ordenar([y for y in filas if y["familia"] and y["familia"].id == f["familia"].id])
                        if x["codigo"] != f["codigo"]]
        cadena = self.miembros(f["familia"], filas) if f["familia"] else []
        pos = next((i for i, x in enumerate(cadena) if x["codigo"] == f["codigo"]), None)
        return {
            "cadena": cadena,
            "anterior": cadena[pos - 1] if pos else None,
            "siguiente": cadena[pos + 1] if pos is not None and pos + 1 < len(cadena) else None,
            "relaciones": relaciones,
            "diagrama": self.diagrama(list(dict.fromkeys(vecinas)), filas, destacada=f["codigo"]),
            "historia": historia,
            "hermanas": hermanas,
        }

    def resumen(self, filas: list[dict]) -> dict:
        iso = self.estado["fuentes"]["iso"] or {}
        return {
            "total": len(filas),
            "por_estado": [(e, sum(1 for f in filas if f["estado"] == e)) for e in ORDEN_ESTADOS],
            "revision_periodica": sum(1 for f in filas if f["subestado"] == Subestado.REVISION_PERIODICA),
            "dato_fecha": (iso.get("last_modified") or "")[:10] or None,
            "comprobado": self.estado["generado"][:10],
        }


def _titulo_parte(titulo: str | None) -> str | None:
    """«… — Part 1: Service management system requirements» → «Service management system requirements»."""
    if not titulo:
        return None
    encontrado = re.search(r"Part\s+[\w-]+\s*:\s*(.+)$", titulo)
    return encontrado[1] if encontrado else titulo


def ordenar(grupo: list[dict]) -> list[dict]:
    """De menor a mayor número, con las antecesoras e históricas al final."""
    return sorted(grupo, key=lambda f: (f["historica"], f["codigo_orden"]))


def _cambios(historial: list[dict], por_codigo: dict[str, dict]) -> list[dict]:
    """Eventos del historial preparados para las plantillas (del más reciente al más antiguo)."""
    from .vigilancia import TIPOS

    return [{
        **h,
        "etiqueta": TIPOS.get(h["tipo"], h["tipo"]),
        "filas": [por_codigo[c] for c in h["normas"] if c in por_codigo],
    } for h in historial]


def generar(estado: dict, validacion: dict, config: Config, docs: Path,
            historial: list[dict] | None = None, registro_une: dict | None = None,
            comprobado: str | None = None) -> list[Path]:
    env = _entorno()
    vista = Vista(estado, config, registro_une)
    filas = vista.filas()
    por_codigo = {f["codigo"]: f for f in filas}
    historial = historial or []
    cambios = _cambios(historial, por_codigo)
    resumen = vista.resumen(filas)
    if comprobado and comprobado[:10] > resumen["comprobado"]:
        resumen["comprobado"] = comprobado[:10]
    ctx = {
        "filas": filas,
        "por_codigo": por_codigo,
        "resumen": resumen,
        "familias": list(config.familias.values()),
        "categorias": list(config.categorias.values()),
        "temario": vista.temario(filas),
        "estados": ORDEN_ESTADOS,
        "anios_aprobacion": sorted({f["anio_aprobacion"] for f in filas if f["anio_aprobacion"]}, reverse=True),
        "naturalezas": NATURALEZAS,
        "mapa": vista.mapa(filas),
        "areas": list(config.areas.values()),
        "cambios": cambios,
        "sitio": SITIO,
        "une_cobertura": registro_une["cobertura"] if registro_une else None,
        "estados_une": une.ESTADOS_UNE,
    }
    salidas = {
        docs / "index.md": env.get_template("inicio.md.j2").render(**ctx),
        docs / "ambito.md": env.get_template("ambito.md.j2").render(**ctx),
        docs / "estado.md": env.get_template("estado.md.j2").render(**ctx),
        docs / TEMARIO / "index.md": env.get_template("temario.md.j2").render(**ctx),
        docs / "comparativas.md": env.get_template("comparativas.md.j2").render(**ctx),
        docs / "une.md": env.get_template("une.md.j2").render(**ctx),
        docs / "guia.md": env.get_template("guia.md.j2").render(**ctx),
        docs / "historial.md": env.get_template("historial.md.j2").render(**ctx),
        docs / "validacion.md": informe.a_markdown(validacion),
    }
    for carpeta in (docs / FICHAS, docs / FAMILIAS, docs / TEMARIO, docs / FEEDS):
        if carpeta.exists():
            shutil.rmtree(carpeta)
    viejo = docs / "temario.md"  # antes, una sola página con todos los temas
    if viejo.exists():
        viejo.unlink()
    plantilla_ficha = env.get_template("ficha.md.j2")
    for f in filas:
        propios = [c for c in cambios if f["codigo"] in c["normas"]]
        salidas[docs / FICHAS / f"{f['ancla']}.md"] = plantilla_ficha.render(
            f=f, cambios_norma=propios, **vista.ficha(f, por_codigo, filas), **ctx,
        )
        salidas[docs / FEEDS / f"{f['ancla']}.xml"] = rss.feed(
            f"{f['codigo']} · cambios detectados", f"{SITIO}{FEEDS}/{f['ancla']}.xml",
            f"{SITIO}{FICHAS}/{f['ancla']}/", [h for h in historial if f["codigo"] in h["normas"]],
            SITIO, estado["generado"], xsl="../feed.xsl",
        )
    salidas[docs / "feed.xml"] = rss.feed(
        f"{rss.NOMBRE} · avisos", f"{SITIO}feed.xml", f"{SITIO}historial/",
        [h for h in historial if h["notificable"]], SITIO, estado["generado"], xsl="feed.xsl",
    )
    plantilla_tema = env.get_template("tema.md.j2")
    temas = ctx["temario"]
    for i, t in enumerate(temas):
        salidas[docs / TEMARIO / f"{t['tema'].numero}.md"] = plantilla_tema.render(
            t=t,
            anterior=temas[i - 1] if i > 0 else None,
            siguiente=temas[i + 1] if i + 1 < len(temas) else None,
            **ctx,
        )
    plantilla_familia = env.get_template("familia.md.j2")
    for fam in config.familias.values():
        salidas[docs / FAMILIAS / f"{fam.id}.md"] = plantilla_familia.render(
            g=vista.familia(fam, filas), **ctx,
        )
    for ruta, texto in salidas.items():
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(texto, encoding="utf-8")
    return list(salidas)
