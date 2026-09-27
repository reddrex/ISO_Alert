# Plan de desarrollo — Vigilancia de normas ISO/UNE (ISO_Alert)

Repositorio: https://github.com/reddrex/ISO_Alert (público, vacío, Issues activados, Pages sin configurar).
Web prevista: `https://reddrex.github.io/ISO_Alert/` · Feed: `https://reddrex.github.io/ISO_Alert/feed.xml`

Este plan se basa en comprobaciones hechas el 2026-09-27 sobre los datos reales (sección 1). Las decisiones de la sección 2 del brief se mantienen; solo señalo dos puntos que conviene matizar (1.3 y 1.4).

---

## 1. Qué he comprobado

### 1.1 ISO Open Data

| Pregunta del brief | Resultado |
|---|---|
| URL de descarga | `iso.org` está detrás de un *challenge* de Cloudflare (un `curl` recibe "Just a moment…"). **Los ficheros no**: se sirven desde Azure Blob sin protección:<br>`https://isopublicstorageprod.blob.core.windows.net/opendata/_latest/iso_deliverables_metadata/json/iso_deliverables_metadata.jsonl` (también `/parquet/…parquet` y `/csv/…csv`). |
| Tamaño | JSONL 79,5 MB · Parquet 24,3 MB · CSV 59,8 MB. 81 478 registros. |
| ¿Streaming? | No hace falta para la memoria, pero leer el JSONL línea a línea con la librería estándar es trivial y evita depender de `pyarrow`. **Elijo JSONL en streaming.** |
| Esquema | 15 campos, todos presentes en todos los registros: `id` (único), `deliverableType` (IS, TS, TR, R, ISP, PAS, GUIDE, IWA, DATA, TTA), `supplementType` (null, Amd, Cor, Add, Suppl, Ext), `reference`, `title{en,fr}`, `publicationDate`, `edition`, `icsCode`, `ownerCommittee`, `currentStage` (entero, p. ej. `6060`), `replaces` y `replacedBy` (**listas de `id`**), `languages`, `pages`, `scope`. |
| Enlace edición en desarrollo ↔ vigente | Por `id`, en los dos sentidos: el proyecto tiene la vigente en `replaces` y la vigente tiene el proyecto en `replacedBy` **antes de que se publique**. Ejemplo: `ISO 22301:2019` (90.92) → `replacedBy=[93606]` = `ISO/CD 22301` (30.60). |
| ¿Siguen las anuladas antiguas? | Sí. Hay registros en 95.99 desde los años 50. ISO/IEC 9126:1991 y 9126-1:2001 aparecen, con `replacedBy` hacia ISO/IEC 25010:2011. |
| Actualización | La cabecera `Last-Modified` era del 23-09 cuando lo consulté el 27-09: **no siempre es diaria**. |

Hallazgos que condicionan el diseño:

1. **`replacedBy` no significa "sustituida".** Se rellena en cuanto hay un proyecto de revisión. Hay que mirar la etapa del sustituto: solo si está publicado (≥ 60.60) la norma está sustituida.
2. **El prefijo cambia entre ediciones**: `ISO/IEC 15289:2006` → `ISO/IEC/IEEE 15289:2011`; `ISO/TR 15801` → `ISO 15801:2026` (cambió incluso de TR a IS). **El emparejamiento se hace por número y parte, no por prefijo ni tipo.**
3. **Las sustituciones cruzan números**: `ISO/IEC 2382-x` → `ISO/IEC 2382:2015`; `ISO/IEC 9126-1` → `ISO/IEC 25010`. Para mostrar "sustituida por…" hay que seguir la cadena `replacedBy` hasta un entregable publicado.
4. **Formatos de referencia variados** que el parser debe cubrir: `ISO/CD 22301`, `ISO/IEC CD 29115.2` (iteración), `ISO/DTR 26102`, `ISO/IEC/IEEE 8802-1Q:2020` (parte alfanumérica), `ISO/IEC 29110-5-1-4` (partes multinivel), `ISO/IEC TR 13335-3:1998`, `ISO 30301:2019/Amd 1:2024`, `ISO Guide 2:1976`.
5. **`reference` no es única** (80 040 valores para 81 478 registros): los proyectos cancelados repiten código. **La clave es siempre `id`.**
6. **Etapas que el brief no menciona**: `xx.98` = proyecto cancelado (≈ 15 000 registros), `90.99` / `95.20` / `95.60` = anulación propuesta o en curso, `60.00` = en publicación.
7. **El dataset no trae fecha de cambio de etapa**, solo `publicationDate`. La fecha de un evento será la **fecha de detección**, y así se dirá en la web.

### 1.2 Prototipo de emparejamiento contra `normas.yaml`

Un matcher rápido (número + parte, ignorando prefijo) encuentra **98 de 100** entradas. Es un adelanto del informe de validación:

| Entrada | Hallazgo | Propuesta |
|---|---|---|
| ISO 30303, ISO 30304 | **No existen en el dataset ISO**, ni siquiera como proyecto. La familia 30300 en ISO solo tiene 30300, 30301 y 30302. | Probablemente solo existen como UNE, o no existen. Quitar de la fase 1 o marcarlas como "solo UNE" para la fase 2. |
| ISO 26102 | Solo existe `ISO/DTR 26102`, cancelado en 30.98. Nunca se publicó. | Mostrar como "No publicada (proyecto cancelado)" o quitar. |
| ISO 31700 | Se publicó como `ISO 31700-1:2023` + `ISO/TR 31700-2:2023` (ya sustituido por `ISO/IEC TR 31700-2:2026`). Hay un AWI 31700-3. | `alcance: serie` es correcto. Resolver `revisar`. |
| ISO/IEC 29115 | Prefijo ISO/IEC confirmado. 2013 en 90.92, con un CD en marcha. | Resolver `revisar`. |
| 15289, 14764, 29148 | Todas son ya ISO/IEC/IEEE (los códigos del YAML son correctos). | Resolver `revisar`. |
| ISO/IEC 14102 | Existe `ISO/IEC 14102:2008` (90.93). | Resolver `revisar`. |
| ISO/IEC/IEEE 8802 | 57 entregables activos (partes 1Q, 1X, 3, 11…). El prefijo actual es ISO/IEC/IEEE. | Limitar a las partes citadas (ver 1.4). |
| ISO/IEC 19794 | 22 partes publicadas. **El dataset no enlaza 19794 con 39794** (sin `replaces`). La 39794 tiene 8 partes publicadas. | Decidir si se añade ISO/IEC 39794 como entrada propia. |
| ISO/IEC 13335 | Todas las partes (TR 1–5 y 13335-1:2004) están anuladas. La 13335-1:2004 no tiene `replacedBy`. | Resolver `revisar`: es histórica. Estado "Anulada". |
| ISO/TR 15801 | Ahora es `ISO 15801:2026` (IS). | Cambiar el código a `ISO 15801`. El matcher lo encuentra igual. |
| ISO/IEC 24766 | Es un TR: `ISO/IEC TR 24766:2009`. | Ajustar el código. |
| ISO/IEC 24708 | En **90.99** (anulación propuesta). | Necesita un estado para esto (ver 5). |
| ISO/IEC 14598 | Solo la parte 6 sigue vigente; el resto está anulado. | Mostrar el recuento por partes de la serie (ver 4.3). |

**Ediciones citadas ya superadas** (8 de 13): ISO 22301:2012 → 2019 · ISO/IEC/IEEE 12207:2017 → 2026 · ISO/IEC 14764:2006 → ISO/IEC/IEEE 14764:2022 · ISO 9000:2015 → 2026 · ISO 9001:2015 → 2026 · ISO/IEC 20924:2018 → 2024 · ISO/IEC 30141:2018 → 2024 · ISO 37120:2015 → 2018 · ISO/TR 15801:2004 → ISO 15801:2026.
**Siguen vigentes**: ISO 10007:2017, ISO 9004:2018, ISO/TR 18492:2005, ISO 19005-1:2005.

Unas **17 entradas** están hoy en 90.92 o tienen un proyecto de revisión en marcha, así que aparecerían como "En revisión": 22301, 31000, 17065, 29115, 15289, 29148, 10007, 33063, 7372, 30300, 30301, 2382-37, 40500, 20924, 30141, 37120, entre otras.

### 1.3 Volumen de las series (punto a matizar)

Las 35 entradas con `alcance: serie` arrastran **1 487 entregables (491 activos)**. Las mayores: ISO 9241 (69 activos), ISO/IEC/IEEE 8802 (57), ISO/IEC 19794 (50), ISO 8000 (35), ISO/IEC 29110 (33), ISO/IEC 9075 (32). Con la política actual, **cualquier parte nueva o revisada de la 9241 abriría un Issue**, aunque el temario solo cite la 9241-210. Eso son decenas de avisos al año que ningún opositor necesita. Propuesta en la sección 9, pregunta 1.

### 1.4 Motor web: Zensical

He instalado Zensical 0.0.65 (publicada el 24-09-2026) y he construido un sitio de prueba con la configuración que necesitamos:

| Requisito | Resultado |
|---|---|
| Buscador | ✅ genera `search.json`, interfaz en español ("Buscar") |
| Modo oscuro con conmutador | ✅ `palette` con `scheme: slate` y `toggle` |
| Colores propios | ✅ `primary: custom` + variables CSS |
| Tipografía propia | ✅ carga desde Google Fonts |
| Pestañas y secciones de navegación | ✅ `navigation.tabs`, `navigation.sections` |
| JS y CSS propios, tablesort | ✅ `extra_javascript` / `extra_css`; el *observable* `document$` existe en el bundle, así que el JS sobrevive a la navegación instantánea |
| Plantillas propias (`custom_dir`) | ✅ el bloque `announce` sobrescrito se renderiza |
| `language: es` | ✅ `lang="es"` |
| Admonitions | ✅ |
| Despliegue en Pages | ✅ genera un `site/` estático; se sube con `actions/upload-pages-artifact` + `actions/deploy-pages` |

**Decisión: Zensical, con versión exacta fijada (`zensical==0.0.65`).**
Justificación: cubre todos los requisitos del brief (comprobado, no solo documentado), lee el mismo `mkdocs.yml` y Material deja de recibir correcciones el 05-11-2026, dentro de 5 semanas.
Riesgo: es 0.x y cambia rápido (65 versiones). Mitigación: versión fijada, actualizaciones solo manuales con la CI verde, y un `requirements-material.txt` alternativo (`mkdocs-material==9.7.7`, `mkdocs==1.6.1`) que construye el mismo `mkdocs.yml` por si Zensical rompe algo. En la fase 0 comprobaré la variante *classic* del tema, que conserva exactamente el aspecto de Material.

### 1.5 BOE (fase 2, solo viabilidad)

- `https://www.boe.es/datosabiertos/api/boe/sumario/AAAAMMDD` con `Accept: application/json` devuelve el sumario estructurado.
- El 09-09-2026 aparecen dos resoluciones de la D.G. de Estrategia Industrial y de la PYME: "normas UNE anuladas durante el mes de agosto" y "se someten a información pública…".
- `https://www.boe.es/diario_boe/xml.php?id=BOE-A-…` devuelve XML con **una `<table>` HTML limpia** (columnas Código / Título). Se puede parsear sin *scraping* de la web.
- Queda por ver una resolución de "aprobadas" con la columna "Sustituye a". Lo haré al inicio de la fase 2.

---

## 2. Fases y entregables

### Fase 0 — Arranque del repositorio (≈ 1 sesión)
- Estructura de directorios (sección 3), `pyproject.toml` (Python 3.12, dependencias mínimas: `pyyaml`, `httpx`, `jinja2`, `pytest`), licencia del código, `.gitignore`.
- `README.md`: qué hace, aviso de **fuente no oficial**, atribución a ISO (ODC-By 1.0) y cómo suscribirse.
- `mkdocs.yml` + Zensical y una web vacía con el tema personalizado (paleta provisional).
- Workflow `ci.yml`: tests y *build* de la web en cada push y PR.
- Validación del esquema de `normas.yaml` (campos obligatorios, `familia` existente, `alcance` válido), que falla en la CI.

**Entregable:** repo con CI verde y web vacía construyendo en local.

### Fase 1a — Núcleo ISO e informe de validación (MVP, parte 1)
- `fuentes/iso.py`: descarga en streaming del JSONL, **validación de esquema** (15 claves, tipos y un mínimo de 70 000 registros), guardado de `Last-Modified`, `ETag` y `sha256`.
- `referencias.py`: parser de códigos (sección 4.1) con tests sobre los formatos reales listados en 1.1.
- `resolver.py`: entrada de `normas.yaml` → entregables → estado (sección 4).
- `informe.py`: **informe de validación** en `data/validacion.json` y `docs/validacion.md` (sección 6).
- CLI: `python -m iso_alert validar`.

**Entregable:** informe de validación generado sobre los datos reales. Con él revisas las entradas `revisar` y corriges `normas.yaml`.

### Fase 1b — Web mínima publicada (MVP, parte 2)
- Generación de las páginas desde `data/` (sección 7): Inicio, Estado, Historial (vacío), Guía, Acerca de y Validación.
- Tabla de estado con filtros, búsqueda, ordenación, vista por familia y diseño móvil.
- Workflow `pages.yml` que publica en GitHub Pages.

**Entregable (fin del MVP):** `https://reddrex.github.io/ISO_Alert/` publicada, con el estado real y el informe de validación.

### Fase 1c — Vigilancia diaria y avisos
- `diff.py`: estado anterior frente a nuevo → eventos del catálogo (sección 5), con ids deterministas.
- `data/historial.json`, `data/estado.json` y `data/last_checked.json`.
- `avisos.py`: un Issue por evento notificable, idempotente.
- `rss.py`: `feed.xml` (Atom) con los eventos notificables y un feed por norma (`feeds/<norma>.xml`) con todos sus eventos.
- Workflow `vigilar.yml`: cron diario + `workflow_dispatch` → commit de `data/` → build y despliegue.
- **Primera ejecución = línea base**: se registra un evento `alta_vigilancia` por entrada, sin Issues.

**Entregable:** vigilancia automática en marcha, con un Issue de prueba creado en un ensayo controlado (sección 8) y cerrado después.

### Fase 2 — BOE / UNE
- `fuentes/boe.py`: recorre los sumarios desde el último día procesado (`last_checked.boe.ultimo_dia`) hasta hoy, **recuperando los días pendientes**.
- Identifica las resoluciones por departamento y un patrón de título (aprobadas, anuladas, información pública, proyectos europeos e internacionales).
- Parsea la tabla del XML y empareja por el número ISO contenido en el código UNE.
- Eventos `adopcion_une`, `anulacion` (fuente UNE) y `proyecto_une_info_publica`.
- Columna "UNE" en la tabla. Sin carga histórica, solo se conoce la UNE vigente si la cita `normas.yaml` o si se ha detectado desde el arranque. La web lo dirá.

### Fase 3 — Mejoras posteriores (fuera del MVP)
Página de detalle por norma, historial por norma, gráfica de actividad y migración a Zensical estable cuando salga la 1.0.

---

## 3. Estructura de directorios

```
ISO_Alert/
├── normas.yaml                 # lista vigilada (editada a mano)
├── mkdocs.yml                  # configuración del sitio (Zensical)
├── pyproject.toml
├── requirements-material.txt   # alternativa si Zensical falla
├── README.md  LICENSE
├── src/iso_alert/
│   ├── cli.py                  # validar | vigilar | web
│   ├── config.py               # carga y valida normas.yaml
│   ├── referencias.py          # parser de códigos ISO/UNE
│   ├── modelo.py               # estados, tipos de cambio, dataclasses
│   ├── resolver.py             # entrada → entregables → estado
│   ├── diff.py                 # estado anterior vs nuevo → eventos
│   ├── avisos.py               # Issues (API de GitHub)
│   ├── rss.py                  # feed Atom
│   ├── informe.py              # informe de validación
│   ├── web.py                  # genera las páginas Markdown del sitio
│   └── fuentes/
│       ├── iso.py
│       └── boe.py              # fase 2
├── plantillas/                 # Jinja2 de las páginas generadas y del cuerpo de los Issues
├── data/
│   ├── estado.json
│   ├── historial.json
│   ├── last_checked.json
│   └── validacion.json
├── docs/                       # fuente del sitio
│   ├── guia.md                 # la guía (hoy guia-normas.md)
│   ├── acerca.md
│   ├── index.md  estado.md  historial.md  validacion.md   # GENERADAS, no se versionan
│   ├── javascripts/estado.js   # filtros y búsqueda de la tabla
│   ├── stylesheets/extra.css   # paleta, colores de estado, móvil
│   └── assets/logo.svg  favicon.svg
├── overrides/main.html         # barra "fuente no oficial"
├── tests/
│   ├── fixtures/iso_subset.jsonl   # extracto real (ver sección 10)
│   ├── fixtures/boe/*.xml          # fase 2
│   └── test_*.py
└── .github/workflows/
    ├── ci.yml                  # tests + build en push/PR
    └── vigilar.yml             # cron diario: vigilar → commit → build → deploy
```

Las páginas generadas no se versionan: se crean en el *build* a partir de `data/`, que es la única fuente de verdad. La guía vive directamente en `docs/guia.md`. El brief la sitúa en `contenido/guia-normas.md`, pero ahora mismo está en la raíz.

---

## 4. Modelo: de entrada a estado

### 4.1 Parser de referencias
`ISO[/IEC][/IEEE] [etapa-borrador] [tipo] NÚMERO[-parte…][.iteración][:año][/Amd|Cor n:año]` →
`{organismos, borrador (NP/PWI/AWI/WD/CD/DIS/FDIS/PRF/DTR/DTS…), tipo (IS/TR/TS/PAS/Guide), numero, parte (alfanumérica, multinivel), anio, suplemento}`.

La **clave de emparejamiento** es `(numero, parte)`. `partes_citadas` admite `"TR 2"` y rangos como `"100-150"`.

### 4.2 Entregables de una entrada
- `alcance: norma`: registros con el mismo número y la misma parte (sin parte si el código no la tiene).
- `alcance: serie`: registros con el mismo número y cualquier parte.
- Los suplementos (Amd, Cor) se asocian a su entregable base y se muestran en el detalle.
- Además se siguen las cadenas `replaces` y `replacedBy` por `id`, para enlazar ediciones aunque cambie el prefijo o el número.

### 4.3 Estado de cada entregable y agregado por entrada

| Etapa ISO | Estado (web y guía) | Sub-estado |
|---|---|---|
| 60.60, 90.00, 90.93 | **Vigente** | — |
| 90.20, 90.60 | **Vigente** | *Revisión periódica* (discreto) |
| 90.92, o proyecto activo (00.00–60.00, no `xx.98`) enlazado por `replacedBy` | **En revisión** | etapa del proyecto (CD, DIS…) |
| 90.99, 95.20, 95.60 | **Vigente** | *Anulación propuesta* (**nuevo, por confirmar**) |
| 95.99 y `replacedBy` alcanza un entregable publicado | **Sustituida** | "por X:AAAA" |
| 95.99 sin sustituto publicado | **Anulada** | — |
| Solo proyectos, o todos cancelados | **No publicada** (**nuevo, por confirmar**) | — |
| Sin registros | **No encontrada** (solo en el informe de validación) | — |

**Entrada `norma`**: el estado de su edición más reciente.
**Entrada `serie`**: se calcula sobre las partes relevantes (las citadas si hay `partes_citadas`; si no, todas). Si todas están anuladas o sustituidas, ese es el estado. Si no, se toma el más relevante, con prioridad En revisión > Revisión periódica > Vigente, y se añade un recuento: "Vigente · 1 de 6 partes vigentes" (caso 14598).

**Edición citada superada**: si `edicion_citada` no coincide con el año de la edición vigente, se marca "El temario cita :2012 · vigente :2019".

---

## 5. Catálogo de tipos de cambio (común a ISO y UNE)

| `tipo` | Disparador ISO | Disparador UNE (fase 2) | Aviso |
|---|---|---|---|
| `edicion_nueva` | Un entregable pasa a 60.60 (o aparece en 60.60) y su `replaces` contiene uno vigilado | — | **Sí** (etiquetas `edicion-nueva`, `fuente:iso`) |
| `adopcion_une` | — | Resolución de aprobadas: "Sustituye a" afecta a una vigilada, o nueva UNE que adopta una ISO vigilada | **Sí** (`edicion-nueva`, `fuente:une`) |
| `anulacion` | Pasa a 95.99 sin sustituto publicado | Aparece en la relación mensual de anuladas | **Sí** (`anulacion`) |
| `revision_iniciada` | Pasa a 90.92, o aparece un proyecto enlazado | — | No |
| `proyecto_avanza` | El proyecto enlazado cambia de etapa (CD → DIS…) | — | No |
| `proyecto_cancelado` | El proyecto pasa a `xx.98` | — | No |
| `publicacion_inminente` | Pasa a 60.00 | — | No |
| `revision_periodica` | Pasa a 90.20 o 90.60 | — | No |
| `confirmada` | Pasa a 90.93 | — | No |
| `anulacion_propuesta` | Pasa a 90.99, 95.20 o 95.60 | — | No |
| `modificacion_publicada` | Un Amd pasa a 60.60 | — | **Sí**, solo partes citadas (`modificacion`) |
| `parte_nueva` | Se publica una parte nueva de una serie vigilada | — | Solo en series sin `partes_citadas` (agrupado) |
| `proyecto_une_info_publica` | — | Proyecto UNE en información pública | No |
| `alta_vigilancia` | Entrada nueva en `normas.yaml` (línea base) | ídem | No |

Cuando ISO publica la edición nueva y anula la anterior en el mismo día, se genera **un solo** evento `edicion_nueva`, con la clave del entregable nuevo. La edición anterior pasa a "Sustituida" sin evento propio.

---

## 6. Esquemas de datos

### `data/estado.json`
```json
{
  "version_esquema": 1,
  "generado": "2026-09-28T06:12:00Z",
  "fuentes": {
    "iso": {"url": "…/iso_deliverables_metadata.jsonl", "last_modified": "2026-09-23T00:41:03Z",
            "etag": "…", "sha256": "…", "registros": 81478}
  },
  "entregables": {
    "75106": {"referencia": "ISO 22301:2019", "numero": "22301", "parte": null, "tipo": "IS",
              "suplemento": null, "etapa": 9092, "edicion": 2, "publicacion": "2019-10-30",
              "titulo_en": "Security and resilience — Business continuity management systems — Requirements",
              "replaces": [50038], "replaced_by": [93606], "entradas": ["ISO 22301"]}
  },
  "normas": {
    "ISO 22301": {
      "estado": "en_revision", "subestado": "CD",
      "vigentes": [75106], "en_desarrollo": [93606], "suplementos": [88412],
      "sustituida_por": [], "partes": null,
      "edicion_citada": {"anio": "2012", "superada": true, "vigente_anio": "2019"},
      "une": {"codigo": null, "estado": null}
    }
  }
}
```
El diff trabaja sobre `entregables` (una clave plana por `id`). `normas` es la vista que se deriva de ellos.
**Si un entregable vigilado desaparece del dataset, la ejecución falla**, porque ISO no borra registros: sería un cambio de formato.

### `data/historial.json`
```json
[
  {"id": "e3b0c442…", "detectado": "2026-10-14", "dato_fecha": "2026-10-13",
   "fuente": "iso", "tipo": "edicion_nueva", "notificable": true,
   "norma": "ISO 22301", "entregable": {"id": 93606, "referencia": "ISO 22301:2026"},
   "sustituye": [{"id": 75106, "referencia": "ISO 22301:2019"}],
   "etapa_anterior": 5020, "etapa_nueva": 6060,
   "resumen": "Publicada ISO 22301:2026, que sustituye a ISO 22301:2019",
   "issue": 42}
]
```
`id` = sha256 de `fuente|tipo|id_entregable|etapa_nueva`. Es determinista, así que repetir una ejecución no duplica entradas.

### `data/last_checked.json`
```json
{"ejecucion": "2026-09-28T06:12:00Z", "resultado": "ok | fuente_sin_cambios | error",
 "iso": {"last_modified": "…", "cambios": true}, "boe": {"ultimo_dia": "2026-09-26"},
 "eventos_nuevos": 0, "run_url": "https://github.com/reddrex/ISO_Alert/actions/runs/…"}
```

### `data/validacion.json` e informe
Por entrada: `encontrada`, `candidatos` (si no se encuentra: el mismo número con otros prefijos, números cercanos de la misma familia o un aviso de "posiblemente solo UNE"), `estado`, `vigente` (referencia y año), `edicion_citada` (`superada` / `vigente` / `n/a`), `cambios_de_prefijo` (p. ej. "ahora ISO/IEC/IEEE"), `revisar` (el texto del YAML) y una `sugerencia`.
La página `validacion.md` lo muestra agrupado: no encontradas → con `revisar` → ediciones citadas superadas → resto.

---

## 7. Sitio web

### 7.1 Generación
`python -m iso_alert web` lee `data/` y escribe `docs/index.md`, `estado.md`, `historial.md`, `validacion.md` y `feed.xml` con plantillas Jinja2. Después se ejecuta `zensical build`. Nada generado se versiona.

### 7.2 Páginas
- **Inicio**: una línea de qué es esto y el aviso de fuente no oficial; "Última comprobación: fecha (datos ISO del día X)"; los 10 últimos cambios; enlaces a la tabla y al feed. Sin *hero* ni tarjetas.
- **Estado**: tabla HTML generada, con una fila por entrada y atributos `data-categoria`, `data-familia` y `data-estado`.
  - Columnas: Código · Nombre (es) · Título oficial (en) · Familia · Categoría · Estado · Edición vigente · Edición citada.
  - `estado.js` (unos 100 líneas, sin dependencias): tres `<select>`, un campo de búsqueda, un contador "N de 100" y los filtros reflejados en la URL (`?estado=en_revision`), para poder compartir enlaces.
  - Tablesort (el que documenta el tema) para ordenar.
  - "Por familia": segunda vista en pestañas del tema (`pymdownx.tabbed`), generada en el servidor.
  - Detalle de cada fila en `<details>`: partes, proyectos en marcha, Amd y enlace a la ficha de iso.org.
  - Móvil: en pantallas estrechas se ocultan Título oficial, Familia y Categoría (quedan en el detalle) y la tabla hace *scroll* horizontal dentro de su contenedor.
- **Historial**: lista cronológica inversa con filtros por tipo y fuente. Cada evento enlaza a su Issue si lo tiene.
- **Guía**: `guia.md` con las admonitions justas. Se amplía la tabla de estados si aceptas "No publicada" y "Anulación propuesta". Se añade la explicación "ISO va por delante de UNE" que pide el brief (§7).
- **Acerca de**: aviso de fuente no oficial, atribución ISO (ODC-By 1.0, con enlace) y BOE, cómo suscribirse (Watch → Custom → Issues; feed Atom), metodología (qué etapa significa qué, fecha de detección frente a fecha real) y enlace al código.
- **Validación**: el informe.

### 7.3 Estados: texto y color
Cada estado es una etiqueta con texto e icono y un color de fondo suave: Vigente (verde), Revisión periódica (gris azulado, discreto), En revisión (ámbar), Sustituida (naranja oscuro), Anulada (rojo), No publicada (gris). El contraste es AA en claro y en oscuro. El color nunca es la única pista.

### 7.4 Paletas (elige una)
| # | Nombre | Primario | Acento | Carácter |
|---|---|---|---|---|
| 1 | Petróleo y ámbar | `#1F4E5F` | `#B5651D` | Sobrio y cálido; se aleja mucho del índigo |
| 2 | Tinta y verde | `#2B3A55` | `#2E7D6B` | Institucional, el más "administración pública" |
| 3 | Grafito y granate | `#37474F` | `#8E2C3A` | Neutro, casi monocromo; el granate solo en enlaces y foco |

Tipografía propuesta: **Source Sans 3** para el texto (legible, con cifras tabulares para años y códigos) e **IBM Plex Mono** para los códigos de norma. Logo: un monograma SVG sencillo (un sello con "ISO" o un check sobre una línea), sin iconos de stock.

---

## 8. Workflows y robustez

**`vigilar.yml`** (cron `17 5 * * *`, a una hora poco habitual para evitar los picos de GitHub; también `workflow_dispatch` con la opción `dry_run`):
1. `concurrency: vigilar` para que no haya dos ejecuciones a la vez.
2. Descargar ISO → validar esquema → si el `sha256` coincide con el anterior, `resultado: fuente_sin_cambios` y se salta el diff.
3. Diff → eventos → historial (deduplicado por `id`).
4. **Guarda antirruido**: si salen más de 15 eventos notificables en una ejecución, no se abre ningún Issue, se abre uno de `revision-manual` y el job falla. Protege contra un fallo del parser o una anomalía del dataset.
5. Abrir los Issues: antes se busca el marcador `<!-- evento:ID -->` en los Issues existentes, así que repetir la ejecución no duplica.
6. Commit de `data/` **solo si ha cambiado** (con `git pull --rebase`), o de *keepalive* si el último commit tiene más de 45 días.
7. Job siguiente: generar la web → `zensical build` → `deploy-pages`.
8. Permisos: `contents: write`, `issues: write`, `pages: write`, `id-token: write`.

**Fallos ruidosos**: cualquier excepción (esquema, 0 registros, entregable desaparecido, error HTTP tras reintentos) hace fallar el job. GitHub avisa por email al autor del cron, y el script abre o actualiza **un único** Issue `fallo-fuente`, que se cierra solo cuando la fuente vuelve a funcionar. Nunca se escribe "sin cambios" tras un error.

**Fuente desactualizada**: si el `Last-Modified` de ISO tiene más de 14 días, se abre un Issue `fuente-desactualizada` (sin fallar).

**Cron desactivado**: además del *keepalive*, el workflow ejecuta `gh api -X PUT …/actions/workflows/vigilar.yml/enable`, que es inocuo y cubre el caso de que GitHub no cuente los commits del bot como actividad.

**Ensayo controlado de avisos (fin de la fase 1c)**: `workflow_dispatch` con un `estado.json` manipulado (ISO 22301 de vuelta a 50.20) comprueba de principio a fin que se crean el Issue, la entrada del feed y la del historial. Después se revierte y se cierra el Issue con la etiqueta `prueba`.

---

## 9. Decisiones (2026-09-27)

1. **Avisos en series**: la web y el historial cubren todas las partes, pero **solo abren Issue las partes citadas** (`partes_citadas`). En las series sin partes citadas avisan todas sus partes, agrupadas en un Issue por serie y ejecución.
2. **Estados nuevos**: se añaden "No publicada" y el sub-estado "Anulación propuesta" a la guía y a la web, **sin aviso**.
3. **Sub-estado "Revisión periódica"** (90.20/90.60 dentro de Vigente): se adopta.
4. **Modificaciones (`Amd`)**: **generan aviso** para las partes citadas (unas 10 al año, sobre todo en 8802-3 y 9594). Además, cada norma tiene su **propio feed Atom** (`feeds/<norma>.xml`) con todos sus eventos, así que cada persona se suscribe solo a las que le interesan, sin datos personales ni servicios externos.
5. **`normas.yaml` corregido**: 30303 y 30304 comentadas (no existen en ISO; se retoman en la fase 2 si aparecen como UNE); 26102 se queda como "No publicada"; `ISO 15801`; `ISO/IEC TR 24766`; se añade **ISO/IEC 39794**; 8802 cita las partes 1Q, 1X y 3; todas las dudas `revisar` resueltas y pasadas a `contexto`. Quedan 99 entradas.
6. **Paleta**: 2, "Tinta y verde".
7. **Licencia**: MIT.
8. **Fuente desactualizada**: 14 días sin fichero nuevo de ISO → Issue de aviso.
9. **Idioma de Issues y feeds**: español.
10. **Commits**: **solo cuando cambian los datos**, más un commit de *keepalive* si pasan 45 días sin ninguno y la llamada a la API que reactiva el workflow. Los commits no notifican a quien sigue el repo, pero así el historial de git queda limpio. La web se despliega en cada ejecución, así que la fecha de última comprobación siempre está al día.
11. **Configuración del repo**: Pages con *GitHub Actions* hecho. Los permisos de escritura los declara cada workflow, así que no hace falta cambiar el valor por defecto.

## 10. Estrategia de tests

- **Fixtures reales**: `tests/fixtures/iso_subset.jsonl`, un extracto del dataset con todos los registros de los números vigilados más los `id` alcanzables por `replaces`/`replacedBy` (unos 2–3 000 registros, menos de 2 MB). Lo genera `scripts/actualizar_fixtures.py`, que se puede volver a ejecutar.
- **Parser**: tabla de casos con los formatos reales de 1.1. Test lento opcional (`-m lento`) que parsea las 81 478 referencias del dataset completo y exige que solo fallen las `Guide` e IWA conocidas.
- **Resolver y validación**: con el extracto, las 100 entradas dan el resultado de la sección 1.2 (98 encontradas, 30303/30304 no encontradas, 22301:2012 superada, 9126 anulada y sustituida por 25010…). Es un test *golden* sobre `validacion.json`.
- **Diff**: transiciones simuladas sobre datos reales. La 22301 con el CD 93606 pasa a 60.60 y la 2019 a 95.99 → exactamente un `edicion_nueva`. 24708 a 95.99 sin sustituto → `anulacion`. 13249-1 de 90.20 a 90.93 → `confirmada`.
- **Idempotencia**: ejecutar dos veces seguidas no produce eventos ni Issues nuevos (el cliente de GitHub se sustituye por un falso en los tests).
- **Fallos**: quitar un campo, un JSONL vacío, un entregable desaparecido o un HTTP 500 → excepción, nunca "sin cambios".
- **Web**: *snapshot* de los Markdown generados y `zensical build` sin errores en la CI.
- **BOE (fase 2)**: los XML reales ya guardados (anuladas de agosto de 2026, información pública) más uno de aprobadas.

## 11. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| ISO mueve el Blob o lo protege con Cloudflare | Fallo ruidoso con un Issue `fallo-fuente`; la URL está en la configuración; el Parquet y el CSV sirven de alternativa. |
| El dataset no se actualiza a diario | Detección por `sha256` más el aviso de fuente desactualizada; la web muestra la fecha del dato, no solo la de ejecución. |
| Falsa "sustitución" por leer `replacedBy` sin mirar la etapa | Regla de 4.3 y tests específicos (caso 22301). |
| Ruido de Issues en series grandes | Pregunta 1 más la guarda antirruido. |
| Cambios de prefijo o tipo rompen el emparejamiento | Emparejar por número y parte, y seguir cadenas por `id`. |
| Zensical 0.x rompe algo al actualizar | Versión exacta fijada, build en CI y alternativa con Material 9.7.7 fijado. |
| Cron impuntual o desactivado | La hora da igual (datos diarios); *keepalive* cada 45 días más `enable` explícito. |
| Fechas engañosas (el dataset no trae fecha de etapa) | Se muestra "detectado el", y en Acerca de se explica. |
| BOE: cambia el formato o los títulos | Patrón de título más validación de las columnas de la tabla. Si una resolución candidata no se puede parsear, fallo ruidoso. |
| Lectores que lo tomen por fuente oficial | Barra fija "fuente no oficial", más Acerca de, más el README. |

## 12. Orden de trabajo propuesto

~~Fase 0~~ → ~~1a~~ → ~~corrección de `normas.yaml`~~ → 1b (**MVP publicado**) → 1c → fase 2.
Las fases 0 y 1a y la corrección de `normas.yaml` están hechas (2026-09-27).
