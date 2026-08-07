# Integracion frontend de resultados clinicos SIGRAM-AM

Fecha: 2026-08-07  
Contrato: backend V1 del piloto 2025

## Regla principal de presentacion

El backend envia el analisis completo para conservar trazabilidad. El frontend
no debe usar `criteria_report` directamente como tabla principal.

| Campo de la respuesta | Uso en frontend |
|---|---|
| `evaluation.clinical_findings` | Vista principal: alertas Beers y STOPP/START confirmadas |
| `evaluation.data_gaps` | Panel secundario "Requiere informacion adicional" |
| `evaluation.manual_review_findings` | Panel secundario "Requiere revision profesional" |
| `evaluation.criteria_report` | Vista tecnica completa bajo "Ver analisis completo" |
| `evaluation.alerts` | Alertas persistidas; filtrar DDInter con `analysis_system === "ddinter"` |

Por defecto se muestran `clinical_findings` y las alertas DDInter. No se deben
mostrar filas `no_alert`, `not_evaluable` o `manual_review` en la tabla
principal.

## Terminologia para el usuario

No mostrar el texto "No evaluable" al medico. Usar:

| Estado API | Etiqueta sugerida | Visibilidad inicial |
|---|---|---|
| `alert` | Alerta | Visible |
| `no_alert` | Sin hallazgo en los datos observados | Oculto |
| `not_evaluable` | Requiere informacion adicional | Oculto, dentro de "Ver mas" |
| `manual_review` | Requiere revision profesional | Oculto, dentro de "Ver mas" |

La ausencia de un criterio en `clinical_findings` no significa que el
medicamento sea seguro. Solo significa que no existe una alerta resuelta para
mostrar en la vista principal.

## Periodo y fecha indice

Mostrar siempre dos conceptos separados:

- `data_availability.medication_index_date`: fecha usada para determinar que
  medicamentos estaban activos.
- `clinical_observation_start_date` y `clinical_observation_end_date`: periodo
  retrospectivo usado para CIE-10 y examenes; en este piloto es todo 2025.

Texto sugerido:

> Medicamentos activos al: 29/12/2025. Evidencia clinica observada:
> 01/01/2025-31/12/2025.

## Evidencia posterior a la fecha indice

Cada evidencia mapeada puede incluir:

```json
{
  "medication_index_date": "2025-06-20",
  "temporal_relation_to_medication_index": "after_index",
  "used_under_pilot_full_year_rule": true
}
```

Valores posibles en laboratorios:

- `before_index`;
- `on_index`;
- `after_index`;
- `medication_index_not_provided`.

Valores posibles en diagnosticos:

- `before_or_on_index`;
- `after_index`;
- `spans_index`;
- `medication_index_not_provided`.

Si `used_under_pilot_full_year_rule` es `true`, mostrar una insignia discreta:

> Evidencia posterior a la fecha indice, considerada por la regla anual del
> piloto 2025.

No ocultar esta marca dentro del detalle de una alerta, porque permite al
medico decidir si la evidencia posterior debe mantener o no el hallazgo.

## Presentacion ESSI y agrupacion farmacologica

Usar `data_availability.medication_catalog_classification`. Cada elemento
contiene:

```json
{
  "essi_presentation": "DICLOFENACO SODICO 25 MG / ML X 3 ML",
  "evaluation_name": "DICLOFENACO",
  "matched_top_v1": true,
  "catalog_medication": "DICLOFENACO SODICO 25 MG / ML X 3 ML",
  "pharmacologic_group": "Antiinflamatorio no esteroideo (AINE)",
  "beers_codes": ["B05", "B06", "B07", "B08"],
  "stopp_codes": ["STOPP-H1", "STOPP-H2", "STOPP-H3", "STOPP-H7"],
  "start_codes": ["START-F3"]
}
```

En la interfaz, presentar primero `essi_presentation` y debajo el grupo. El
nombre normalizado es trazabilidad tecnica, no el nombre principal para el
medico.

Si `matched_top_v1` es `false`, mostrar "Sin agrupacion validada en el top V1"
y no inferir una clase farmacologica desde texto libre.

El catalogo completo esta disponible en:

```text
GET /api/catalog/v1/medications
```

## Flujo recomendado

```javascript
const response = await fetch(
  `/api/pilot/v1/sample-patients/${patientCode}/evaluate`,
  { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }
).then(r => r.json());

const evaluation = response.evaluation;

const beers = evaluation.clinical_findings.filter(
  item => item.system === "beers"
);
const stoppStart = evaluation.clinical_findings.filter(
  item => item.system === "stopp_start"
);
const ddinter = evaluation.alerts.filter(
  item => item.analysis_system === "ddinter"
);

const additionalData = evaluation.data_gaps;
const manualReview = evaluation.manual_review_findings;
const fullTechnicalReport = evaluation.criteria_report;
```

## Estructura visual recomendada

1. Encabezado con fecha indice y periodo observable.
2. Lista de medicamentos activos con presentacion ESSI y grupo.
3. Tres tarjetas: Beers, STOPP/START y DDInter.
4. Tabla principal construida con `clinical_findings` y DDInter.
5. Boton "Ver mas" con contadores:
   - `data_gaps.length`;
   - `manual_review_findings.length`;
   - criterios sin hallazgo, derivados desde `criteria_report` si se requieren.
6. Dentro del detalle, evidencia, protectores, excepciones, acciones y relacion
   temporal respecto a la fecha indice.

## Compatibilidad con ejecuciones anteriores

Las propiedades derivadas se calculan al responder la API. Por ello funcionan
tambien al consultar ejecuciones antiguas mediante:

```text
GET /api/cases/{case_id}/results
GET /api/executions/{execution_id}
```

No es necesario modificar ni eliminar la base SQLite existente.

## Advertencia funcional

Este es un tamizaje de investigacion. El frontend no debe ofrecer acciones de
prescripcion automatica ni presentar una alerta como diagnostico confirmado.
