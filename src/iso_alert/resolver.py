"""De una entrada de normas.yaml a sus entregables ISO y su estado.

Reglas (ver PLAN.md §4):
- Se empareja por (número, parte), nunca por prefijo ni tipo.
- ``replacedBy`` se rellena en cuanto hay un proyecto de revisión; una norma
  solo está *sustituida* si su sustituto está publicado.
- Las sustituciones pueden cruzar números (9126-1 → 25010), así que se sigue
  la cadena ``replacedBy`` por ``id``.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field

from . import modelo as m
from .config import Config, Norma
from .modelo import Estado, Subestado
from .referencias import Referencia, parte_citada, partes_en, try_parse


@dataclass(frozen=True)
class Entregable:
    id: int
    referencia: str
    ref: Referencia
    tipo: str
    suplemento: bool
    etapa: int
    edicion: int | None
    publicacion: str | None
    titulo_en: str | None
    comite: str | None
    replaces: tuple[int, ...]
    replaced_by: tuple[int, ...]

    @property
    def anio(self) -> str | None:
        return self.ref.anio

    @property
    def orden(self) -> tuple:
        return (self.publicacion or "", self.edicion or 0, self.id)

    @classmethod
    def desde_registro(cls, r: dict, ref: Referencia) -> Entregable:
        return cls(
            id=r["id"],
            referencia=r["reference"],
            ref=ref,
            tipo=r["deliverableType"],
            suplemento=bool(r["supplementType"] or ref.suplemento),
            etapa=r["currentStage"],
            edicion=r["edition"],
            publicacion=r["publicationDate"],
            titulo_en=(r["title"] or {}).get("en"),
            comite=r["ownerCommittee"],
            replaces=tuple(r["replaces"] or ()),
            replaced_by=tuple(r["replacedBy"] or ()),
        )


class Indice:
    """Índice del dataset en memoria por id y por número."""

    def __init__(self, registros: Iterable[dict]):
        self.por_id: dict[int, Entregable] = {}
        self.por_numero: dict[str, list[Entregable]] = defaultdict(list)
        self.no_reconocidas = 0
        for r in registros:
            ref = try_parse(r["reference"])
            if ref is None:
                self.no_reconocidas += 1
                continue
            e = Entregable.desde_registro(r, ref)
            self.por_id[e.id] = e
            self.por_numero[e.ref.numero].append(e)

    def __len__(self) -> int:
        return len(self.por_id)

    def seguir_sustitucion(self, e: Entregable, max_saltos: int = 10) -> list[Entregable]:
        """Entregables publicados que sustituyen a ``e``, siguiendo la cadena de anulados."""
        resultado: dict[int, Entregable] = {}
        visto = {e.id}
        frontera = list(e.replaced_by)
        for _ in range(max_saltos):
            siguiente = []
            for i in frontera:
                if i in visto or i not in self.por_id:
                    continue
                visto.add(i)
                x = self.por_id[i]
                if m.publicado(x.etapa) and not x.suplemento:
                    resultado[x.id] = x
                elif x.etapa == m.ANULADA:
                    siguiente.extend(x.replaced_by)
            if not siguiente:
                break
            frontera = siguiente
        return sorted(resultado.values(), key=lambda x: x.orden)


@dataclass
class Linea:
    """Una línea de ediciones con la misma (número, parte)."""

    parte: str | None
    estado: Estado
    subestado: Subestado | None
    vigente: Entregable | None
    proyectos: list[Entregable]
    anteriores: list[Entregable]  # ediciones anuladas, de más antigua a más reciente
    suplementos: list[Entregable]  # Amd/Cor publicados de la edición vigente
    sustituida_por: list[Entregable]
    citada: bool = False

    @property
    def ultima(self) -> Entregable | None:
        return self.vigente or (self.anteriores[-1] if self.anteriores else None)

    @property
    def todas(self) -> list[Entregable]:
        return self.anteriores + ([self.vigente] if self.vigente else []) + self.proyectos


@dataclass
class Resultado:
    norma: Norma
    estado: Estado
    subestado: Subestado | None
    lineas: list[Linea]
    relevantes: list[Linea]
    recuento: Counter = field(default_factory=Counter)
    edicion_citada: dict | None = None
    codigo_actual: str | None = None  # si difiere del de normas.yaml
    partes_no_encontradas: list[str] = field(default_factory=list)
    notas: list[str] = field(default_factory=list)
    entregables: list[Entregable] = field(default_factory=list)  # todos los del alcance, suplementos incluidos


def _linea(indice: Indice, parte: str | None, grupo: list[Entregable], supl: list[Entregable]) -> Linea:
    grupo = sorted(grupo, key=lambda e: e.orden)
    publicados = [e for e in grupo if m.publicado(e.etapa)]
    anulados = [e for e in grupo if e.etapa == m.ANULADA]
    vigente = publicados[-1] if publicados else None

    proyectos = {e.id: e for e in grupo if m.proyecto_activo(e.etapa)}
    if vigente:
        for i in vigente.replaced_by:
            x = indice.por_id.get(i)
            if x and not x.suplemento and m.proyecto_activo(x.etapa):
                proyectos[x.id] = x
    proyectos_l = sorted(proyectos.values(), key=lambda e: e.orden)

    sustituida_por: list[Entregable] = []
    if vigente:
        estado, sub = m.estado_publicado(vigente.etapa)
        if proyectos_l and estado == Estado.VIGENTE and sub != Subestado.ANULACION_PROPUESTA:
            estado, sub = Estado.EN_REVISION, None
    elif anulados:
        sustituida_por = indice.seguir_sustitucion(anulados[-1])
        estado, sub = (Estado.SUSTITUIDA if sustituida_por else Estado.ANULADA), None
    else:
        estado, sub = Estado.NO_PUBLICADA, None

    suplementos = []
    if vigente:
        suplementos = sorted(
            (s for s in supl if s.ref.anio == vigente.anio and m.publicado(s.etapa)),
            key=lambda e: e.orden,
        )
    return Linea(parte, estado, sub, vigente, proyectos_l, anulados, suplementos, sustituida_por)


def resolver(norma: Norma, indice: Indice) -> Resultado:
    todos = indice.por_numero.get(norma.numero, [])
    principales = [e for e in todos if not e.suplemento]
    suplementos = [e for e in todos if e.suplemento]

    if norma.alcance == "norma":
        en_alcance = lambda p: p == norma.parte  # noqa: E731
    elif norma.parte is None:
        en_alcance = lambda p: True  # noqa: E731
    else:
        en_alcance = lambda p: p is not None and (p == norma.parte or p.startswith(norma.parte + "-"))  # noqa: E731

    grupos: dict[str | None, list[Entregable]] = defaultdict(list)
    supl_por_parte: dict[str | None, list[Entregable]] = defaultdict(list)
    for e in principales:
        if en_alcance(e.ref.parte):
            grupos[e.ref.parte].append(e)
    for s in suplementos:
        if en_alcance(s.ref.parte):
            supl_por_parte[s.ref.parte].append(s)

    lineas = [_linea(indice, p, g, supl_por_parte[p]) for p, g in grupos.items()]
    lineas.sort(key=lambda l: _orden_parte(l.parte))

    res = Resultado(norma, Estado.NO_ENCONTRADA, None, lineas, [])
    res.entregables = sorted(
        [e for g in grupos.values() for e in g] + [s for ss in supl_por_parte.values() for s in ss],
        key=lambda e: e.id,
    )
    if not todos:
        res.notas.append(f"No hay ningún registro con el número {norma.numero} en el dataset ISO.")
        return res
    if not lineas:
        partes = sorted({e.ref.parte for e in principales if e.ref.parte}, key=_orden_parte)
        if norma.alcance == "norma" and partes:
            res.notas.append(
                f"Solo existen partes ({', '.join(partes[:8])}{'…' if len(partes) > 8 else ''}); "
                "¿debería ser alcance: serie?"
            )
        return res

    # Partes relevantes: las citadas, o todas si no se citan.
    if norma.alcance == "serie" and norma.partes_citadas:
        for l in lineas:
            l.citada = parte_citada(l.parte, list(norma.partes_citadas))
        relevantes = [l for l in lineas if l.citada]
        for c in norma.partes_citadas:
            exacta, desde, hasta = partes_en(c)
            if not any(parte_citada(l.parte, [c]) for l in lineas):
                res.partes_no_encontradas.append(c)
            # 8802-1 frente a 8802-1Q, 8802-1X…: la parte citada puede ser un grupo.
            if exacta:
                hermanas = [
                    l.parte for l in lineas
                    if l.parte and l.parte != exacta and l.parte.startswith(exacta)
                    and l.parte[len(exacta)].isalpha() and l.vigente
                ]
                if hermanas:
                    res.notas.append(
                        f"Además de la parte {exacta} hay partes vigentes {', '.join(hermanas[:8])}"
                        f"{'…' if len(hermanas) > 8 else ''}: ¿se refiere el temario a ellas?"
                    )
        if not relevantes:
            relevantes = lineas
    else:
        for l in lineas:
            l.citada = True
        relevantes = lineas
    res.relevantes = relevantes

    # Estado agregado.
    res.recuento = Counter(l.estado for l in relevantes)
    if len(relevantes) == 1:
        res.estado, res.subestado = relevantes[0].estado, relevantes[0].subestado
    else:
        res.estado = next(e for e in m.PRIORIDAD_SERIE if res.recuento[e])

    if res.estado == Estado.NO_PUBLICADA:
        proyectos = sorted((e for l in relevantes for e in l.todas + _cancelados(l, principales)), key=lambda e: e.orden)
        res.notas.append("Nunca se ha publicado. Proyectos: " + ", ".join(
            f"{e.referencia} ({'cancelado' if m.cancelado(e.etapa) else 'en curso'}, {m.etapa_txt(e.etapa)})"
            for e in dict.fromkeys(proyectos)
        ))

    res.edicion_citada = _edicion_citada(norma, relevantes)
    res.codigo_actual = _codigo_actual(norma, relevantes)
    return res


def _cancelados(linea: Linea, principales: list[Entregable]) -> list[Entregable]:
    return [e for e in principales if e.ref.parte == linea.parte and m.cancelado(e.etapa)]


def _orden_parte(parte: str | None) -> tuple:
    if parte is None:
        return ()
    # Orden natural: 1, 1Q, 1X, 2, 10 (no 1, 10, 1Q, 2).
    claves = []
    for t in parte.split("-"):
        mt = re.match(r"(\d*)(.*)", t)
        claves.append((int(mt[1]) if mt[1] else -1, mt[2]))
    return tuple(claves)


def _edicion_citada(norma: Norma, relevantes: list[Linea]) -> dict | None:
    anio = norma.edicion_citada
    if not anio:
        return None
    vigentes = sorted({l.vigente.anio for l in relevantes if l.vigente and l.vigente.anio})
    existentes = {e.anio for l in relevantes for e in l.anteriores + ([l.vigente] if l.vigente else [])}
    if anio in vigentes:
        resultado = "vigente"
    elif anio in existentes:
        resultado = "superada"
    else:
        resultado = "no_existe"
    return {"anio": anio, "resultado": resultado, "vigentes": vigentes}


def _codigo_actual(norma: Norma, relevantes: list[Linea]) -> str | None:
    """Código actual si el prefijo o el tipo han cambiado respecto a normas.yaml."""
    vigentes = sorted((l.vigente for l in relevantes if l.vigente), key=lambda e: e.orden)
    if not vigentes:
        return None
    actual = vigentes[-1].ref
    original = try_parse(norma.codigo)
    if norma.alcance == "norma":
        return actual.codigo_sin_anio if actual.codigo_sin_anio != norma.codigo else None
    # En series, las partes pueden ser TR o TS y mezclar organismos (31700-1 es ISO,
    # 31700-2 es ISO/IEC): solo se avisa si ninguna parte vigente conserva el original.
    organismos = {e.ref.organismos for e in vigentes}
    if original and original.organismos not in organismos:
        return f"{'/'.join(actual.organismos)} {norma.numero}"
    return None


def resolver_todo(config: Config, indice: Indice) -> list[Resultado]:
    return [resolver(n, indice) for n in config.normas]
