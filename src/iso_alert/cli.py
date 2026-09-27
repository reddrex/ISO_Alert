"""Línea de órdenes.

    python -m iso_alert actualizar   # dataset ISO → data/estado.json y data/validacion.json
    python -m iso_alert web          # data/ → páginas generadas en docs/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import config as cfg
from . import estado, informe, web
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


def generar_web(args) -> int:
    config = cfg.cargar(args.normas)
    datos = Path(args.datos)
    leer = lambda nombre: json.loads((datos / nombre).read_text(encoding="utf-8"))  # noqa: E731
    for ruta in web.generar(leer("estado.json"), leer("validacion.json"), config, Path(args.docs)):
        print(f"→ {ruta}")
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
