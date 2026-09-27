# ISO_Alert — Vigilancia de normas ISO/UNE para opositores TIC

Herramienta que vigila las normas técnicas ISO/IEC (y, más adelante, sus adopciones UNE) citadas en el temario del Cuerpo Superior de Sistemas y Tecnologías de la Información de la Administración del Estado (TIC A1). Muestra en una web el estado actual de cada norma y avisa cuando sale una edición nueva o se anula una norma.

**Web:** <https://reddrex.github.io/ISO_Alert/>

> [!WARNING]
> **No es una fuente oficial.** Puede contener errores y los datos llegan con retraso. Ante cualquier duda, consulta [ISO](https://www.iso.org) o [UNE](https://www.une.org).

## Estado del proyecto

En desarrollo. Ya funcionan la comprobación de la lista de normas contra el dataset de ISO y el [informe de validación](https://reddrex.github.io/ISO_Alert/validacion/). Faltan la vigilancia diaria y los avisos. El plan completo está en [PLAN.md](PLAN.md).

## Cómo suscribirse (cuando estén activos los avisos)

- **GitHub:** *Watch* → *Custom* → *Issues*. Se abre un Issue por cada edición nueva o anulación.
- **RSS/Atom:** `https://reddrex.github.io/ISO_Alert/feed.xml`.

No se recogen emails ni datos personales.

## Uso local

```sh
python -m venv .venv
.venv/bin/pip install -e ".[dev,web]"      # en Windows: .venv\Scripts\pip

python -m iso_alert validar                # descarga el dataset ISO (~80 MB) y genera el informe
python -m iso_alert validar --sin-descarga # reutiliza la descarga de .cache/
zensical serve                             # web en http://localhost:8000

pytest                                     # tests con un extracto real del dataset
pytest -m lento                            # tests sobre el dataset completo
```

La lista de normas vigiladas está en [`normas.yaml`](normas.yaml). La cabecera del fichero documenta sus campos.

## Fuentes y atribución

- **ISO Open Data**, dataset *ISO deliverables metadata*, © ISO, con licencia [ODC-By 1.0](https://opendatacommons.org/licenses/by/1-0/). Fuente: <https://www.iso.org/open-data.html>.
- **Boletín Oficial del Estado** (fase 2), a través de su [API de datos abiertos](https://www.boe.es/datosabiertos/).

## Licencia

Código con licencia [MIT](LICENSE). Los datos derivados del dataset ISO mantienen la atribución que exige la licencia ODC-By 1.0.
