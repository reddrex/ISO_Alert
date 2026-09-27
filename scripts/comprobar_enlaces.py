"""Comprueba que todos los enlaces internos del sitio construido (site/) existen.

    python scripts/comprobar_enlaces.py [site]

Sale con código 1 si hay enlaces rotos. La página 404 usa rutas absolutas del
sitio publicado (/ISO_Alert/…) y se ignora.
"""

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

raiz = Path(sys.argv[1] if len(sys.argv) > 1 else "site").resolve()
ids: dict[Path, set[str]] = {}


def ids_de(pagina: Path) -> set[str]:
    if pagina not in ids:
        ids[pagina] = set(re.findall(r'id="([^"]+)"', pagina.read_text(encoding="utf-8")))
    return ids[pagina]


rotos: dict[str, set[str]] = {}
total = 0
for html in raiz.rglob("*.html"):
    if html.name == "404.html":
        continue
    for href in re.findall(r'href="([^"]+)"', html.read_text(encoding="utf-8")):
        if href.startswith(("http:", "https:", "mailto:", "javascript:", "data:", "#")):
            continue
        total += 1
        url = urlparse(href)
        destino = (html.parent / unquote(url.path)).resolve()
        if destino.is_dir():
            destino = destino / "index.html"
        ok = destino.exists() and destino.is_relative_to(raiz)
        if ok and url.fragment and destino.suffix == ".html":
            ok = url.fragment in ids_de(destino)
        if not ok:
            rotos.setdefault(href, set()).add(str(html.relative_to(raiz)))

print(f"{total} enlaces internos, {len(rotos)} rotos")
for href, paginas in sorted(rotos.items()):
    print(f"  {href}  ← {', '.join(sorted(paginas)[:3])}")
sys.exit(1 if rotos else 0)
