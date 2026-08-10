# Guía de usuario de SIGRAM-AM

## 1. Propósito y advertencia

SIGRAM-AM apoya el tamizaje de prescripciones potencialmente inapropiadas en adultos mayores mediante criterios Beers, STOPP/START e interacciones DDInter. Combina medicamentos, contexto clínico, laboratorios y CIE-10 disponibles para producir hallazgos trazables.

> **Uso seguro:** es un prototipo para simulación, investigación y validación metodológica. No sustituye el juicio clínico ni la historia institucional. Una alerta no es una orden terapéutica y “sin hallazgo” no prueba que una prescripción sea segura.

## 2. Acceso e inicio local

Con Docker Desktop abierto, ejecute desde la carpeta raíz:

```powershell
.\run-local.ps1
```

- Aplicación: `http://127.0.0.1:8088`
- Documentación de API: `http://127.0.0.1:8001/docs`

Para detenerla:

```powershell
.\stop-local.ps1
```

Los casos simulados se conservan entre reinicios en el volumen local de Docker. No ejecute `docker compose down -v` salvo que desee borrar definitivamente esos casos.

## 3. Navegación

| Sección | Finalidad |
| --- | --- |
| **Nuevo caso** | Registrar una receta simulada y ejecutar el análisis. |
| **Historial** | Consultar casos que ya fueron analizados. |
| **Casos del piloto** | Ejecutar los 10 pacientes pseudonimizados de muestra. |
| **Validación de datos** | Auditar fuentes, mapeos, exclusiones y catálogos. |

Nuevo caso e Historial son las áreas operativas. Casos del piloto y Validación de datos son funciones de investigación y usan datos pseudonimizados.

## 4. Crear un caso

Abra **Nuevo caso** para simular una receta y evaluar polifarmacia, criterios clínicos e interacciones.

### 4.1. Elegir el origen de la historia

En **Historia para la simulación** seleccione una de estas opciones:

1. **Crear paciente nuevo sin historial.** Use esta opción para captura manual; los datos y medicamentos quedan vacíos para completar.
2. **Paciente pseudonimizado del piloto.** Seleccione uno de los 10 pacientes por código. El listado indica edad, sexo y número de medicamentos activos.

Al elegir una historia del piloto, SIGRAM-AM carga solo los datos disponibles: edad, sexo, diagnósticos CIE-10 de 2025, contexto derivado de laboratorios/CIE-10 y medicamentos activos en la fecha índice. La carga es temporal, no modifica al paciente de origen ni crea un caso todavía.

### 4.2. Datos obligatorios

Revise y complete estos campos:

- **Código del caso:** identificador del caso simulado, por ejemplo `CASO-2026-001`.
- **Edad:** la aplicación se orienta a población de 60 años o más.
- **Sexo:** seleccione Masculino o Femenino.
- **Diagnósticos / condiciones clínicas:** ingrese condiciones relevantes o complete los CIE-10 precargados.

La precarga no inventa antecedentes. Si la historia no contiene una condición, mantenga el campo pendiente o complételo solo con información confiable.

### 4.3. Medicamentos nuevos

La tarjeta superior **Medicamentos activos** es la receta nueva que se desea simular. Para cada fila:

1. Elija el fármaco en **Medicamento del catálogo**.
2. Revise el **Nombre normalizado**, completado desde el catálogo V1.
3. Ingrese dosis, unidad, frecuencia y vía.
4. Ingrese duración cuando se conozca, usando número de días, por ejemplo `30 días` o `120 días`.
5. Pulse **Agregar** para otra fila o use el ícono de eliminación para retirarla.

El catálogo V1 contiene 54 medicamentos priorizados. El botón de evaluación se habilita después de completar los campos obligatorios de cada medicamento nuevo.

### 4.4. Medicamentos en uso

Al elegir un paciente pseudonimizado aparece debajo de la receta nueva el desplegable **Medicamentos en uso**.

- Contiene el tratamiento activo hallado en la historia para la fecha índice.
- Es solo de consulta; no debe capturarse como una nueva prescripción.
- Permanece plegado para mantener visible la receta nueva.
- Al ejecutar el caso, los medicamentos históricos se combinan con los nuevos para evaluar polifarmacia e interacciones.

Al volver a “Crear paciente nuevo sin historial”, los medicamentos históricos se eliminan de la simulación para evitar mezclar pacientes.

### 4.5. Contexto clínico

Abra **Contexto clínico (opcional)** para revisar o ingresar datos como función renal, electrolitos, antecedentes gastrointestinales, caídas, deterioro cognitivo, insuficiencia cardiaca, gastroprotección o condiciones cardiovasculares.

Los campos se presentan en dos desplegables:

- **Exámenes y datos clínicos realizados:** valores ya disponibles desde historia, laboratorio o CIE-10 mapeado.
- **Exámenes y datos clínicos no realizados / no registrados:** campos pendientes que puede completar manualmente.

Un valor “No” es información registrada. “No registrado” significa que el sistema no puede usar ese dato para evaluar un criterio.

### 4.6. Ejecutar

Cuando el indicador inferior muestre **Datos mínimos completos**, pulse **Crear caso y ejecutar tamizaje**. La aplicación guarda el caso simulado, combina medicamentos nuevos e históricos si corresponde, ejecuta Beers, STOPP/START y DDInter, y abre los resultados.

Si el botón permanece desactivado, complete código, edad, sexo, diagnósticos y los campos requeridos de las filas nuevas.

## 5. Resultados

La pantalla de resultados se organiza por Beers, STOPP/START y DDInter. La vista inicial usa hallazgos clínicos visibles; el análisis técnico completo queda bajo detalle para evitar ruido y conclusiones excesivas.

### 5.1. Estados

| Estado | Significado |
| --- | --- |
| **Alerta** | Hay un hallazgo según los datos observados y la regla disponible. Requiere revisión profesional. |
| **Requiere información adicional** | Faltan datos necesarios. No significa que el criterio se cumpla ni que se descarte. |
| **Revisión manual** | El criterio requiere interpretación profesional o información no automatizable. |
| **Sin hallazgo en los datos observados** | No se halló una señal con los datos disponibles. Se consulta dentro del análisis completo. |

Use búsqueda, filtros de estado y pestañas de sistema para focalizar la revisión. DDInter se presenta aparte porque evalúa pares de medicamentos e interacciones.

### 5.2. Ver detalle

Pulse **Ver detalle** en una fila para consultar el enunciado, medicamentos implicados, datos faltantes, laboratorios usados, evidencia CIE-10, protectores, excepciones y acciones sugeridas. Abra **Ver más** para revisar justificación, fuente, versión, evidencia activadora y cobertura farmacológica.

Use esta información para comprender por qué se generó una alerta o por qué faltó información. No reemplace un dato faltante por “No” sin respaldo clínico.

### 5.3. Evidencia posterior a la fecha índice

En el piloto puede aparecer el aviso “Evidencia posterior a la fecha índice, considerada por la regla anual del piloto 2025”. Significa que el dato pertenece a 2025 pero se registró después del día usado para determinar medicamentos activos. Se usa para la validación retrospectiva anual, no como evidencia necesariamente conocida al momento exacto de la receta.

## 6. Historial

Abra **Historial** para consultar casos ya analizados. Cada registro permite identificar código, datos generales, fecha y resultados. Esta sección no es para capturar casos ni para auditar datos fuente; esas actividades pertenecen a Nuevo caso y Validación de datos respectivamente.

## 7. Casos del piloto

Use **Casos del piloto** para ejecutar directamente uno de los 10 pacientes pseudonimizados.

1. Seleccione el paciente.
2. Revise fecha índice y disponibilidad de datos.
3. Ejecute el análisis.
4. Revise resultados y trazabilidad.

La fecha índice es el día de 2025 con mayor solapamiento de medicamentos del catálogo. Laboratorios y diagnósticos CIE-10 se revisan retrospectivamente durante todo 2025, desde `2025-01-01` hasta `2025-12-31`.

## 8. Validación de datos

La pestaña **Validación de datos** es una función de investigación; no crea ni modifica casos. Seleccione un paciente pseudonimizado para revisar:

- Medicamentos activos en la fecha índice y periodo clínico completo de 2025.
- Filas originales de laboratorio: fecha, código ESSI, analito, valor, unidad, rango y estado de validación.
- Filas CIE-10 de origen.
- Campos aceptados por los mapeos de laboratorio y diagnóstico.
- Advertencias, registros excluidos y conteos de disponibilidad.
- Catálogo de 54 medicamentos y catálogo de criterios.

En el catálogo de criterios, **Sistema** indica Beers o STOPP/START. **Tipo** muestra `STOPP` o `START` para esos criterios y una raya (`—`) para Beers, porque Beers no usa esa clasificación.

Esta pantalla sirve para responder: “¿qué examen se utilizó?”, “¿qué CIE-10 resolvió una condición?”, “¿por qué una fila fue excluida?” y “¿qué información falta para evaluar un criterio?”.

## 9. Uso seguro y límites

- Verifique datos en la fuente institucional antes de una decisión clínica.
- No interprete un campo no registrado como antecedente negativo o examen normal.
- Revise la fecha de medicamentos, laboratorios y diagnósticos.
- Complete manualmente antecedentes difíciles de representar en CIE-10/laboratorio, como fragilidad, adherencia, indicación o riesgo de caídas.
- Confirme dosis, frecuencia, vía y duración antes de ejecutar una simulación.
- Use alertas como punto de partida para revisión, nunca como conclusión terapéutica automática.

El piloto se limita al catálogo V1 de 54 medicamentos, 10 pacientes pseudonimizados y datos retrospectivos de 2025. Los mapeos ESSI, CIE-10, laboratorio y DDInter requieren validación clínica e institucional continua; varios criterios siguen dependiendo de contexto o revisión manual.

## 10. Problemas frecuentes

### La aplicación no abre

1. Confirme que Docker Desktop está iniciado.
2. Ejecute `.\run-local.ps1` desde la raíz.
3. Abra `http://127.0.0.1:8088`.
4. Si persiste, ejecute `docker compose ps` y confirme que backend y frontend estén saludables.

### No se cargan pacientes del piloto

Confirme que el backend esté saludable y que exista la muestra en `SIGRAM_AM_BACKEND_V1_20260805/data/processed/v1_handoff/`. Esa carpeta debe contener los archivos de pacientes, medicamentos, laboratorios y diagnósticos.

### Un criterio requiere información adicional

Abra **Ver detalle**, revise datos faltantes y complete Contexto clínico solo si tiene un dato confiable. Si no existe, mantenga la brecha de información; no la reemplace por “No” sin sustento.

### STOPP o START no aparece en Tipo

Recargue la aplicación. La versión actual recibe `criterion_type` desde el backend y muestra `STOPP` o `START`; Beers conserva una raya en esa columna.

### No se considera el tratamiento histórico

Verifique que eligió el paciente correcto y abra **Medicamentos en uso**. Ese bloque se combina automáticamente con la receta nueva. Si eligió “Crear paciente nuevo sin historial”, se elimina intencionalmente.
