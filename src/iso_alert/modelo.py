"""Estados que muestra la web y su relación con las etapas ISO.

Las etapas llegan como entero sin puntuación: ``6060`` es 60.60.
Referencia: https://www.iso.org/stage-codes.html
"""

from __future__ import annotations

from enum import StrEnum


class Estado(StrEnum):
    VIGENTE = "vigente"
    EN_REVISION = "en_revision"
    SUSTITUIDA = "sustituida"
    ANULADA = "anulada"
    NO_PUBLICADA = "no_publicada"
    NO_ENCONTRADA = "no_encontrada"

    @property
    def etiqueta(self) -> str:
        return ETIQUETAS[self]


class Subestado(StrEnum):
    REVISION_PERIODICA = "revision_periodica"
    ANULACION_PROPUESTA = "anulacion_propuesta"

    @property
    def etiqueta(self) -> str:
        return ETIQUETAS[self]


ETIQUETAS: dict[StrEnum, str] = {
    Estado.VIGENTE: "Vigente",
    Estado.EN_REVISION: "En revisión",
    Estado.SUSTITUIDA: "Sustituida",
    Estado.ANULADA: "Anulada",
    Estado.NO_PUBLICADA: "No publicada",
    Estado.NO_ENCONTRADA: "No encontrada",
    Subestado.REVISION_PERIODICA: "Revisión periódica",
    Subestado.ANULACION_PROPUESTA: "Anulación propuesta",
}

# Prioridad para agregar el estado de una serie: gana el primero de la lista.
PRIORIDAD_SERIE = [Estado.EN_REVISION, Estado.VIGENTE, Estado.SUSTITUIDA, Estado.ANULADA, Estado.NO_PUBLICADA]

ANULADA = 9599
PUBLICADA = 6060
EN_PUBLICACION = 6000
REVISION_PERIODICA = {9020, 9060}
SE_REVISARA = 9092
ANULACION_PROPUESTA = {9099, 9520, 9560}


def etapa_txt(etapa: int) -> str:
    return f"{etapa // 100:02d}.{etapa % 100:02d}"


def cancelado(etapa: int) -> bool:
    """xx.98: proyecto cancelado."""
    return etapa % 100 == 98


def publicado(etapa: int) -> bool:
    """Publicado y no anulado (60.60 a 95.60)."""
    return PUBLICADA <= etapa < ANULADA


def proyecto_activo(etapa: int) -> bool:
    """En elaboración (00.00 a 60.00) y no cancelado."""
    return etapa < PUBLICADA and not cancelado(etapa)


def estado_publicado(etapa: int) -> tuple[Estado, Subestado | None]:
    """Estado de un entregable publicado, sin mirar si tiene proyectos de revisión."""
    if etapa == SE_REVISARA:
        return Estado.EN_REVISION, None
    if etapa in REVISION_PERIODICA:
        return Estado.VIGENTE, Subestado.REVISION_PERIODICA
    if etapa in ANULACION_PROPUESTA:
        return Estado.VIGENTE, Subestado.ANULACION_PROPUESTA
    return Estado.VIGENTE, None
