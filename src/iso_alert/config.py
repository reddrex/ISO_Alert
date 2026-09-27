"""Carga y validación de normas.yaml."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .referencias import ReferenciaInvalida, parse

ALCANCES = {"norma", "serie"}
CAMPOS = {
    "codigo", "nombre", "alcance", "familia", "partes_citadas", "edicion_citada",
    "une", "categoria", "contexto", "revisar",
}


class ConfigError(ValueError):
    def __init__(self, errores: list[str]):
        self.errores = errores
        super().__init__("normas.yaml no es válido:\n  - " + "\n  - ".join(errores))


@dataclass(frozen=True)
class Familia:
    id: str
    nombre: str


@dataclass(frozen=True)
class Norma:
    codigo: str
    nombre: str
    alcance: str
    categoria: str
    numero: str
    parte: str | None
    familia: str | None = None
    partes_citadas: tuple[str, ...] = ()
    edicion_citada: str | None = None
    une: str | None = None
    contexto: str | None = None
    revisar: str | None = None


@dataclass(frozen=True)
class Config:
    familias: dict[str, Familia]
    normas: list[Norma] = field(default_factory=list)


def cargar(ruta: str | Path) -> Config:
    with open(ruta, encoding="utf-8") as f:
        datos = yaml.safe_load(f) or {}
    return validar(datos)


def validar(datos: dict) -> Config:
    errores: list[str] = []
    familias: dict[str, Familia] = {}
    for i, fam in enumerate(datos.get("familias") or []):
        if not fam.get("id") or not fam.get("nombre"):
            errores.append(f"familias[{i}]: faltan 'id' o 'nombre'")
            continue
        if fam["id"] in familias:
            errores.append(f"familia duplicada: {fam['id']}")
        familias[fam["id"]] = Familia(fam["id"], fam["nombre"])

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
        if n.get("familia") and n["familia"] not in familias:
            errores.append(f"{donde}: familia '{n['familia']}' no existe")
        ed = n.get("edicion_citada")
        if ed is not None and not re.fullmatch(r"\d{4}", str(ed)):
            errores.append(f"{donde}: edicion_citada debe ser un año entre comillas, p. ej. \"2015\"")
        partes = n.get("partes_citadas") or []
        if not isinstance(partes, list) or not all(isinstance(p, str) for p in partes):
            errores.append(f"{donde}: partes_citadas debe ser una lista de textos")
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
        ))

    if errores:
        raise ConfigError(errores)
    return Config(familias=familias, normas=normas)
