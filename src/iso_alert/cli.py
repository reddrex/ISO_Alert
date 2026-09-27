"""Línea de órdenes.

    python -m iso_alert vigilar      # comprobación diaria: cambios, historial y avisos
    python -m iso_alert actualizar   # dataset ISO → data/estado.json y data/validacion.json
    python -m iso_alert web          # data/ → páginas generadas en docs/
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import avisos, estado, informe, vigilancia, web
from . import config as cfg
from .fuentes import iso
from .resolver import Indice

RAIZ = Path.cwd()
CACHE = RAIZ / ".cache" / "iso_deliverables_metadata.jsonl"
CACHE_META = CACHE.with_suffix(".meta.json")


def _obtener_dataset(args) -> tuple[Path, iso.Descarga]:
    if args.fichero:
        ruta = Path(args.fichero)
        return ruta, iso.Descarga(ruta, str(ruta), None, None, iso.sha256_de(ruta), ruta.stat().st_size)
    if args.sin_descarga and CACHE.exists():
        print(f"Usando {CACHE} (sin descargar)", file=sys.stderr)
        meta = json.loads(CACHE_META.read_text(encoding="utf-8")) if CACHE_META.exists() else {}
        return CACHE, iso.Descarga(
            CACHE, iso.URL, meta.get("last_modified"), meta.get("etag"),
            iso.sha256_de(CACHE), CACHE.stat().st_size,
        )
    print(f"Descargando {iso.URL}", file=sys.stderr)
    d = iso.descargar(CACHE)
    CACHE_META.write_text(json.dumps({"last_modified": d.last_modified, "etag": d.etag}), encoding="utf-8")
    print(f"  {d.bytes / 1e6:.1f} MB · Last-Modified {d.last_modified}", file=sys.stderr)
    return d.ruta, d


def _escribir_json(ruta: Path, datos: dict) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def actualizar(args) -> int:
    config = cfg.cargar(args.normas)
    ruta, descarga = _obtener_dataset(args)
    indice = Indice(iso.leer(ruta, minimo=args.minimo))
    datos_estado = estado.construir(config, indice, descarga)
    datos_validacion = informe.construir(config, indice, descarga)
    datos = Path(args.datos)
    _escribir_json(datos / "estado.json", datos_estado)
    _escribir_json(datos / "validacion.json", datos_validacion)

    r = datos_validacion["resumen"]
    print(f"{r['total']} normas · {r['por_estado']}")
    print(f"{r['con_sugerencias']} con sugerencias · {r['ediciones_superadas']} ediciones citadas superadas")
    print(f"{len(datos_estado['entregables'])} entregables vigilados → {datos / 'estado.json'}")
    return 0


def _escribir_si_cambia(ruta: Path, datos) -> bool:
    """Escribe solo si cambia algo más que la fecha de generación (evita commits vacíos)."""
    if isinstance(datos, dict) and ruta.exists():
        previo = json.loads(ruta.read_text(encoding="utf-8"))
        if {**previo, "generado": None} == {**datos, "generado": None}:
            return False
    _escribir_json(ruta, datos)
    return True


def _leer_json(ruta: Path, defecto):
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else defecto


def vigilar(args) -> int:
    """Comprobación diaria: datos ISO → cambios → historial → avisos → data/."""
    hoy = datetime.now(timezone.utc).date().isoformat()
    datos = Path(args.datos)
    cliente = None if args.simulacro else avisos.GitHub.desde_entorno()
    if cliente is None and not args.simulacro:
        print("Sin GITHUB_TOKEN/GITHUB_REPOSITORY: no se abrirán Issues (simulacro)", file=sys.stderr)
    ultima = {
        "ejecucion": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "run_url": os.environ.get("RUN_URL"),
    }

    config = cfg.cargar(args.normas)
    try:
        ruta, descarga = _obtener_dataset(args)
        indice = Indice(iso.leer(ruta, minimo=args.minimo))
        nuevo = estado.construir(config, indice, descarga)
        anterior = _leer_json(datos / "estado.json", {"entregables": {}, "normas": {}, "fuentes": {}})
        eventos = vigilancia.comparar(anterior, nuevo, config, hoy)
    except iso.FuenteError as e:
        ultima.update(resultado="error", error=str(e))
        _escribir_json(datos / "last_checked.json", ultima)
        if cliente:
            avisos.issue_de_estado(
                cliente, "fallo-fuente", "La comprobación diaria ha fallado",
                f"La descarga o la lectura de ISO Open Data ha fallado:\n\n```\n{e}\n```\n\n"
                f"Ejecución: {ultima['run_url'] or '—'}\n\nNo se ha registrado ningún cambio.",
                abierto=True,
            )
        raise

    historial = _leer_json(datos / "historial.json", [])
    nuevos = vigilancia.registrar(historial, eventos)
    notificables = [ev for ev in nuevos if ev.notificable]
    print(f"{len(nuevos)} cambios nuevos, {len(notificables)} con aviso")
    for ev in nuevos:
        print(f"  {'!' if ev.notificable else ' '} {ev.etiqueta}: {ev.resumen}")

    if cliente:
        try:
            numeros = avisos.publicar(nuevos, cliente, web.SITIO)
        except avisos.GuardaAntirruido as e:
            avisos.issue_de_estado(
                cliente, "revision-manual", "Demasiados cambios a la vez: revisar antes de avisar",
                f"{e}. No se ha abierto ningún aviso ni se ha guardado nada, por si es un fallo "
                "del análisis y no cambios reales.\n\n"
                + "\n".join(f"- {ev.etiqueta}: {ev.resumen}" for ev in notificables[:50]),
                abierto=True,
            )
            raise
        for h in historial:
            if h["id"] in numeros:
                h["issue"] = numeros[h["id"]]
        avisos.issue_de_estado(cliente, "fallo-fuente", "", "", abierto=False)
        avisos.issue_de_estado(cliente, "revision-manual", "", "", abierto=False)
        antiguedad = _dias_desde(descarga.last_modified, hoy)
        avisos.issue_de_estado(
            cliente, "fuente-desactualizada",
            f"ISO Open Data lleva {antiguedad} días sin actualizarse",
            f"El último fichero de ISO Open Data es del {(descarga.last_modified or '')[:10]}. "
            "La web sigue mostrando esos datos; los cambios posteriores se detectarán cuando ISO publique un fichero nuevo.",
            abierto=antiguedad is not None and antiguedad > DIAS_DESACTUALIZADA,
        )

    _escribir_si_cambia(datos / "estado.json", nuevo)
    _escribir_si_cambia(datos / "validacion.json", informe.construir(config, indice, descarga))
    if nuevos or not (datos / "historial.json").exists():
        _escribir_json(datos / "historial.json", historial)
    ultima.update(
        resultado="ok" if nuevos else "sin_cambios",
        iso={"last_modified": descarga.last_modified, "sha256": descarga.sha256},
        eventos_nuevos=len(nuevos),
        avisos=len(notificables),
    )
    _escribir_json(datos / "last_checked.json", ultima)
    return 0


DIAS_DESACTUALIZADA = 14


def _dias_desde(fecha_iso: str | None, hoy: str) -> int | None:
    if not fecha_iso:
        return None
    from datetime import date
    return (date.fromisoformat(hoy) - date.fromisoformat(fecha_iso[:10])).days


def generar_web(args) -> int:
    config = cfg.cargar(args.normas)
    datos = Path(args.datos)
    leer = lambda nombre: json.loads((datos / nombre).read_text(encoding="utf-8"))  # noqa: E731
    historial = _leer_json(datos / "historial.json", [])
    rutas = web.generar(leer("estado.json"), leer("validacion.json"), config, Path(args.docs), historial)
    carpetas = (web.FICHAS, web.FAMILIAS, web.TEMARIO, web.FEEDS)
    for ruta in rutas:
        if ruta.parent.name not in carpetas:
            print(f"→ {ruta}")
    for carpeta in carpetas:
        n = sum(1 for r in rutas if r.parent.name == carpeta)
        print(f"→ {n} páginas en {Path(args.docs) / carpeta}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="iso_alert", description="Vigilancia de normas ISO/UNE")
    sub = p.add_subparsers(dest="orden", required=True)

    a = sub.add_parser("actualizar", help="descarga el dataset ISO y calcula el estado de las normas")
    a.add_argument("--normas", default="normas.yaml")
    a.add_argument("--datos", default="data", help="carpeta de salida de estado.json y validacion.json")
    a.add_argument("--fichero", help="JSONL local en lugar de descargar")
    a.add_argument("--sin-descarga", action="store_true", help="reutiliza .cache/ si existe")
    a.add_argument("--minimo", type=int, default=iso.MIN_REGISTROS, help=argparse.SUPPRESS)
    a.set_defaults(func=actualizar)

    v = sub.add_parser("vigilar", help="comprobación diaria: detecta cambios, los registra y avisa")
    v.add_argument("--normas", default="normas.yaml")
    v.add_argument("--datos", default="data")
    v.add_argument("--fichero", help="JSONL local en lugar de descargar")
    v.add_argument("--sin-descarga", action="store_true", help="reutiliza .cache/ si existe")
    v.add_argument("--simulacro", action="store_true", help="no abre Issues aunque haya token")
    v.add_argument("--minimo", type=int, default=iso.MIN_REGISTROS, help=argparse.SUPPRESS)
    v.set_defaults(func=vigilar)

    w = sub.add_parser("web", help="genera las páginas del sitio a partir de data/")
    w.add_argument("--normas", default="normas.yaml")
    w.add_argument("--datos", default="data")
    w.add_argument("--docs", default="docs")
    w.set_defaults(func=generar_web)

    args = p.parse_args(argv)
    try:
        return args.func(args)
    except (cfg.ConfigError, iso.FuenteError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
