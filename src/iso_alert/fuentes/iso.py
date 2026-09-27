"""ISO Open Data: dataset ``iso_deliverables_metadata`` (licencia ODC-By 1.0).

iso.org está detrás de un *challenge* de Cloudflare, pero los ficheros se
sirven directamente desde Azure Blob. Se usa el JSONL, que se lee línea a
línea sin dependencias.

Cualquier desviación del formato esperado lanza ``FuenteError``: el
workflow debe fallar, nunca registrar "sin cambios" en silencio.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from pathlib import Path

URL = (
    "https://isopublicstorageprod.blob.core.windows.net/opendata/_latest/"
    "iso_deliverables_metadata/json/iso_deliverables_metadata.jsonl"
)
PAGINA = "https://www.iso.org/open-data.html"
LICENCIA = "ODC-By 1.0"

CAMPOS = {
    "id": int,
    "deliverableType": str,
    "supplementType": (str, type(None)),
    "reference": str,
    "title": dict,
    "publicationDate": (str, type(None)),
    "edition": (int, type(None)),
    "icsCode": (list, type(None)),
    "ownerCommittee": (str, type(None)),
    "currentStage": int,
    "replaces": (list, type(None)),
    "replacedBy": (list, type(None)),
    "languages": (list, type(None)),
    "pages": (dict, type(None)),
    "scope": (dict, type(None)),
}
MIN_REGISTROS = 70_000
USER_AGENT = "ISO_Alert (+https://github.com/reddrex/ISO_Alert)"


class FuenteError(RuntimeError):
    pass


@dataclass(frozen=True)
class Descarga:
    ruta: Path
    url: str
    last_modified: str | None  # ISO 8601
    etag: str | None
    sha256: str
    bytes: int


def descargar(destino: Path, url: str = URL, intentos: int = 3) -> Descarga:
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(destino.suffix + ".part")
    ultimo_error: Exception | None = None
    for intento in range(1, intentos + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=120) as resp:
                if resp.status != 200:
                    raise FuenteError(f"HTTP {resp.status} al descargar {url}")
                h = hashlib.sha256()
                total = 0
                with open(tmp, "wb") as f:
                    while trozo := resp.read(1 << 20):
                        f.write(trozo)
                        h.update(trozo)
                        total += len(trozo)
                lm = resp.headers.get("Last-Modified")
                etag = resp.headers.get("ETag")
                esperado = resp.headers.get("Content-Length")
            if esperado and int(esperado) != total:
                raise FuenteError(f"descarga incompleta: {total} de {esperado} bytes")
            tmp.replace(destino)
            return Descarga(
                ruta=destino,
                url=url,
                last_modified=parsedate_to_datetime(lm).isoformat() if lm else None,
                etag=etag,
                sha256=h.hexdigest(),
                bytes=total,
            )
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            ultimo_error = e
            if intento < intentos:
                time.sleep(10 * intento)
    raise FuenteError(f"no se pudo descargar {url}: {ultimo_error}")


def sha256_de(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        while trozo := f.read(1 << 20):
            h.update(trozo)
    return h.hexdigest()


def leer(ruta: Path, minimo: int = MIN_REGISTROS) -> Iterator[dict]:
    """Recorre el JSONL validando cada registro contra el esquema esperado."""
    n = 0
    with open(ruta, encoding="utf-8") as f:
        for linea_n, linea in enumerate(f, 1):
            if not linea.strip():
                continue
            try:
                r = json.loads(linea)
            except json.JSONDecodeError as e:
                raise FuenteError(f"línea {linea_n}: JSON inválido ({e})") from e
            _validar(r, linea_n)
            n += 1
            yield r
    if n < minimo:
        raise FuenteError(f"el dataset tiene {n} registros; se esperaban al menos {minimo}")


def _validar(r: dict, linea_n: int) -> None:
    faltan = CAMPOS.keys() - r.keys()
    if faltan:
        raise FuenteError(f"línea {linea_n}: faltan campos {sorted(faltan)}; ¿ha cambiado el esquema?")
    for campo, tipos in CAMPOS.items():
        if not isinstance(r[campo], tipos):
            raise FuenteError(
                f"línea {linea_n} (id {r.get('id')}): '{campo}' es {type(r[campo]).__name__}; ¿ha cambiado el esquema?"
            )
