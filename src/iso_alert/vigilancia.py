"""Detección de cambios entre dos data/estado.json (PLAN.md §5 y §9).

El diff trabaja sobre la vista plana ``entregables`` (por id ISO). Cada cambio
es un evento con un id determinista, así que repetir una ejecución no duplica
nada en el historial ni en los avisos.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field

from . import modelo as m
from .config import Config
from .fuentes.iso import FuenteError
from .referencias import parte_citada

# Tipos de cambio (comunes a ISO y UNE) y su texto en la web.
TIPOS = {
    "edicion_nueva": "Edición nueva",
    "modificacion_publicada": "Modificación publicada",
    "anulacion": "Anulación",
    "parte_nueva": "Parte nueva",
    "revision_iniciada": "Revisión iniciada",
    "proyecto_avanza": "Proyecto de revisión avanza",
    "proyecto_cancelado": "Proyecto cancelado",
    "publicacion_inminente": "Publicación inminente",
    "revision_periodica": "Revisión periódica",
    "confirmada": "Confirmada",
    "anulacion_propuesta": "Anulación propuesta",
    "alta_vigilancia": "Empieza a vigilarse",
}
# Tipos que generan aviso (Issue y feed general), siempre que afecten a partes citadas.
NOTIFICABLES = {"edicion_nueva", "modificacion_publicada", "anulacion"}


@dataclass
class Evento:
    id: str
    tipo: str
    normas: list[str]
    resumen: str
    notificable: bool
    detectado: str  # fecha de detección (AAAA-MM-DD)
    dato_fecha: str | None  # fecha del dataset ISO
    fuente: str = "iso"
    entregable: dict | None = None  # {id, referencia}
    sustituye: list[dict] = field(default_factory=list)
    etapa_anterior: int | None = None
    etapa_nueva: int | None = None
    issue: int | None = None

    @property
    def etiqueta(self) -> str:
        return TIPOS[self.tipo]

    def a_dict(self) -> dict:
        return asdict(self)


def _id(*partes) -> str:
    return hashlib.sha256("|".join(str(p) for p in partes).encode()).hexdigest()[:16]


def _tipo_por_etapa(antes: int | None, despues: int, e: dict, entregables: dict) -> str | None:
    """Tipo de cambio para un entregable que aparece (antes=None) o cambia de etapa."""
    if antes == despues:
        return None
    if m.cancelado(despues):
        return "proyecto_cancelado" if antes is not None and m.proyecto_activo(antes) else None
    if m.proyecto_activo(despues):
        if despues == m.EN_PUBLICACION:
            return "publicacion_inminente"
        return "revision_iniciada" if antes is None else "proyecto_avanza"
    if despues == m.ANULADA:
        # Si ya hay un sustituto publicado, la edición nueva es el aviso; esto no.
        sustitutos = [entregables.get(str(i)) for i in e["replaced_by"]]
        if any(s and m.publicado(s["etapa"]) for s in sustitutos):
            return None
        return "anulacion"
    if m.publicado(despues) and (antes is None or not m.publicado(antes)):
        if e["suplemento"]:
            return "modificacion_publicada"
        return "edicion_nueva" if e["replaces"] else "parte_nueva"
    if despues == m.SE_REVISARA:
        return "revision_iniciada"
    if despues == 9093:
        return "confirmada"
    if despues in m.REVISION_PERIODICA:
        return "revision_periodica"
    if despues in m.ANULACION_PROPUESTA:
        return "anulacion_propuesta"
    return None


def _resumen(tipo: str, e: dict, sustituye: list[dict], despues: int) -> str:
    ref = e["referencia"]
    if tipo == "edicion_nueva":
        previas = ", ".join(s["referencia"] for s in sustituye if not s.get("suplemento"))
        if not previas:
            return f"ISO publica {ref}."
        con_modificaciones = any(s.get("suplemento") for s in sustituye)
        return f"ISO publica {ref}, que sustituye a {previas}" + (" y sus modificaciones." if con_modificaciones else ".")
    if tipo == "modificacion_publicada":
        return f"ISO publica la modificación {ref}."
    if tipo == "anulacion":
        return f"ISO anula {ref} sin sustituirla por otra edición."
    if tipo == "parte_nueva":
        return f"ISO publica una parte nueva de la serie: {ref}."
    if tipo in ("revision_iniciada", "proyecto_avanza", "publicacion_inminente"):
        if m.proyecto_activo(despues):
            return f"El proyecto {ref} está en {m.fase_proyecto(despues)}."
        return f"ISO ha decidido revisar {ref}."
    if tipo == "proyecto_cancelado":
        return f"ISO cancela el proyecto {ref}."
    if tipo == "revision_periodica":
        return f"{ref} entra en revisión periódica ({m.etapa_txt(despues)})."
    if tipo == "confirmada":
        return f"ISO confirma {ref} sin cambios tras su revisión periódica."
    if tipo == "anulacion_propuesta":
        return f"Se ha propuesto anular {ref} ({m.etapa_txt(despues)})."
    return ref


def _notificable(tipo: str, e: dict, config: Config) -> bool:
    """Avisa de ediciones, modificaciones y anulaciones de normas enteras o partes citadas.

    Las partes nuevas solo avisan en series sin partes citadas (PLAN.md §9, decisión 1).
    """
    if tipo not in NOTIFICABLES and tipo != "parte_nueva":
        return False
    por_codigo = {n.codigo: n for n in config.normas}
    for codigo in e["normas"]:
        n = por_codigo.get(codigo)
        if n is None or n.numero != e["numero"]:
            continue
        if tipo == "parte_nueva":
            if n.alcance == "serie" and not n.partes_citadas:
                return True
        elif n.alcance == "norma" or not n.partes_citadas or parte_citada(e["parte"], list(n.partes_citadas)):
            return True
    return False


def comparar(anterior: dict, nuevo: dict, config: Config, detectado: str) -> list[Evento]:
    """Eventos entre dos estados. Lanza FuenteError si desaparecen entregables vigilados."""
    viejos, nuevos = anterior["entregables"], nuevo["entregables"]
    normas_antes = set(anterior["normas"])
    vigiladas = {n.codigo for n in config.normas}
    numero_de = {n.codigo: n.numero for n in config.normas}
    dato = ((nuevo["fuentes"].get("iso") or {}).get("last_modified") or "")[:10] or None
    eventos: list[Evento] = []

    desaparecidos = [
        i for i, e in viejos.items()
        if i not in nuevos and set(e["normas"]) & vigiladas
    ]
    if desaparecidos:
        muestra = ", ".join(viejos[i]["referencia"] for i in desaparecidos[:5])
        raise FuenteError(
            f"{len(desaparecidos)} entregables vigilados han desaparecido del dataset ({muestra}…); "
            "ISO no borra registros, así que probablemente ha cambiado el formato"
        )

    for codigo in sorted(vigiladas - normas_antes):
        eventos.append(Evento(
            id=_id("iso", "alta_vigilancia", codigo),
            tipo="alta_vigilancia",
            normas=[codigo],
            resumen=f"{codigo} se añade a la lista de normas vigiladas.",
            notificable=False,
            detectado=detectado,
            dato_fecha=dato,
        ))

    for i, e in nuevos.items():
        if not set(e["normas"]) & normas_antes:
            continue  # norma recién añadida: su alta ya es el evento
        # Solo cuenta para las normas de su mismo número: 25010 está en el alcance de la 9126
        # como sustituta, pero sus cambios se avisan una sola vez, en la 25010.
        propias = [c for c in e["normas"] if numero_de.get(c) == e["numero"]]
        if not propias:
            continue
        antes = viejos[i]["etapa"] if i in viejos else None
        if antes is None and e["etapa"] == m.ANULADA:
            continue  # registro antiguo que entra ahora en el alcance, no un cambio
        tipo = _tipo_por_etapa(antes, e["etapa"], e, nuevos)
        if tipo is None:
            continue
        sustituye = [
            {"id": int(j), "referencia": nuevos[str(j)]["referencia"], "suplemento": nuevos[str(j)]["suplemento"]}
            for j in e["replaces"] if str(j) in nuevos
        ]
        eventos.append(Evento(
            id=_id("iso", tipo, i, e["etapa"]),
            tipo=tipo,
            normas=propias,
            resumen=_resumen(tipo, e, sustituye, e["etapa"]),
            notificable=_notificable(tipo, e, config),
            detectado=detectado,
            dato_fecha=dato,
            entregable={"id": int(i), "referencia": e["referencia"]},
            sustituye=sustituye,
            etapa_anterior=antes,
            etapa_nueva=e["etapa"],
        ))
    return sorted(eventos, key=lambda ev: (not ev.notificable, ev.normas, ev.id))


def registrar(historial: list[dict], eventos: list[Evento]) -> list[Evento]:
    """Añade al historial los eventos que no estaban. Devuelve los añadidos."""
    vistos = {h["id"] for h in historial}
    nuevos = [ev for ev in eventos if ev.id not in vistos]
    historial.extend(ev.a_dict() for ev in nuevos)
    historial.sort(key=lambda h: (h["detectado"], h["id"]), reverse=True)
    return nuevos
