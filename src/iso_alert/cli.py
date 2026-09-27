"""Línea de órdenes: ``python -m iso_alert validar``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import config as cfg
from . import informe
from .fuentes import iso
from .resolver import Indice

RAIZ = Path.cwd()
CACHE = RAIZ / ".cache" / "iso_deliverables_metadata.jsonl"
CACHE_META = CACHE.with_suffix(".meta.json")


def _obtener_dataset(args) -> tuple[Path, iso.Descarga | None]:
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


def validar(args) -> int:
    config = cfg.cargar(args.normas)
    ruta, descarga = _obtener_dataset(args)
    indice = Indice(iso.leer(ruta, minimo=args.minimo))
    datos = informe.construir(config, indice, descarga)

    salida_json = Path(args.salida_json)
    salida_json.parent.mkdir(parents=True, exist_ok=True)
    salida_json.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    salida_md = Path(args.salida_md)
    salida_md.parent.mkdir(parents=True, exist_ok=True)
    salida_md.write_text(informe.a_markdown(datos), encoding="utf-8")

    r = datos["resumen"]
    print(f"{r['total']} normas · {r['por_estado']}")
    print(f"{r['con_sugerencias']} con sugerencias · {r['ediciones_superadas']} ediciones citadas superadas")
    print(f"→ {salida_json}\n→ {salida_md}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="iso_alert", description="Vigilancia de normas ISO/UNE")
    sub = p.add_subparsers(dest="orden", required=True)

    v = sub.add_parser("validar", help="genera el informe de validación de normas.yaml")
    v.add_argument("--normas", default="normas.yaml")
    v.add_argument("--fichero", help="JSONL local en lugar de descargar")
    v.add_argument("--sin-descarga", action="store_true", help="reutiliza .cache/ si existe")
    v.add_argument("--minimo", type=int, default=iso.MIN_REGISTROS, help=argparse.SUPPRESS)
    v.add_argument("--salida-json", default="data/validacion.json")
    v.add_argument("--salida-md", default="docs/validacion.md")
    v.set_defaults(func=validar)

    args = p.parse_args(argv)
    try:
        return args.func(args)
    except (cfg.ConfigError, iso.FuenteError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
