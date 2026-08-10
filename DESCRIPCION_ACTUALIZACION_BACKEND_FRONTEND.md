# SIGRAM-AM: descripción técnica de la versión actual

## 1. Alcance y versión de referencia

Este documento describe el estado integrado que se ejecuta desde la raíz del
proyecto mediante `compose.yaml`. La aplicación usa como backend activo
`SIGRAM_AM_BACKEND_V1_20260805`

y como cliente `frontend`.

La referencia anterior fue la entrega de julio de 2026: una aplicación de
casos simulados con catálogo clínico, evaluación Beers/STOPP-START y una
primera muestra piloto. La versión actual conserva ese núcleo, pero añade la
trazabilidad clínica basada en CIE-10, una vista de investigación/validación
de datos, una respuesta clínica más segura y un flujo de simulación que parte
de la historia pseudonimizada de los pacientes de prueba.

El sistema sigue siendo una **prueba de concepto de tamizaje**. No sustituye la
revisión farmacoterapéutica ni debe usarse para tomar decisiones clínicas
autónomas.

## 2. Arquitectura de ejecución

El archivo `compose.yaml` levanta dos servicios y un volumen persistente:

| Componente | Tecnología | Puerto local | Responsabilidad |
| --- | --- | --- | --- |
| Backend | FastAPI, SQLAlchemy y SQLite | `127.0.0.1:8001` | API, reglas clínicas, catálogos, muestra piloto y persistencia de casos simulados. |
| Frontend | React, TypeScript, Vite y Nginx | `127.0.0.1:8088` | Captura de casos, navegación, resultados, historial y validación metodológica. |
| Volumen `sigram_backend_data` | Docker volume | No expuesto | Conserva la base SQLite de casos y evaluaciones entre reinicios. |

El backend usa archivos versionados del paquete para el catálogo clínico,
alias de DDInter, mapeo CIE-10 y muestra pseudonimizada del piloto. Los
Parquet institucionales masivos no se requieren para levantar esta entrega:
la aplicación utiliza la muestra reducida situada en
`data/processed/v1_handoff/`.

## 3. Backend actual

### 3.1. Núcleo funcional conservado

El backend mantiene los flujos de la versión anterior:

- Crear y consultar casos simulados.
- Registrar medicamentos y contexto clínico opcional.
- Ejecutar análisis independientes de Beers, STOPP/START y DDInter.
- Persistir caso, medicamentos, ejecuciones de evaluación y alertas en SQLite.
- Exponer catálogo de medicamentos, criterios y resumen del catálogo.
- Servir documentación OpenAPI en `/docs`.

Los tres sistemas no se mezclan: Beers y STOPP/START trabajan con el catálogo
V1 de 54 medicamentos priorizados; DDInter consulta los ocho CSV locales de
interacciones y usa alias auditables para normalizar nombres.

### 3.2. Cambio principal: contexto clínico desde CIE-10

La versión anterior requería que varios antecedentes clínicos se consignaran
manualmente. La versión actual incorpora
`data/mappings/cie10_clinical_context_v1.json` y el servicio
`DiagnosisContextService` para comparar los códigos CIE-10 disponibles del
piloto con condiciones que las reglas pueden utilizar.

El mapeo no interpreta la ausencia de un CIE-10 como ausencia de enfermedad.
Si no hay evidencia suficiente, el criterio conserva su estado de información
incompleta. Esto evita mostrar como negativo un criterio que realmente no pudo
evaluarse.

La evidencia CIE-10 conserva, cuando existe, códigos coincidentes, conteo,
primera y última fecha de atención, campo clínico satisfecho, procedencia y
relación temporal respecto de los medicamentos. Por ello, condiciones como
deterioro cognitivo, caídas, insuficiencia cardiaca, enfermedad gastrointestinal
o renal pueden resolverse solo si la muestra contiene un CIE-10 o dato clínico
que respalde ese campo.

### 3.3. Periodo clínico y regla anual del piloto

La fecha índice de medicamentos se obtiene identificando el día de 2025 con
mayor solapamiento de dispensaciones del paciente. Para ello se consideran
fecha de despacho y duración, sin mezclar todas las dispensaciones del año.

Sin embargo, para el piloto el contexto clínico y de laboratorio se examina
retrospectivamente durante todo 2025:

- `clinical_observation_start_date`: `2025-01-01`.
- `clinical_observation_end_date`: `2025-12-31`.
- `medication_index_date`: fecha del episodio activo de medicamentos.

Una evidencia posterior a la fecha índice, pero dentro de 2025, queda marcada
con `temporal_relation_to_medication_index: "after_index"` y
`used_under_pilot_full_year_rule: true`. El frontend la comunica como evidencia
posterior incluida por la regla anual del piloto, en lugar de ocultarla o
presentarla erróneamente como evidencia contemporánea.

### 3.4. Contrato de resultados refinado

La respuesta de una evaluación contiene dos niveles:

1. **Vista clínica principal:** `evaluation.clinical_findings`. Es la fuente de
   la tabla de alertas visible al profesional.
2. **Trazabilidad completa:** `evaluation.criteria_report`, `data_gaps` y
   `manual_review_findings`. Incluye el análisis técnico de todos los criterios,
   incluidos los que no tienen hallazgo o que no pueden automatizarse.

Los estados se conservan para trazabilidad:

- `alert`: hallazgo según los datos observados.
- `not_evaluable`: faltan datos necesarios; el frontend lo traduce como
  **“Requiere información adicional”**.
- `manual_review`: precisa interpretación profesional.
- `no_alert`: sin hallazgo en los datos observados. Solo se muestra dentro del
  análisis completo, no como una falsa garantía clínica en la vista principal.

La salida incluye datos faltantes, evidencia activadora y protectora,
excepciones, acciones sugeridas, fuente, versión y cobertura farmacológica. La
clasificación `medication_catalog_classification` identifica la presentación
ESSI, grupo farmacológico y códigos Beers/STOPP/START asociados.

### 3.5. Nuevos endpoints del piloto

Además del `POST /api/pilot/v1/sample-patients/{patient_code}/evaluate`, la
versión actual incorpora:

| Endpoint | Uso |
| --- | --- |
| `GET /api/pilot/v1/sample-patients` | Lista los 10 pacientes pseudonimizados, edad, sexo, fecha índice, recuentos y máximo de medicamentos simultáneos. |
| `GET /api/pilot/v1/sample-patients/{patient_code}/research-data` | Devuelve filas de laboratorio y CIE-10 de origen, mapeos aceptados, exclusiones y advertencias para validación metodológica. No persiste un caso. |
| `GET /api/pilot/v1/sample-patients/{patient_code}/case-prefill` | Carga edad, sexo, diagnósticos CIE-10, contexto derivado y medicamentos activos para llenar “Nuevo caso”. No crea ni modifica registros. |
| `POST /api/pilot/v1/sample-patients/{patient_code}/evaluate` | Genera un caso simulado basado en la muestra y ejecuta los tres analizadores. |

El endpoint `case-prefill` es deliberadamente de solo lectura. Normaliza el
sexo para el formulario, agrupa los medicamentos que estaban activos en la
fecha índice, transfiere los valores de contexto derivados de laboratorios y
CIE-10, y conserva los campos de dosis/frecuencia/vía como “no estructurada”
cuando la historia de origen no los contiene.

## 4. Frontend actual

### 4.1. Navegación y separación de propósitos

El frontend mantiene dos secciones operativas principales:

- **Nuevo caso:** simulación y evaluación de una receta.
- **Historial:** solo registra los casos que ya se analizaron y sus resultados.

Las funciones de investigación se distinguen visualmente con el estilo morado:

- **Casos del piloto:** ejecuta los casos pseudonimizados existentes.
- **Validación de datos:** audita el material de origen y los mapeos realizados.

Se retiró del Historial el texto de “Registro de pruebas…”, porque la revisión
metodológica pertenece a Validación de datos, no al registro operativo.

### 4.2. Resultados clínicos y detalle técnico

La tabla principal usa `clinical_findings`; no presenta directamente el
`criteria_report` completo. Esto reduce ruido y evita que “sin alerta” se
interprete como una conclusión clínica absoluta.

El botón **Ver detalle** de un criterio expone estado, medicamento, datos
faltantes, evidencia de laboratorios y CIE-10, protectores, excepciones y
acciones. Un segundo bloque **Ver más** agrupa la justificación de evaluación,
fuente, versión, evidencia activadora y cobertura farmacológica. El análisis
completo también dispone de detalle por fila para que el médico pueda revisar
datos no observados, brechas o evidencia que el piloto pudo haber encontrado
fuera de la fecha índice.

DDInter se presenta por separado filtrando las alertas cuyo
`analysis_system` es `ddinter`; no se mezcla con criterios Beers o STOPP/START.

### 4.3. Validación de datos

La pestaña permite seleccionar un paciente pseudonimizado y consultar:

- Fecha índice y periodo clínico completo de 2025.
- Medicamentos activos en la fecha índice.
- Filas originales de laboratorio: fecha, ESSI, analito, valor, unidad, rango y
  estado de validación.
- Filas CIE-10 de origen.
- Campos aceptados por los mapeos de laboratorio y diagnóstico.
- Advertencias, exclusiones y conteos de registros rechazados.
- Catálogo de 54 medicamentos y catálogo de criterios Beers/STOPP/START.

En el catálogo de criterios, la columna **Tipo** muestra `STOPP` o `START`;
para Beers se usa una raya, pues no emplea esa clasificación.

### 4.4. Nuevo caso con historia pseudonimizada

Se añadió un desplegable al inicio de “Nuevo caso”. Incluye:

- **Crear paciente nuevo sin historial**, que deja el flujo habitual vacío.
- Los 10 pacientes pseudonimizados, identificados por código, edad, sexo y
  cantidad máxima de medicamentos activos.

Al elegir un paciente, el frontend consulta `case-prefill` y autocompleta solo
la información disponible: edad, sexo, diagnósticos, contexto clínico y
medicamentos históricos. Los valores no presentes se mantienen disponibles
para que el usuario los complete; no se inventan datos clínicos.

El formulario de la parte superior conserva el comportamiento original y está
reservado para **medicamentos nuevos**. El botón “Agregar” incorpora filas de
la prescripción que se desea simular. Debajo se muestra un bloque plegable
**Medicamentos en uso**, exclusivamente informativo, con los fármacos activos
provenientes de la historia pseudonimizada. No se editan como si fuesen parte
de la nueva receta.

Al enviar el caso, el frontend combina internamente medicamentos nuevos e
históricos para que el backend evalúe la polifarmacia real de la simulación.
El historial no se altera y el endpoint de precarga tampoco persiste datos.

### 4.5. Contexto clínico plegable

Para evitar que el formulario se llene de campos, “Contexto clínico” se divide
en dos desplegables:

- **Exámenes y datos clínicos realizados:** muestra valores cargados desde la
  historia, CIE-10 o laboratorios mapeados.
- **Exámenes y datos clínicos no realizados / no registrados:** concentra los
  campos pendientes que el profesional puede completar manualmente.

La clasificación se basa en si el campo tiene un valor disponible. Un valor
booleano “No” cuenta como dato registrado; no se confunde con dato ausente.

## 5. Diferencias resumidas respecto de la versión anterior

| Área | Antes | Ahora |
| --- | --- | --- |
| CIE-10 | No resolvía sistemáticamente condiciones clínicas del piloto. | Mapeo CIE-10 versionado, evidencia trazable y actualización de contexto. |
| Datos faltantes | Podían parecer ausencia de enfermedad. | Se conservan como información adicional requerida; no se convierten en resultado negativo. |
| Resultados | El reporte técnico podía mostrarse directamente. | `clinical_findings` guía la vista clínica; el análisis completo queda bajo detalle. |
| Periodo | Riesgo de interpretar todo el contexto como contemporáneo. | Fecha índice de medicamentos separada de la observación retrospectiva anual 2025. |
| Investigación | Sin una auditoría completa en una pantalla dedicada. | Validación de datos con fuentes, mapeos, exclusiones y catálogos. |
| Nuevo caso | Solo ingreso manual. | Selección de paciente pseudonimizado, precarga de historia y simulación de polifarmacia. |
| Medicación | No separaba receta nueva de tratamiento histórico. | Receta nueva arriba e historial de medicamentos en uso abajo, plegado y solo lectura. |
| Contexto | Todos los campos se desplegaban a la vez. | Datos realizados y pendientes organizados en dos desplegables. |

## 6. Operación local y límites

Para iniciar la versión actual se usa `run-local.ps1` o `docker compose up -d
--build`. La aplicación queda en `http://127.0.0.1:8088` y Swagger en
`http://127.0.0.1:8001/docs`.

Los resultados corresponden a un piloto de 2025 y una muestra de 10 pacientes
pseudonimizados. Siguen pendientes la validación clínica del mapeo CIE-10 y de
laboratorios, la validación institucional de nombres/ATC/DDInter y la revisión
profesional de cada hallazgo antes de cualquier uso clínico.
