# Entrega SIGRAM-AM V1

## Adenda CIE-10 y fecha indice 2026-08-05

- Se incorporo `atenmed.parquet` como fuente principal de diagnosticos ligados
  a atenciones.
- Se regenero la muestra con nuevos pseudonimos y se agrego
  `sample_diagnoses_2025.parquet`: 132 filas, 70 CIE-10 distintos y 10 pacientes.
- El mapeo es de evidencia positiva: la ausencia de codigo no crea falsos
  negativos y un diagnostico general no sustituye gravedad o mediciones.
- La API acepta una `index_date` opcional dentro de 2025.
- Se agrego logica explicita para combinaciones, medicamentos protectores y
  excepciones: la API devuelve evidencia activadora, proteccion encontrada,
  estado de excepcion y acciones recomendadas.
- B05 ya diferencia la duracion del AINE de la de otros medicamentos y detecta
  el riesgo de AINE con corticoide/anticoagulante/antiagregante.
- La suite actual tiene 113 pruebas aprobadas.

## Adenda de prueba local 2026-07-31

- Se agregaron endpoints para listar y evaluar los 10 pacientes
  pseudonimizados desde Swagger.
- La carga selecciona el episodio con mayor solapamiento temporal de
  medicamentos del top y no mezcla todas las dispensaciones de 2025.
- Se agrego `scripts/try_sample_patients.py` y la guia
  `docs/pilot/probar_prototipo_backend.md`.
- La suite de esa adenda tenia 96 pruebas aprobadas; el estado vigente es 109.
- Se probaron y persistieron localmente tres casos (IDs 5, 6 y 7); el caso 5
  produjo alertas en los tres sistemas.

Fecha de preparación: 2026-07-30.

## Estado entregado

- Backend/API FastAPI versión `1.0.0`.
- Tres análisis separados: Beers, STOPP/START y DDInter.
- Catálogo clínico reducido: 54 medicamentos, 23 criterios Beers y 74
  STOPP/START.
- Reporte tecnico completo en `criteria_report` y vista principal de alertas en
  `clinical_findings`; las brechas quedan disponibles bajo "Ver mas".
- Clasificacion por farmaco activo: presentacion ESSI, grupo farmacologico y
  codigos Beers/STOPP/START asociados.
- Cohorte local validada: 733,564 pacientes de 60+ con polifarmacia.
- Muestra pseudonimizada de 10 pacientes preparada para revisar el prototipo.
- Suite automatizada vigente: 113 pruebas aprobadas.

## SQL ejecutado en la máquina de origen

1. `docs/sql/piloto_2025/01_reutilizar_cohorte_local.sql`
2. `docs/sql/piloto_2025/03_muestra_prototipo_v1.sql`

La consulta `02_essi_laboratorios_incrementales.sql` no se ejecutó porque es
Oracle/ESSI y los resultados ya están disponibles en
`data/raw/sigram.parquet`.

Resultados agregados de la ejecución:

| Control | Resultado |
|---|---:|
| Pacientes del piloto | 733,564 |
| Dispensaciones 2025 | 33,433,224 |
| Pacientes con dispensación | 733,564 |
| Códigos de medicamento | 1,005 |
| Diagnósticos/atenciones 2025 | 6,056,509 |
| Filas de medicamentos del top | 24,119,550 |
| Pacientes con al menos un medicamento del top | 731,919 |
| Pacientes de la muestra | 10 |
| Dispensaciones del top en la muestra | 260 |
| Medicamentos distintos del top en la muestra | 41 |
| Resultados de laboratorio 2025 en la muestra | 603 |
| Pacientes de la muestra con laboratorio 2025 | 9 |
| Registros CIE-10 de atenciones en la muestra | 132 |
| CIE-10 distintos en la muestra | 70 |
| Pacientes de la muestra con CIE-10 | 10 |

## Muestra preparada

Ubicación: `data/processed/v1_handoff/`.

- `sample_patients.parquet`: edad y sexo con código pseudonimizado.
- `sample_medications.parquet`: medicamentos priorizados y criterios
  asociados.
- `sample_labs_2025.parquet`: exámenes crudos de 2025 sin solicitud, centro ni
  identificador institucional.
- `sample_diagnoses_2025.parquet`: fecha de atencion, posicion y CIE-10
  normalizado, derivado de `atenmed.parquet` sin identificador institucional.
- `sample_criterion_reports.json`: primera ejecución Beers/STOPP-START.
- `sample_summary.csv`: conteos por paciente para revisión rápida.
- `manifest.json`: tamaño y SHA-256 de cada archivo.

La sal aleatoria usada para pseudonimizar se destruyó al terminar la ejecución.
No existe una tabla de reversión dentro del proyecto. Aun así, son datos
clínicos pseudonimizados y sólo deben compartirse dentro del entorno de
investigación autorizado.

## Resultado vigente de los 10 casos

- 20 alertas clinicas visibles: 12 Beers y 8 STOPP/START.
- Dentro de STOPP/START: 5 STOPP y 3 START.
- `clinical_findings` contiene 20 alertas visibles; `criteria_report` conserva
  tambien `no_alert`, `not_evaluable` y `manual_review` para auditoria.
- Cada medicamento activo conserva presentacion ESSI y grupo farmacologico.

Estos valores fueron regenerados con el periodo clinico observable completo de
2025 y la fecha indice para seleccionar los medicamentos activos. Sirven para
depuración, no para conclusiones clínicas. El backend
conserva el texto crudo y aplica solo los mapeos V1 aceptados: TFG directa,
potasio, sodio, TSH, T4 libre con rango propio y proteinuria de 24 horas. Cada
valor aplicado conserva fecha, unidad, fila fuente, hash y advertencias.

## Preparar el entorno en la nueva máquina

No copiar ni reutilizar `.venv`: los entornos virtuales contienen rutas de la
máquina donde se crearon.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Iniciar el backend:

```powershell
.\scripts\start_backend.ps1
```

- API: `http://127.0.0.1:8000`
- Swagger: `http://127.0.0.1:8000/docs`

## Verificaciones reproducibles

```powershell
.\.venv\Scripts\python.exe scripts\verify_handoff_v1.py
.\.venv\Scripts\python.exe scripts\audit_v1_sources.py
.\.venv\Scripts\python.exe scripts\prepare_handoff_v1.py
```

`prepare_handoff_v1.py` vuelve a generar los pseudónimos, por lo que los
códigos de paciente cambiarán en cada ejecución.

## Datos grandes requeridos para regenerar todo

Los siguientes archivos contienen información institucional y no deben
enviarse por correo, repositorios públicos ni servicios no autorizados:

- `data/raw/cohorte.parquet`
- `data/raw/sigram.parquet`
- farmacia 2025 S1/S2 del estudio de polifarmacia;
- `atenmed.parquet`;
- `maestra_paciente_servicio_2025_elegible.parquet`.

Sus tamaños y hashes quedan en
`reports/handoff_required_data_manifest.json`. La copia debe hacerse por el
canal institucional y verificarse antes de ejecutar nuevamente los SQL.

## Trabajo recomendado con el médico

1. Revisar primero los 34 tamizajes de la muestra.
2. Revisar las alertas visibles y la cobertura de datos agregada sin presentar
   filas `not_evaluable` al medico.
3. Validar la homologacion V1 de laboratorios, `VALID_RESULT` y el uso
   retrospectivo de todo el ano 2025.
4. Definir cómo obtener caídas, fragilidad, cognición, hipotensión
   ortostática, adherencia e indicación.
5. Ajustar reglas y excepciones antes de aumentar la muestra.
6. No usar el prototipo para decisiones asistenciales.
