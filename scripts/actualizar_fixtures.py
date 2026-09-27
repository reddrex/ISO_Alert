"""Regenera tests/fixtures/iso_subset.jsonl a partir del dataset completo.

Incluye todos los registros de los números vigilados y los alcanzables desde
ellos por replaces/replacedBy (hasta 3 saltos), para poder seguir cadenas de
sustitución como 9126-1 → 25010.

    python scripts/actualizar_fixtures.py [.cache/iso_deliverables_metadata.jsonl]
"""

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from iso_alert.config import cargar  # noqa: E402
from iso_alert.referencias import try_parse  # noqa: E402

origen = Path(sys.argv[1] if len(sys.argv) > 1 else RAIZ / ".cache" / "iso_deliverables_metadata.jsonl")
destino = RAIZ / "tests" / "fixtures" / "iso_subset.jsonl"

numeros = {n.numero for n in cargar(RAIZ / "normas.yaml").normas}
registros = {}
for linea in open(origen, encoding="utf-8"):
    r = json.loads(linea)
    registros[r["id"]] = r

elegidos = set()
for r in registros.values():
    ref = try_parse(r["reference"])
    if ref and ref.numero in numeros:
        elegidos.add(r["id"])

frontera = set(elegidos)
for _ in range(3):
    nuevos = set()
    for i in frontera:
        r = registros[i]
        for j in (r["replaces"] or []) + (r["replacedBy"] or []):
            if j in registros and j not in elegidos:
                nuevos.add(j)
    elegidos |= nuevos
    frontera = nuevos

destino.parent.mkdir(parents=True, exist_ok=True)
with open(destino, "w", encoding="utf-8", newline="\n") as f:
    for i in sorted(elegidos):
        f.write(json.dumps(registros[i], ensure_ascii=False, separators=(",", ":")) + "\n")
print(f"{len(elegidos)} registros → {destino} ({destino.stat().st_size / 1e6:.1f} MB)")
