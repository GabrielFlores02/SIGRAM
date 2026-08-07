# Cobertura de datos y criterios - prototipo V1

## Fuentes auditadas

| Fuente | Resultado |
|---|---:|
| `data/raw/cohorte.parquet` | 1,185,657 filas y pacientes únicos |
| Cohorte 60+ con polifarmacia elegible | 733,564 pacientes |
| `data/raw/sigram.parquet` | 278,872,980 resultados |
| Pacientes de la cohorte con algún examen | 952,949 |
| Pacientes de la cohorte sin exámenes | 232,708 |
| `atenmed.parquet` | 10,801,766 atenciones con hasta tres CIE-10 |
| CIE-10 pseudonimizados en la muestra | 132 filas, 70 codigos, 10 pacientes |
| Catálogo médico V1 | 54 medicamentos y 97 criterios |
| Beers | 23 criterios |
| STOPP/START | 74 criterios |

## Estado de automatización

- 40 criterios tienen una primera regla automática determinística.
- 57 criterios necesitan contexto adicional, interpretación clínica o una
  regla que todavía debe validarse.
- La coincidencia con un medicamento del top no basta para declarar una
  alerta.
- Un criterio con datos incompletos se conserva en `criteria_report` y se
  deriva a `data_gaps`; el frontend lo oculta por defecto sin interpretarlo
  como negativo.

## Información potencialmente recuperable de `sigram.parquet`

La fuente contiene código y descripción de examen, analito, unidad, resultado,
rango de referencia, fecha y validación. Puede aportar creatinina/TFGe,
electrolitos, calcio, TSH/T4 y proteinuria si esos analitos están presentes.

En el Parquet local `FEC_RESULTADO` está almacenado como texto con formato
`DD/MM/YY`; las consultas DuckDB deben convertirlo explícitamente con
`try_strptime(FEC_RESULTADO, '%d/%m/%y')`.

Antes de usarlos en reglas se debe validar:

1. nombre/código institucional del analito;
2. unidad;
3. conversión de `VALOR_RESULT` desde texto a número;
4. fecha y selección del resultado clínicamente aplicable;
5. rango de referencia y estado `VALID_RESULT`.

## Información que no está estructurada en la base de exámenes

- caídas o fracturas;
- fragilidad;
- demencia, cognición o delirium;
- hipotensión ortostática y síncope;
- adherencia;
- indicación clínica y línea terapéutica;
- intensidad o tipo de dolor;
- expectativa de vida y objetivos de cuidado.

Desde 2026-08-05, los antecedentes con correspondencia directa se obtienen de
`atenmed.parquet` mediante un mapeo CIE-10 versionado. La ausencia de codigo no
se interpreta como ausencia de enfermedad. Gravedad, sintomas, mediciones y
variables funcionales siguen procediendo de otras fuentes o revision manual.
El API V1 permite ingresarlos opcionalmente en `clinical_context`, que tiene
prioridad sobre el mapeo automatico.

## Lectura del reporte por paciente

Cada ejecución publica el analisis completo en `criteria_report`, con:

- código, sistema y texto del criterio;
- medicamentos implicados;
- estado tecnico;
- versión y ubicación en el catálogo;
- `context_used`, `lab_evidence` y `diagnosis_evidence`;
- `triggering_evidence` con medicamentos, combinaciones y contexto aplicado;
- `protective_evidence`, `exception_status` y `exception_reason`;
- `recommended_actions` y advertencia de cobertura limitada al top V1;
- marca especial de adaptación Beers para pacientes de 60-64 años.

`clinical_findings` contiene solo alertas resueltas para la vista principal;
`data_gaps` y `manual_review_findings` alimentan la opcion "Ver mas".

`data_availability.medication_catalog_classification` devuelve para cada
farmaco activo su presentacion ESSI, nombre evaluado, grupo farmacologico y
codigos Beers/STOPP/START. El periodo clinico observable del piloto es todo el
ano calendario 2025.
La evidencia incluye su relacion temporal con la fecha indice y una marca si
fue posterior pero se utilizo por la regla anual retrospectiva.

La duracion y dosis se asocian al medicamento implicado. Los criterios de
combinacion comprueban primero la presencia de todos sus componentes, y los
protectores admitidos (por ejemplo IBP, antagonista H2, laxante o acido folico)
pueden modificar el resultado. Una ausencia dentro del top V1 obliga a revisar
la lista farmacologica completa.

El prototipo sigue siendo un tamizaje para validación; no debe utilizarse para
decisiones asistenciales.
