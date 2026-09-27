"""Parser de códigos de norma ISO/IEC.

Descompone referencias como ``ISO/IEC CD 29115.2``, ``ISO/DTR 26102`` o
``ISO 30301:2019/Amd 1:2024`` en sus partes. La clave para emparejar ediciones
es ``(numero, parte)``: el prefijo y el tipo cambian entre ediciones
(``ISO/IEC 15289`` → ``ISO/IEC/IEEE 15289``, ``ISO/TR 15801`` → ``ISO 15801``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Tipos de documento que aparecen en el código (IS no se escribe).
TIPOS = {"TR", "TS", "PAS", "R", "ISP", "IWA", "TTA", "Guide", "GUIDE", "DATA"}

# Etapas de borrador que preceden al número. Hay más variantes históricas
# (FCD, PDTR, FDAM…), así que se acepta cualquier sigla en mayúsculas.
BORRADORES = {"NP", "PWI", "AWI", "WD", "CD", "DIS", "FDIS", "PRF", "DTR", "DTS", "DPAS"}
_SIGLA_BORRADOR = re.compile(r"^[A-Z]{1,6}$")

# Suplementos: "/Amd 1:2024", "/CD Cor 1", "/DAmd 1", "/FDCor 1", "/PDAM 3".
_SUPLEMENTO = re.compile(r"/(?P<supl>[A-Z]* ?(?:Amd|Cor|Add|Suppl|Ext|DAM|AM)\b.*)$")
_NUMERO = re.compile(
    r"^(?P<numero>\d+)"
    r"(?P<parte>(?:-[0-9A-Za-z]+)*)"
    r"(?:\.(?P<iteracion>\d+))?"
    r"(?::(?P<anio>\d{4}))?$"
)


class ReferenciaInvalida(ValueError):
    pass


@dataclass(frozen=True)
class Referencia:
    original: str
    organismos: tuple[str, ...]
    borrador: str | None
    tipo: str  # IS, TR, TS…
    numero: str
    parte: str | None
    iteracion: int | None
    anio: str | None
    suplemento: str | None

    @property
    def clave(self) -> tuple[str, str | None]:
        return (self.numero, self.parte)

    @property
    def prefijo(self) -> str:
        """Prefijo publicado, p. ej. ``ISO/IEC`` o ``ISO/TR``."""
        org = "/".join(self.organismos)
        if not org:
            return self.tipo
        if self.tipo == "IS":
            return org
        sep = " " if len(self.organismos) > 1 else "/"
        return f"{org}{sep}{self.tipo}"

    @property
    def codigo_sin_anio(self) -> str:
        parte = f"-{self.parte}" if self.parte else ""
        return f"{self.prefijo} {self.numero}{parte}"


def _clasificar(codigo: str) -> tuple[str | None, str | None]:
    """Devuelve (borrador, tipo) para un token como ``CD``, ``TR`` o ``DTR``."""
    if codigo in TIPOS:
        return None, "Guide" if codigo == "GUIDE" else codigo
    for pre in ("FD", "PD", "D"):
        if codigo.startswith(pre) and codigo[len(pre):] in TIPOS:
            return codigo, _clasificar(codigo[len(pre):])[1]
    if codigo in BORRADORES or _SIGLA_BORRADOR.match(codigo):
        return codigo, None
    raise ReferenciaInvalida(codigo)


def parse(ref: str) -> Referencia:
    texto = ref.strip()
    suplemento = None
    m = _SUPLEMENTO.search(texto)
    if m:
        suplemento = m["supl"]
        texto = texto[: m.start()]

    tokens = texto.split()
    if not tokens:
        raise ReferenciaInvalida(ref)

    # Primer token: organismos y, a veces, códigos pegados con "/" (ISO/DTR, ISO/IEC/IEEE).
    # Los IWA se publican sin organismo delante ("IWA 1:2001", "NP IWA 7").
    organismos: list[str] = []
    codigos: list[str] = []
    resto = tokens
    if tokens[0].split("/")[0] in {"ISO", "IEC"}:
        for i, trozo in enumerate(tokens[0].split("/")):
            if i == 0 or (not codigos and trozo not in TIPOS and trozo not in BORRADORES):
                organismos.append(trozo)
            else:
                codigos.append(trozo)
        resto = tokens[1:]
    elif "IWA" not in tokens:
        raise ReferenciaInvalida(ref)

    resto = list(resto)
    while resto and not resto[0][0].isdigit():
        codigos.append(resto.pop(0))
    if len(resto) != 1:
        raise ReferenciaInvalida(ref)
    mn = _NUMERO.match(resto[0])
    if not mn:
        raise ReferenciaInvalida(ref)

    borrador = None
    tipo = "IS"
    for c in codigos:
        try:
            b, t = _clasificar(c)
        except ReferenciaInvalida:
            raise ReferenciaInvalida(ref) from None
        borrador = b or borrador
        tipo = t or tipo

    return Referencia(
        original=ref,
        organismos=tuple(organismos),
        borrador=borrador,
        tipo=tipo,
        numero=mn["numero"],
        parte=mn["parte"].lstrip("-") or None,
        iteracion=int(mn["iteracion"]) if mn["iteracion"] else None,
        anio=mn["anio"],
        suplemento=suplemento,
    )


def try_parse(ref: str) -> Referencia | None:
    try:
        return parse(ref)
    except ReferenciaInvalida:
        return None


def partes_en(citada: str) -> tuple[str | None, int | None, int | None]:
    """Interpreta una entrada de ``partes_citadas``.

    ``"1"`` → parte exacta; ``"TR 2"`` → parte 2; ``"100-150"`` → rango numérico.
    Devuelve (parte_exacta, desde, hasta).
    """
    valor = citada.split()[-1]
    m = re.fullmatch(r"(\d+)-(\d+)", valor)
    if m and int(m[1]) < int(m[2]):
        return None, int(m[1]), int(m[2])
    return valor, None, None


def parte_citada(parte: str | None, citadas: list[str]) -> bool:
    if parte is None:
        return False
    for c in citadas:
        exacta, desde, hasta = partes_en(c)
        if exacta is not None and parte == exacta:
            return True
        if desde is not None and parte.isdigit() and desde <= int(parte) <= hasta:
            return True
    return False
