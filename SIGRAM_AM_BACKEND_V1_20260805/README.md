# SIGRAM-AM - prototipo V1

Documentacion tecnica completa del backend:
[`docs/backend/DOCUMENTACION_BACKEND.md`](docs/backend/DOCUMENTACION_BACKEND.md).

SIGRAM-AM es una prueba de concepto de soporte a la revisión farmacoterapéutica en adultos de 60 años o más con polifarmacia.

> **Advertencia:** el software aún no está validado para tomar decisiones clínicas. Los resultados son tamizajes y requieren revisión profesional.

## Alcance confirmado del piloto

- Periodo: 2025.
- Población: pacientes de 60+ con polifarmacia.
- Definición reproducible inicial: al menos cinco medicamentos únicos activos el mismo día (polifarmacia simultánea).
- Tres salidas independientes: Beers, STOPP/START y DDInter.
- Beers y STOPP/START: catálogo V1 reducido a los 54 medicamentos priorizados por el equipo médico.
- DDInter: activo de forma provisional con los ocho CSV locales A, B, D, H, L, P, R y V.

Beers 2023 fue diseñado para 65+. Su aplicación a pacientes de 60-64 se registrará como una adaptación del protocolo y el sistema conservará el estrato 65+ para trazabilidad y análisis de sensibilidad.

## Estado actual

El backend FastAPI/SQLAlchemy/SQLite permite crear casos simulados, añadir contexto clínico opcional, evaluarlos y persistir alertas. La respuesta incluye `analysis_results` y `criteria_report`:

- `beers`: `active_v1_screening_catalog`;
- `stopp_start`: `active_v1_screening_catalog`;
- `ddinter`: `active_local_legacy_catalog`.

`criteria_report` conserva el analisis tecnico completo. El frontend debe usar
`clinical_findings` como vista principal y dejar `data_gaps` y
`manual_review_findings` bajo "Ver mas". Un dato ausente nunca se convierte en
un criterio negativo.
El catálogo V1 contiene 23 criterios Beers y 74 STOPP/START vinculados a los
54 medicamentos del top médico. De los 97 criterios, 40 tienen una primera
regla automática y 57 aún dependen de contexto o revisión clínica. Los
resultados exponen evidencia activadora, protectores, excepciones y acciones.

DDInter se consulta localmente, sin servicios externos. Los pares se canonizan y deduplican; `Unknown` se excluye por defecto. El mapeo español-inglés disponible es provisional y debe validarse contra el maestro institucional/ATC.

## Datos ya disponibles

## Despliegue Rebagliati 2025

La configuración de Docker de la raíz despliega la cohorte completa de
Rebagliati 2025. Monta la carpeta
`../SIGRAM_Rebagliati_2025_Entrega_Desarrollador` como solo lectura y consulta
los Parquet con DuckDB, filtrando siempre por `patient_code`. El endpoint del
directorio es paginado: `GET /api/pilot/v1/sample-patients?offset=0&limit=50`
y admite `query=REB-000001`.

No se cargan en memoria los 6,012,673 despachos ni los 19,623,893 laboratorios.
Para ejecutar sin Docker, copie `.env.rebagliati.example` a `.env` desde esta
carpeta. Por indicación clínica posterior se habilitan Beers, STOPP/START y
DDInter como tamizajes de investigación. Las reglas sin contexto suficiente se
reportan como no evaluables o sujetas a revisión profesional.

La ausencia de filas de laboratorio se conserva como ausencia de registro, no
como un resultado normal. Los resultados siguen siendo tamizajes de
investigación y no decisiones clínicas.

`data/raw/cohorte.parquet` contiene 1,185,657 pacientes únicos de 60+.
Al cruzarla con la elegibilidad previa de polifarmacia quedan 733,564
pacientes para el piloto. `data/raw/sigram.parquet` contiene 278,872,980
resultados de exámenes; 952,949 pacientes de la cohorte tienen al menos un
resultado y 232,708 no tienen ninguno.

`atenmed.parquet` contiene 10,801,766 atenciones con hasta tres CIE-10
normalizados. La muestra del backend incluye 132 registros diagnosticos, 70
codigos distintos y cobertura para sus 10 pacientes pseudonimizados.

- Plan de datos y brechas: [`docs/pilot/piloto_2025_plan_datos.md`](docs/pilot/piloto_2025_plan_datos.md)
- SQL local e incremental ESSI: [`docs/sql/piloto_2025/README.md`](docs/sql/piloto_2025/README.md)
- Diccionarios ESSI: [`docs/references/essi_diccionarios/README.md`](docs/references/essi_diccionarios/README.md)
- Arquitectura: [`docs/architecture/arquitectura_poc.md`](docs/architecture/arquitectura_poc.md)
- Cobertura V1 y datos faltantes: [`reports/v1_criteria_data_coverage.md`](reports/v1_criteria_data_coverage.md)
- Catálogo derivado versionado: [`data/catalogs/v1/README.md`](data/catalogs/v1/README.md)

## Backend

```powershell
.venv-local\Scripts\python.exe -m pip install -r backend\requirements.txt
.venv-local\Scripts\python.exe -m pytest backend\tests -v
.\scripts\start_backend.ps1
```

API: `http://127.0.0.1:8000`  
Swagger: `http://127.0.0.1:8000/docs`

### Probar pacientes de la muestra

El backend ya puede listar y evaluar los 10 pacientes pseudonimizados de
`data/processed/v1_handoff/`. No mezcla todas las dispensaciones del aÃ±o:
selecciona por paciente el dÃ­a con mayor solapamiento de medicamentos del top
V1, usando fecha de despacho y duraciÃ³n.

- `GET /api/pilot/v1/sample-patients`: muestra casos, fecha Ã­ndice, nÃºmero de
  medicamentos simultÃ¡neos del top y filas de laboratorio disponibles.
- `POST /api/pilot/v1/sample-patients/{patient_code}/evaluate`: crea un caso
  simulado y ejecuta Beers, STOPP/START y DDInter. Acepta una `index_date`
  opcional de 2025; si no se envia usa el maximo solapamiento.

Desde PowerShell tambiÃ©n se puede probar sin levantar el servidor:

```powershell
.venv-local\Scripts\python.exe scripts\try_sample_patients.py --list
.venv-local\Scripts\python.exe scripts\try_sample_patients.py --patient-code PILOT-011DA2C70400CA24
```

GuÃ­a detallada: [`docs/pilot/probar_prototipo_backend.md`](docs/pilot/probar_prototipo_backend.md).

Si el entorno virtual copiado no inicia en otra máquina, debe recrearse; consulte `reports/environment_setup.md`.

## Entrega a otro desarrollador

La guía vigente de traspaso está en [`HANDOFF_V1.md`](HANDOFF_V1.md).

Se generó un paquete liviano en
`handoff/SIGRAM_AM_BACKEND_V1_20260805.zip`. Incluye código, pruebas,
documentación, DDInter, catálogo clínico y una muestra pseudonimizada; no
incluye los Parquet institucionales grandes. El archivo
`handoff/SIGRAM_AM_BACKEND_V1_20260805.sha256.json` permite verificar su
integridad.

Los tamaños y hashes de los Parquet necesarios para regenerar la cohorte están
en `reports/handoff_required_data_manifest.json`.

## Pendientes prioritarios

1. Validar con el médico la primera implementación de los 40 criterios automatizados, incluidos protectores, excepciones y el umbral operativo de AINE crónico.
2. Validar con ESSI/médico el mapeo V1 de laboratorios, el uso retrospectivo de
   todo 2025 y el significado de `VALID_RESULT`; ampliar analitos solo con evidencia.
3. Validar con el medico el mapeo CIE-10 V1. Los codigos pueden aportar algunos
   antecedentes, pero fragilidad, hipotension ortostatica, adherencia e
   indicacion todavia requieren otras fuentes o captura manual.
4. Probar la consulta de muestra con pocos pacientes y revisar falsos positivos y cobertura observable.
5. Validar el cruce medicamento ESSI -> principio activo/ATC -> DDInter.
6. Crear el frontend y efectuar validación clínica manual del piloto.
