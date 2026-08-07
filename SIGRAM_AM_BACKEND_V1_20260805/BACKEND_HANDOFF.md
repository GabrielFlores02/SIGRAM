# Entrega del backend SIGRAM-AM V1

Documentacion tecnica completa:
`docs/backend/DOCUMENTACION_BACKEND.md`.

Paquete actualizado: 2026-08-05.

## Contenido

- Backend FastAPI y 113 pruebas automatizadas.
- Catalogo V1: Beers y STOPP/START para los 54 medicamentos priorizados.
- Ocho archivos locales DDInter y sus alias provisionales.
- Muestra pseudonimizada de 10 pacientes, con 132 registros CIE-10 de
  `atenmed.parquet` y 603 resultados de laboratorio.
- Endpoints para listar y evaluar la muestra.
- Scripts de arranque y prueba.

No se incluyen `cohorte.parquet`, `sigram.parquet`, otros datos institucionales
grandes, la base SQLite local ni entornos virtuales.

## Instalacion en otra maquina

Requiere Python 3.12. Desde la carpeta extraida:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe -m pytest backend\tests -q
.\scripts\start_backend.ps1
```

Abrir `http://127.0.0.1:8000/docs`.

## Prueba rapida

```powershell
.\.venv\Scripts\python.exe scripts\try_sample_patients.py --list
.\.venv\Scripts\python.exe scripts\try_sample_patients.py `
  --patient-code PILOT-011DA2C70400CA24
```

En Swagger tambien se puede usar:

- `GET /api/pilot/v1/sample-patients`
- `POST /api/pilot/v1/sample-patients/{patient_code}/evaluate`

El POST admite `index_date` opcional (`AAAA-MM-DD`) para evaluar cualquier dia
de 2025 con medicamentos del top activos. Si se omite, usa el dia de maximo
solapamiento.

La respuesta separa Beers, STOPP/START y DDInter en
`evaluation.analysis_results`.

`evaluation.criteria_report` conserva el analisis tecnico completo.
`evaluation.clinical_findings` contiene las alertas que el frontend debe
mostrar por defecto; `data_gaps` y `manual_review_findings` quedan disponibles
bajo "Ver mas".
`data_availability.medication_catalog_classification` conserva para cada
farmaco activo su presentacion ESSI, grupo y codigos Beers/STOPP/START.
La evidencia indica si ocurrio antes, en o despues de la fecha indice.
La ausencia de un protector se etiqueta como limitada al top V1 y debe
confirmarse con la lista farmacologica completa.

## Advertencias

- Prototipo de investigacion; no usar para decisiones asistenciales.
- Los laboratorios reconocidos de la muestra alimentan el contexto y las reglas
  con trazabilidad. Se aceptan TFG reportada directamente, potasio, sodio, TSH,
  T4 libre con rango de referencia y proteinuria de 24 horas; los demas se
  rechazan o quedan pendientes de homologacion.
- El uso retrospectivo de todo el ano calendario 2025 y la semantica de
  `VALID_RESULT` deben validarse con el equipo clinico/ESSI.
- Los CIE-10 de `atenmed.parquet` se usan solo como evidencia positiva. Ausencia
  de codigo no significa ausencia de antecedente; diagnosticos generales no
  sustituyen gravedad, sintomas o mediciones exigidas por el criterio.
- Caidas, fragilidad, cognicion, hipotension ortostatica, adherencia e
  indicacion requieren entrada manual.
- Un cero DDInter no prueba ausencia de interacciones: la homologacion de
  nombres y la cobertura de grupos son provisionales.
- Para consultar cualquier paciente institucional se deben transferir los
  Parquet grandes por un canal autorizado e implementar el endpoint de consulta.
