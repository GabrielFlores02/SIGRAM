# Backend V1 - SIGRAM-AM

Backend FastAPI para registrar casos simulados, ejecutar evaluaciones determinísticas y persistir alertas trazables.

> No está validado para decisiones clínicas reales.

## Stack

- FastAPI y Uvicorn
- Pydantic v2
- SQLAlchemy 2.0 y SQLite
- Pytest

## Capas

```text
backend/app/
|-- api/             endpoints
|-- models/          entidades SQLAlchemy
|-- schemas/         contratos Pydantic
|-- services/        motor, normalización y proveedores
|-- repositories/    persistencia
|-- config.py        configuración
`-- main.py          aplicación FastAPI
```

## Evaluación actual

La respuesta expone `analysis_results` con tres sistemas:

| Sistema | Estado | Comportamiento actual |
|---|---|---|
| Beers | `active_v1_screening_catalog` | Evalúa el top médico V1 y marca adaptación en pacientes de 60-64 años. |
| STOPP/START | `active_v1_screening_catalog` | Evalúa reglas V1 y conserva STOPP/START como subtipos distintos. |
| DDInter | `active_local_legacy_catalog` | Consulta los ocho CSV locales y genera alertas conocidas. |

La ejecución publica el analisis completo en `criteria_report`. Para la vista
principal, el frontend usa `clinical_findings`; `data_gaps` y
`manual_review_findings` quedan disponibles bajo "Ver mas". Un dato ausente
nunca se convierte en un resultado negativo.

Cada resultado incluye evidencia activadora, medicamentos protectores,
estado/razon de la excepcion y acciones recomendadas. Las reglas de combinacion
comprueban primero que los dos medicamentos o grupos requeridos esten presentes;
los IBP, antagonistas H2, laxantes y acido folico se reconocen como protectores
cuando el criterio correspondiente los admite.

El motor conserva además reglas técnicas de polifarmacia, duplicidad y combinaciones sintéticas para regresión de la PoC. No deben confundirse con los tres análisis clínicos.

## DDInter local

`DDInterCsvProvider`:

- lee `data/raw/ddinter2/ddinter_downloads_code_*.csv` sin modificarlos;
- canoniza y deduplica pares;
- mapea Major/Moderate/Minor a alta/moderada/advertencia;
- excluye `Unknown` por defecto;
- usa alias provisionales de `data/mappings/ddinter_name_aliases.csv`;
- registra IDs, nivel y archivos de origen en `trace_data`.

Los CSV no incluyen el texto detallado de mecanismo o manejo. Por eso la recomendación del backend es genérica y exige confirmación profesional.

## Configuración

```env
DDINTER_DATA_DIR=data/raw/ddinter2
DDINTER_ALIAS_FILE=data/mappings/ddinter_name_aliases.csv
DDINTER_INCLUDE_UNKNOWN=false
CLINICAL_CATALOG_FILE=data/catalogs/v1/clinical_catalog_v1.json
PILOT_COHORT_FILE=data/raw/cohorte.parquet
PILOT_LABS_FILE=data/raw/sigram.parquet
PILOT_OBSERVATION_YEAR=2025
PILOT_LAB_LOOKBACK_DAYS=365
PILOT_DIAGNOSES_FILE=docs/ESTUDIO DE polifarmacia de referencia/6.1 polifarmacia/bd_limpia_polifarmacia/data_analitica_limpia/atenmed.parquet
CIE10_CONTEXT_MAPPING_FILE=data/mappings/cie10_clinical_context_v1.json
PILOT_DIAGNOSIS_LOOKBACK_DAYS=365
```

## Endpoints V1

- `GET /api/catalog/v1/summary`
- `GET /api/catalog/v1/medications`
- `GET /api/catalog/v1/criteria?system=beers`
- `GET /api/pilot/v1/sources`
- `GET /api/pilot/v1/sample-patients`
- `POST /api/pilot/v1/sample-patients/{patient_code}/evaluate`
- `POST /api/cases`
- `POST /api/cases/{case_id}/evaluate`

## Comandos

```powershell
.venv-local\Scripts\python.exe -m pip install -r backend\requirements.txt
.venv-local\Scripts\python.exe -m pytest backend\tests -v
.\scripts\start_backend.ps1
```

Swagger: `http://127.0.0.1:8000/docs`

La muestra V1 se puede probar sin preparar payloads manuales:

```powershell
.venv-local\Scripts\python.exe scripts\try_sample_patients.py --list
.venv-local\Scripts\python.exe scripts\try_sample_patients.py --patient-code PILOT-011DA2C70400CA24
.venv-local\Scripts\python.exe scripts\try_sample_patients.py --patient-code CODIGO_ACTUAL --index-date 2025-06-15
```

La muestra incluye `sample_diagnoses_2025.parquet`, derivado de
`atenmed.parquet`: 132 registros CIE-10, 70 codigos distintos y cobertura para
los 10 pacientes. `DiagnosisContextService` usa todos los codigos aceptados del
ano calendario 2025 como evidencia positiva. La ausencia de un codigo nunca se
interpreta como ausencia de enfermedad.

## Limitaciones pendientes

- El catálogo V1 cubre sólo el top de 54 medicamentos, no el universo farmacológico.
- La muestra aplica retrospectivamente en todo 2025 solo TFG reportada
  directamente, potasio, sodio, TSH, T4 libre con rango propio y proteinuria de
  24 horas, mediante identidades ESSI y unidades permitidas. El significado de
  `VALID_RESULT` requiere validación institucional.
- CIE-10 completa antecedentes directos como artrosis u osteoporosis. Los
  diagnosticos generales no sustituyen gravedad, sintomas ni mediciones: por
  ejemplo, `N18` no reemplaza TFGe e `I50` no prueba fraccion de eyeccion.
- Caidas y cognicion pueden completarse solo con evidencia CIE-10 positiva
  permitida. Fragilidad, hipotension ortostatica, adherencia e indicacion no
  estan estructuradas en `sigram.parquet` y requieren otra fuente o captura.
- El crosswalk ESSI-ATC-DDInter es provisional.
- La persistencia de alertas debe consolidarse en una sola transacción antes de procesamiento masivo.
- El frontend está pendiente.
