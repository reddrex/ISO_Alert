"""Carga y validación de normas.yaml y temario.yaml."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .referencias import ReferenciaInvalida, parse

ALCANCES = {"norma", "serie"}
CAMPOS = {
    "codigo", "nombre", "resumen", "concepto", "pregunta", "descripcion", "ejemplo", "alcance", "familia", "partes_citadas", "edicion_citada",
    "une", "categoria", "contexto", "revisar", "naturaleza", "certificable", "temas", "claves",
    "relaciones", "partes_descripcion",
}

NATURALEZAS = {
    "requisitos": "Norma de requisitos",
    "vocabulario": "Fundamentos y vocabulario",
    "guia": "Guía o directrices",
    "modelo": "Modelo o marco de referencia",
    "procesos": "Procesos del ciclo de vida",
    "metodo": "Método de medición o evaluación",
    "especificacion": "Especificación técnica",
    "informe": "Informe técnico (informativo)",
}

# tipo: (cómo se lee desde el origen, cómo se lee desde el destino)
TIPOS_RELACION = {
    "desarrolla": ("Desarrolla", "Desarrollada por"),
    "amplia": ("Amplía", "Ampliada por"),
    "aplica": ("Aplica", "Aplicada por"),
    "se_apoya_en": ("Se apoya en", "Sirve de base a"),
    "complementa": ("Complementa a", "Complementada por"),
    "vocabulario_de": ("Aporta el vocabulario de", "Usa el vocabulario de"),
    "guia_de": ("Guía de implantación de", "Tiene como guía de implantación"),
    "mide": ("Mide", "Medida por"),
    "evalua": ("Evalúa", "Evaluada por"),
    "metodologia_de": ("Metodología de evaluación de", "Se evalúa con la metodología de"),
    "metodo_conforme_a": ("Método conforme a", "Marco de los métodos"),
    "prueba": ("Pruebas de conformidad de", "Se prueba con"),
    "encapsula": ("Encapsula los datos de", "Sus datos se encapsulan con"),
    "audita": ("Directrices para auditar", "Se audita con"),
    "sustituye": ("Sustituye a", "Sustituida por"),
    "se_situa_en": ("Se sitúa en el modelo de", "Modelo de referencia de"),
}


class ConfigError(ValueError):
    def __init__(self, errores: list[str]):
        self.errores = errores
        super().__init__("normas.yaml no es válido:\n  - " + "\n  - ".join(errores))


@dataclass(frozen=True)
class Familia:
    id: str
    nombre: str
    corto: str
    categoria: str | None = None  # tema en el que se muestra en «Por temas»
    descripcion: str | None = None
    temas: tuple[int, ...] = ()


@dataclass(frozen=True)
class Area:
    """Bloque del mapa de estudio; agrupa varias categorías."""
    id: str
    nombre: str


@dataclass(frozen=True)
class Categoria:
    id: str
    nombre: str
    area: str | None = None


@dataclass(frozen=True)
class TemaTemario:
    numero: int
    titulo: str
    relacion: str | None = None
    asociacion: tuple[tuple[str, str], ...] = ()  # (código, idea), de lo general a lo específico


@dataclass(frozen=True)
class Relacion:
    tipo: str
    norma: str  # código de la norma destino


@dataclass(frozen=True)
class Norma:
    codigo: str
    nombre: str
    alcance: str
    categoria: str
    numero: str
    parte: str | None
    resumen: str | None = None
    concepto: str | None = None
    pregunta: str | None = None
    descripcion: str | None = None
    ejemplo: str | None = None
    familia: str | None = None
    partes_citadas: tuple[str, ...] = ()
    edicion_citada: str | None = None
    une: str | None = None
    contexto: str | None = None
    revisar: str | None = None
    naturaleza: str | None = None
    certificable: bool = False
    temas: tuple[int, ...] = ()
    claves: tuple[str, ...] = ()
    relaciones: tuple[Relacion, ...] = ()
    partes_descripcion: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Config:
    familias: dict[str, Familia]
    normas: list[Norma] = field(default_factory=list)
    categorias: dict[str, Categoria] = field(default_factory=dict)
    temario: dict[int, TemaTemario] = field(default_factory=dict)
    areas: dict[str, Area] = field(default_factory=dict)


def cargar(ruta: str | Path, ruta_temario: str | Path | None = None) -> Config:
    """Carga normas.yaml y, si existe, el temario.yaml de la misma carpeta."""
    ruta = Path(ruta)
    with open(ruta, encoding="utf-8") as f:
        datos = yaml.safe_load(f) or {}
    ruta_temario = Path(ruta_temario) if ruta_temario else ruta.with_name("temario.yaml")
    if ruta_temario.exists():
        with open(ruta_temario, encoding="utf-8") as f:
            datos["temario"] = (yaml.safe_load(f) or {}).get("temas") or []
    return validar(datos)


def _temas(valor, donde: str, temario: dict, errores: list[str]) -> tuple[int, ...]:
    if valor is None:
        return ()
    if not isinstance(valor, list) or not all(isinstance(t, int) for t in valor):
        errores.append(f"{donde}: temas debe ser una lista de números")
        return ()
    if temario:
        for t in valor:
            if t not in temario:
                errores.append(f"{donde}: el tema {t} no está en temario.yaml")
    return tuple(valor)


def validar(datos: dict) -> Config:
    errores: list[str] = []

    temario: dict[int, TemaTemario] = {}
    for i, t in enumerate(datos.get("temario") or []):
        if not isinstance(t.get("numero"), int) or not t.get("titulo"):
            errores.append(f"temario[{i}]: faltan 'numero' o 'titulo'")
            continue
        asociacion = tuple(
            (a["norma"], a["idea"]) for a in t.get("asociacion") or [] if a.get("norma") and a.get("idea")
        )
        if len(asociacion) != len(t.get("asociacion") or []):
            errores.append(f"tema {t['numero']}: cada paso de 'asociacion' necesita 'norma' e 'idea'")
        temario[t["numero"]] = TemaTemario(t["numero"], t["titulo"], t.get("relacion"), asociacion)

    areas: dict[str, Area] = {}
    for i, a in enumerate(datos.get("areas") or []):
        if not a.get("id") or not a.get("nombre"):
            errores.append(f"areas[{i}]: faltan 'id' o 'nombre'")
            continue
        areas[a["id"]] = Area(a["id"], a["nombre"])

    categorias: dict[str, Categoria] = {}
    for i, cat in enumerate(datos.get("categorias") or []):
        if not cat.get("id") or not cat.get("nombre"):
            errores.append(f"categorias[{i}]: faltan 'id' o 'nombre'")
            continue
        if cat["id"] in categorias:
            errores.append(f"categoría duplicada: {cat['id']}")
        if areas and cat.get("area") not in areas:
            errores.append(f"categoría {cat['id']}: área '{cat.get('area')}' no existe")
        categorias[cat["id"]] = Categoria(cat["id"], cat["nombre"], cat.get("area"))

    familias: dict[str, Familia] = {}
    for i, fam in enumerate(datos.get("familias") or []):
        if not fam.get("id") or not fam.get("nombre"):
            errores.append(f"familias[{i}]: faltan 'id' o 'nombre'")
            continue
        if fam["id"] in familias:
            errores.append(f"familia duplicada: {fam['id']}")
        if fam.get("categoria") and categorias and fam["categoria"] not in categorias:
            errores.append(f"familia {fam['id']}: categoría '{fam['categoria']}' no existe")
        familias[fam["id"]] = Familia(
            fam["id"], fam["nombre"], fam.get("corto") or fam["nombre"],
            fam.get("categoria"), fam.get("descripcion"),
            _temas(fam.get("temas"), f"familia {fam['id']}", temario, errores),
        )

    normas: list[Norma] = []
    vistos: set[str] = set()
    for i, n in enumerate(datos.get("normas") or []):
        donde = f"normas[{i}] ({n.get('codigo', '?')})"
        for campo in ("codigo", "nombre", "alcance", "categoria"):
            if not n.get(campo):
                errores.append(f"{donde}: falta '{campo}'")
        extra = set(n) - CAMPOS
        if extra:
            errores.append(f"{donde}: campos desconocidos {sorted(extra)}")
        if n.get("alcance") and n["alcance"] not in ALCANCES:
            errores.append(f"{donde}: alcance '{n['alcance']}' no es norma|serie")
        if n.get("categoria") and categorias and n["categoria"] not in categorias:
            errores.append(f"{donde}: categoría '{n['categoria']}' no existe")
        if n.get("familia") and n["familia"] not in familias:
            errores.append(f"{donde}: familia '{n['familia']}' no existe")
        if n.get("naturaleza") and n["naturaleza"] not in NATURALEZAS:
            errores.append(f"{donde}: naturaleza '{n['naturaleza']}' no es válida")
        ed = n.get("edicion_citada")
        if ed is not None and not re.fullmatch(r"\d{4}", str(ed)):
            errores.append(f"{donde}: edicion_citada debe ser un año entre comillas, p. ej. \"2015\"")
        partes = n.get("partes_citadas") or []
        if not isinstance(partes, list) or not all(isinstance(p, str) for p in partes):
            errores.append(f"{donde}: partes_citadas debe ser una lista de textos")
        relaciones = []
        for r in n.get("relaciones") or []:
            if not isinstance(r, dict) or r.get("tipo") not in TIPOS_RELACION or not r.get("norma"):
                errores.append(f"{donde}: relación no válida {r!r}")
                continue
            relaciones.append(Relacion(r["tipo"], r["norma"]))
        partes_desc = n.get("partes_descripcion") or {}
        if not isinstance(partes_desc, dict):
            errores.append(f"{donde}: partes_descripcion debe ser un diccionario parte → texto")
            partes_desc = {}
        codigo = n.get("codigo")
        if not codigo:
            continue
        if codigo in vistos:
            errores.append(f"{donde}: código duplicado")
        vistos.add(codigo)
        try:
            ref = parse(codigo)
        except ReferenciaInvalida:
            errores.append(f"{donde}: código no reconocible")
            continue
        if ref.anio or ref.suplemento or ref.borrador:
            errores.append(f"{donde}: el código no debe llevar año, suplemento ni etapa de borrador")
        normas.append(Norma(
            codigo=codigo,
            nombre=n.get("nombre", ""),
            resumen=n.get("resumen"),
            concepto=n.get("concepto"),
            pregunta=n.get("pregunta"),
            descripcion=n.get("descripcion"),
            ejemplo=n.get("ejemplo"),
            alcance=n.get("alcance", ""),
            categoria=n.get("categoria", ""),
            numero=ref.numero,
            parte=ref.parte,
            familia=n.get("familia"),
            partes_citadas=tuple(partes) if isinstance(partes, list) else (),
            edicion_citada=str(ed) if ed is not None else None,
            une=n.get("une"),
            contexto=n.get("contexto"),
            revisar=n.get("revisar"),
            naturaleza=n.get("naturaleza"),
            certificable=bool(n.get("certificable")),
            temas=_temas(n.get("temas"), donde, temario, errores),
            claves=tuple(n.get("claves") or ()),
            relaciones=tuple(relaciones),
            partes_descripcion=tuple((str(k), v) for k, v in partes_desc.items()),
        ))

    for norma in normas:
        for r in norma.relaciones:
            if r.norma not in vistos:
                errores.append(f"{norma.codigo}: la relación apunta a '{r.norma}', que no está en normas.yaml")
    for tema in temario.values():
        for codigo, _ in tema.asociacion:
            if codigo not in vistos:
                errores.append(f"tema {tema.numero}: la asociación cita '{codigo}', que no está en normas.yaml")

    if errores:
        raise ConfigError(errores)
    return Config(familias=familias, normas=normas, categorias=categorias, temario=temario, areas=areas)
