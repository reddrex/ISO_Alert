# ISO_Alert — Observatorio de estándares TIC

Herramienta que vigila las normas técnicas ISO/IEC y sus adopciones UNE citadas en el temario del Cuerpo Superior de Sistemas y Tecnologías de la Información de la Administración del Estado (TIC A1). Muestra en una web el estado actual de cada norma y avisa cuando sale una edición nueva o se anula una norma.

**Web:** <https://reddrex.github.io/ISO_Alert/>

> [!WARNING]
> **No es una fuente oficial.** Puede contener errores y los datos llegan con retraso. Ante cualquier duda, consulta [ISO](https://www.iso.org) o [UNE](https://www.une.org).

## Estado del proyecto

En desarrollo. La web ya muestra el [estado de cada norma](https://reddrex.github.io/ISO_Alert/estado/) con los datos de ISO del día, una capa de estudio (las normas [por ámbito](https://reddrex.github.io/ISO_Alert/ambito/), en áreas y familias, las [normas de cada tema del temario](https://reddrex.github.io/ISO_Alert/temario/) y [trucos de examen](https://reddrex.github.io/ISO_Alert/comparativas/)), una página por familia y por norma y el [informe de validación](https://reddrex.github.io/ISO_Alert/validacion/) de la lista. Cada día compara los datos de ISO con los del día anterior y lee el BOE para las normas UNE (qué versión española está vigente y si adopta la edición ISO actual); registra los cambios en el [historial](https://reddrex.github.io/ISO_Alert/historial/) y avisa de las ediciones nuevas, modificaciones y anulaciones, de ISO y de UNE. El plan completo está en [PLAN.md](PLAN.md).

## Cómo suscribirse

- **RSS/Atom:** un feed general (`https://reddrex.github.io/ISO_Alert/feed.xml`) y uno por norma, para seguir solo las que te interesen. Es la única vía pública: el repositorio es privado.
- **Issues del repositorio:** se abre uno por cada edición nueva, modificación o anulación (ISO o UNE) de las normas y partes citadas en el temario. Solo los ven los colaboradores.

No se recogen emails ni datos personales.

## Uso local

```sh
python -m venv .venv
.venv/bin/pip install -e ".[dev,web]"      # en Windows: .venv\Scripts\pip

python -m iso_alert vigilar --simulacro       # comprobación diaria: detecta cambios sin abrir Issues
python -m iso_alert actualizar                # descarga el dataset ISO (~80 MB) → data/estado.json y data/validacion.json
python -m iso_alert actualizar --sin-descarga # reutiliza la descarga de .cache/
python -m iso_alert une                       # carga inicial (reanudable) de las normas UNE desde el BOE → data/une.json
python -m iso_alert web                       # data/ → páginas generadas en docs/
zensical serve                                # web en http://localhost:8000

pytest                                     # tests con un extracto real del dataset
pytest -m lento                            # tests sobre el dataset completo
```

La lista de normas vigiladas está en [`normas.yaml`](normas.yaml), con sus textos de estudio, relaciones y temas del temario; la cabecera del fichero documenta sus campos. Los temas del temario están en [`temario.yaml`](temario.yaml).

## Fuentes y atribución

- **ISO Open Data**, dataset *ISO deliverables metadata*, © ISO, con licencia [ODC-By 1.0](https://opendatacommons.org/licenses/by/1-0/). Fuente: <https://www.iso.org/open-data.html>.
- **Boletín Oficial del Estado**, a través de su [API de datos abiertos](https://www.boe.es/datosabiertos/): resoluciones mensuales de normas UNE aprobadas, anuladas y en información pública.

## Licencia

Código con licencia [MIT](LICENSE). Los datos derivados del dataset ISO mantienen la atribución que exige la licencia ODC-By 1.0.
