# Acerca de

!!! warning "No es una fuente oficial"
    Esta web la mantiene un opositor para ayudar a otros opositores. Puede contener errores y los datos llegan con retraso. Antes de dar nada por seguro, consulta [ISO](https://www.iso.org) o [UNE](https://www.une.org).

## Qué hace

Cada día descarga los metadatos públicos de las normas ISO y comprueba si alguna de las normas del temario ha cambiado: una edición nueva, una revisión en marcha o una anulación. También lee el BOE para saber qué versión española (UNE) está vigente, si adopta la edición ISO actual y si hay una nueva en preparación.

Solo se muestran metadatos públicos: código, título, estado y fechas. El contenido de las normas está protegido por derechos de autor y no se reproduce aquí.

## Fuentes y atribución

- **ISO Open Data**, dataset *ISO deliverables metadata*, © ISO, publicado con licencia [Open Data Commons Attribution License (ODC-By) 1.0](https://opendatacommons.org/licenses/by/1-0/). Fuente: <https://www.iso.org/open-data.html>. Los títulos oficiales, las etapas y las relaciones entre ediciones proceden de este dataset.
- **[Boletín Oficial del Estado](https://www.boe.es/datosabiertos/)** (API de datos abiertos), para las normas UNE. Cada mes el BOE publica la relación de normas UNE aprobadas (con la norma a la que sustituyen), la de anuladas y los proyectos en información pública. La web las lee desde el año 2000; los anexos anteriores a 2004, más o menos, son imágenes escaneadas y no se pueden leer. Por eso una UNE aprobada antes solo se conoce si una posterior la sustituye o si se anula.

## Frecuencia de actualización

La web comprueba **cada día** (hacia las 7:15, hora peninsular) los datos de ISO y las normas UNE que publica el BOE. Los cambios quedan en el [historial](historial.md), y las ediciones nuevas, modificaciones y anulaciones generan un aviso.

- **ISO** no actualiza sus datos abiertos todos los días, así que un cambio puede tardar unos días en aparecer.
- **UNE**: el BOE publica cada mes la relación de normas aprobadas y anuladas del mes anterior, así que las normas UNE llegan con uno o dos meses de retraso sobre su aprobación. La web lee el BOE hasta el día anterior.

## Cómo leer las fechas

El dataset de ISO indica la etapa en la que está cada norma, pero no desde cuándo. Por eso las fechas del historial son las del día en que esta web **detectó** el cambio, no las del cambio real. Además, ISO no siempre actualiza el dataset a diario.

## Calidad de la lista de normas

La lista de normas se extrajo del temario y se revisó contra los datos de ISO. El [informe de validación](validacion.md) indica, para cada norma, si se encontró, cuál es su edición vigente y si la edición que cita el temario sigue en vigor.
