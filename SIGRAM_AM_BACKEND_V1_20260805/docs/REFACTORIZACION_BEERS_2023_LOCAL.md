# Refactorización local de AGS Beers Criteria 2023

**Fecha:** 11 de agosto de 2026  
**Ámbito:** entorno local de desarrollo `sigram-am-dev` únicamente.  
**No realizado:** commit, push, cambio de GitHub, ni modificación del entorno estable accesible por el Dr. Armando.

## Objetivo

Separar la fuente normativa AGS Beers 2023, el catálogo operativo disponible y el resultado computado por paciente. La implementación evita presentar como hallazgo clínico automático aquello que exige interpretación profesional o para lo que el catálogo V1 no tiene datos suficientes.

## Fuentes revisadas

- `Documentos de Referencias/AGS_Beers_Criteria_2023.md`.
- Artículo PDF AGS Beers 2023 contenido en `Documentos de Referencias`.
- Catálogo operativo local `data/catalogs/v1/top_medications_v1.csv`.

No se modificó el catálogo CSV ni se declaró que reemplaza la fuente AGS. La cobertura sigue limitada al top local de medicamentos.

## Cambios de backend

### Modelo clínico y trazabilidad

- Se añadieron estados explícitos para Beers: `activated`, `not_evaluable`, `manual_review`, `no_alert` y `out_of_scope`.
- Los casos menores de 65 años se devuelven como `out_of_scope`; no se etiquetan como adaptación equivalente a la aplicación canónica de AGS Beers.
- Cada resultado Beers expone, cuando corresponde: fuente, año, versión, tabla/sección, categoría, formulación operativa, fundamento, tipo y texto de recomendación, calidad/fuerza de evidencia, excepciones, modo de automatización y si cuenta como hallazgo clínico.
- La salida distingue recomendaciones de evitar, usar con precaución, reducir dosis, clasificación de apoyo y revisión manual.
- Para Beers se vacía `recommended_actions`, evitando que el sistema presente acciones clínicas genéricas como si estuvieran validadas.
- Se añadió el campo clínico estructurado `tramadol_release_formulation` para diferenciar liberación inmediata y extendida.
- El resumen de análisis ahora contabiliza `out_of_scope_count` por separado.

### Reglas implementadas o endurecidas

| Código | Tratamiento aplicado |
|---|---|
| B01 | Pasa a `manual_review` hasta disponer de regla clínica validada; no genera alerta automática. |
| B02 | Identifica relajantes musculares esqueléticos, presenta `Evitar.` y permite `activated`. |
| B03 | Se conserva como clasificación de anticolinérgico fuerte; siempre es información de apoyo, no hallazgo clínico independiente. |
| B04 | Exige duración estructurada del IBP e indicación de mantenimiento; activa solo si supera 8 semanas sin indicación documentada. |
| B05 | Exige confirmación de alternativas más seguras ineficaces y conserva el estado de excepción/protección. |
| B06 | Diferencia insuficiencia cardiaca asintomática (`use_with_caution`), sintomática (`avoid`) y estado desconocido (`not_evaluable`). |
| B11 | Se mantiene evaluable con información clínica; no se convierte en resultado negativo por ausencia de datos. |
| B15/B16/B17 | Conservan la detección de combinaciones; las activaciones Beers usan el estado `activated` y B16 mantiene la excepción de transición/reducción de opioide. |
| B18 | Cuenta solo medicamentos clasificados mediante B03 como anticolinérgicos fuertes; no usa relajantes musculares como sustituto. |
| B19 | Exige depuración de creatinina (CrCl) documentada; si CrCl es <60 mL/min, comunica `Reducir dosis.`. TFGe no se usa como sustituto automático. |
| B20 | Exige CrCl y formulación de tramadol; si CrCl es <30 mL/min, distingue reducción de dosis (liberación inmediata) de evitar (liberación extendida). |
| B21 | Exige ERC estadio 3a o mayor confirmada y detecta dos inhibidores del SRA, o un inhibidor del SRA junto con amilorida/triamtereno. |
| B22 | No se fuerza una falsa ausencia de alerta por la sola presencia de datos de monitorización; continúa requiriendo la lógica clínica aplicable. |
| B23 | Para tamsulosina se devuelve `manual_review`; la evidencia disponible requiere valoración individual. |

## Cambios de interfaz

- La vista Beers muestra “criterios activados” y “candidatos analizados”, en lugar de reutilizar la semántica antigua de alertas/gravedad.
- La tabla Beers separa indicador, código, medicamentos, recomendación, fundamento y acción de revisión.
- Se eliminó la gravedad visual, la advertencia genérica y las acciones sugeridas genéricas en resultados Beers.
- El panel de detalle muestra la recomendación, el fundamento clínico y la trazabilidad AGS, incluyendo tabla/sección y calidad/fuerza cuando están disponibles.
- STOPP/START y DDInter conservan su visualización previa, salvo los ajustes técnicos compartidos para admitir los nuevos estados.

## Validación realizada

Ejecutado dentro del contenedor de desarrollo:

```powershell
docker compose exec -T backend sh -lc 'cd /app && PYTHONPATH=/app PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider'
```

Resultado: **116 pruebas aprobadas** y una advertencia de dependencia de `python_multipart` de Starlette.

También se reconstruyó el entorno y se verificó:

- Frontend: `http://127.0.0.1:8089/health` devuelve HTTP 200.
- Backend: `http://127.0.0.1:8002/health` disponible a través del contenedor saludable.
- Contenedores activos: `sigram-am-dev-backend-1` y `sigram-am-dev-frontend-1`.

## Corrección complementaria: observaciones pendientes

- **B03:** ahora usa el estado `supporting_classification` y se presenta como “Clasificación de apoyo”. No es `no_alert`, no activa un PIM independiente y no aparece en Hallazgos Beers.
- **B16:** solo puede activarse con un opioide más gabapentina/pregabalina. Cuando se activa, los medicamentos implicados y el motivo incluyen toda la combinación real. La excepción se muestra en el detalle, no en el chip breve de recomendación.
- **B17:** aplica estrictamente el umbral de tres o más medicamentos activos del SNC. Se exponen `cns_active_count`, medicamentos y clases usadas para el conteo; dos medicamentos devuelven `no_alert`.
- **Estados visuales:** activado rojo discreto; falta de información ámbar; revisión clínica morado; sin hallazgo azul-gris; fuera del ámbito gris; clasificación de apoyo gris-azulado. Ninguno de estos colores expresa gravedad.
- **Recomendación AGS:** los chips son independientes del estado: Evitar (rojo suave), Usar con precaución (ámbar), Reducir dosis (azul), Monitorizar (turquesa), Condicional (violeta) y clasificación (gris-azulado).
- **Drawer B02:** separa recomendación, situación evaluada, rationale, medicamento, motivo y datos faltantes. La trazabilidad ya no repite el motivo e incluye fuente, tabla/sección, calidad y fuerza con estilo neutral, formulación operativa, versión, evidencia técnica y cobertura.
- **Contadores Beers:** muestran estados mutuamente interpretables (activados, requieren información, requieren revisión y sin hallazgo). La cantidad de candidatos se presenta como cobertura secundaria.
- **Validación posterior:** pruebas automatizadas: **118 aprobadas**; revisión visual local de Hallazgos Beers y drawer B02, incluida la trazabilidad desplegada.

## Limitaciones pendientes de validación clínica/metodológica

- Esta no es una certificación clínica ni una sustitución del juicio profesional.
- Varias reglas del catálogo local no tienen aún una formulación computable completamente validada; se conservan como revisión manual o no evaluables cuando faltan datos.
- B18 solo puede contar las sustancias anticolinérgicas fuertes presentes en el catálogo V1. La cobertura no equivale al listado completo de AGS Table 7.
- B08/B19/B20 no infieren CrCl a partir de TFGe. El dato debe venir documentado desde la fuente autorizada; la estrategia de disponibilidad de CrCl en ESSI requiere validación de integración.
- B23 queda deliberadamente en revisión manual por la limitación de evidencia aplicada a tamsulosina.
- Antes de un uso institucional o clínico, se debe revisar cada regla con el equipo metodológico y documentar las decisiones de implementación, excepciones y pruebas de aceptación.

## Ajustes locales posteriores para pruebas de integración ESSI

- **B06 y enfermedad crónica:** si no existe evidencia positiva de insuficiencia cardiaca en la fuente histórica, B06 se reporta como `not_applicable` y no incrementa “requiere información adicional”. Si la insuficiencia cardiaca sí está documentada pero falta definir si es sintomática, conserva `not_evaluable`.
- **Datos de triaje:** el formulario incluye peso, talla e IMC calculado. Estos campos son editables en la simulación y permiten mostrar cómo ESSI podrá completar datos recuperables de triaje.
- **Clon seguro:** se habilitó el clonado editable de `PILOT-96CBA7BBFA883815`. Carga automáticamente código, edad, sexo, diagnósticos y medicamentos en un caso nuevo simulado; los medicamentos pueden editarse, eliminarse o agregarse sin modificar la cohorte piloto fuente.
- **Acciones sugeridas:** para los criterios no Beers se mantiene el texto existente, pero su bloque usa un color violeta tenue que lo diferencia de un hallazgo o una recomendación normativa.

## Archivos modificados

- `backend/app/services/clinical_catalog_service.py`
- `backend/app/schemas/evaluations.py`
- `backend/app/schemas/cases.py`
- `backend/tests/test_clinical_catalog_v1.py`
- `backend/tests/test_hardening.py`
- `backend/tests/test_health.py`
- `frontend/src/App.tsx`
- `frontend/src/styles.css`
- `frontend/src/types.ts`

Los cambios previos de aislamiento local permanecen en `compose.yaml` y `run-local.ps1`: proyecto Docker `sigram-am-dev`, puertos locales 8089/8002 y volumen independiente. No se incluyeron cambios a GitHub.
