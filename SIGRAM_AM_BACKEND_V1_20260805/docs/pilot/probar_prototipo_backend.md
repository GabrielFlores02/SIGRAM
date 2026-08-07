# Probar el prototipo con pacientes de la muestra

Fecha de verificacion: 2026-08-05.

> El prototipo es un tamizaje de investigacion. No esta validado para tomar
> decisiones asistenciales.

## 1. Arrancar el backend

El `.venv` copiado inicialmente no funciona en esta maquina porque conserva
la ruta de Python de otro disco. Se creo `.venv-local`, se instalaron las
dependencias declaradas y se verifico la suite automatizada.

Desde la raiz del proyecto:

```powershell
.\scripts\start_backend.ps1
```

Abrir `http://127.0.0.1:8000/docs`.

## 2. Probar desde Swagger

1. Ejecutar `GET /health`; debe responder `status: ok`.
2. Ejecutar `GET /api/pilot/v1/sources`; confirma cohorte, laboratorios y
   catalogo local.
3. Ejecutar `GET /api/pilot/v1/sample-patients`.
4. Copiar un `patient_code`.
5. Ejecutar `POST /api/pilot/v1/sample-patients/{patient_code}/evaluate`.
   Se puede enviar cuerpo vacio.
6. Revisar `evaluation.analysis_results`, que separa `beers`, `stopp_start` y
   `ddinter`.
7. Usar `evaluation.clinical_findings` como vista principal. Abrir
   `data_gaps`, `manual_review_findings` y `criteria_report` solo bajo "Ver mas".
8. Revisar `data_availability`: fecha indice, numero de medicamentos cargados,
   `mapped_lab_fields`, `mapped_diagnosis_fields`, periodo observable 2025 y
   `medication_catalog_classification`.

La guia exacta para el frontend esta en
`docs/frontend/INTEGRACION_RESULTADOS_CLINICOS.md`.

Para elegir otra fecha indice de 2025:

```json
{
  "index_date": "2025-06-15",
  "clinical_context": {}
}
```

Si ese dia no hay medicamentos del top V1 activos, la API devuelve HTTP 422.

Para aportar datos revisados manualmente por el medico, usar por ejemplo:

```json
{
  "clinical_context": {
    "egfr_ml_min_1_73m2": 25,
    "falls_history": true,
    "frailty_status": "fragil",
    "cognitive_impairment": false,
    "orthostatic_hypotension": true,
    "adherence_known": true,
    "indication_confirmed": true
  }
}
```

Cada llamada crea un nuevo caso simulado, por lo que se pueden comparar
resultados con y sin contexto. El `case_id` queda en la respuesta y el ultimo
resultado se consulta con `GET /api/cases/{case_id}/results`.

## 3. Probar desde PowerShell

Listar los 10 pacientes:

```powershell
.venv-local\Scripts\python.exe scripts\try_sample_patients.py --list
```

Evaluar un paciente:

```powershell
.venv-local\Scripts\python.exe scripts\try_sample_patients.py --patient-code CODIGO_OBTENIDO_CON_LIST
```

Evaluar varios:

```powershell
.venv-local\Scripts\python.exe scripts\try_sample_patients.py `
  --patient-code PILOT-011DA2C70400CA24 `
  --patient-code PILOT-08C4AA4597AE690A `
  --patient-code PILOT-0FF5A104DC7B3852
```

Agregar contexto manual:

```powershell
.venv-local\Scripts\python.exe scripts\try_sample_patients.py `
  --patient-code PILOT-011DA2C70400CA24 `
  --context-json '{"egfr_ml_min_1_73m2":25,"falls_history":true}'
```

Elegir fecha indice:

```powershell
.venv-local\Scripts\python.exe scripts\try_sample_patients.py `
  --patient-code CODIGO_OBTENIDO_CON_LIST `
  --index-date 2025-06-15
```

## 4. Codigos pseudonimizados

Ejecutar siempre `--list` para obtener los codigos vigentes. Al regenerar la
muestra se crea una nueva sal aleatoria y cambian los valores `PILOT-...`; esto
impide conservar una tabla reversible hacia el identificador institucional.

## 5. Interpretacion y limites

- Si no se envia `index_date`, se elige por maximo solapamiento de
  dispensaciones del top V1. Si se envia, se reconstruyen los medicamentos
  activos en esa fecha. En ambos casos, el piloto usa retrospectivamente los
  laboratorios y CIE-10 aceptados de todo 2025.
- La cohorte completa define polifarmacia con todos los medicamentos. La
  muestra entregada contiene solamente medicamentos del top de 54, por lo que
  puede mostrar menos de cinco aunque el paciente sea elegible.
- El backend aplica solo laboratorios de identidad ESSI y unidad reconocidas:
  TFG reportada directamente, potasio, sodio, TSH, T4 libre cuando trae rango
  interpretable y proteinuria de 24 horas. Toma el ultimo valor aceptado entre
  2025-01-01 y 2025-12-31; un valor manual enviado por el medico tiene
  prioridad. La evidencia queda en `mapped_lab_fields`, `lab_provenance` y en
  cada criterio que haya utilizado el campo.
- No calcula TFG desde creatinina ni interpreta calcio total, microalbuminuria o
  creatinina urinaria como sustitutos. La muestra actual no contiene TFG
  directa, aunque el Parquet completo si la contiene.
- Los antecedentes se obtienen principalmente de `sample_diagnoses_2025.parquet`,
  generado desde `atenmed.parquet`. Solo se infieren condiciones positivas con
  mapeo explicito. La ausencia de CIE-10 no se interpreta como ausencia de
  enfermedad.
- Un CIE-10 general no sustituye datos mas especificos: `N18` no reemplaza
  TFGe, `I50` no determina sintomas o fraccion de eyeccion, `J44` no determina
  gravedad y `N40` no confirma sintomas urinarios.
- Caidas, fragilidad, cognicion, hipotension ortostatica, adherencia e
  indicacion siguen siendo entradas manuales.
- Un cero en DDInter no demuestra ausencia de interacciones: tambien puede
  indicar que falta el alias ESSI-DDInter o que el farmaco no esta en los ocho
  grupos locales.
- Beers y STOPP/START cubren solo el catalogo V1 priorizado, no el universo de
  medicamentos.
- El motor START necesita revision adicional para detectar omisiones sin
  depender de que el medicamento candidato ya este presente.
