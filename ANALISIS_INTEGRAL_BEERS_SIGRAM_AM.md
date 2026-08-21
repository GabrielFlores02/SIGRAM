# Análisis integral de AGS Beers Criteria 2023, catálogo operativo B01–B23 del Dr. Armando Torre e implementación recomendada en SIGRAM-AM

**Proyecto:** SIGRAM-AM — Sistema piloto de soporte a la decisión clínica para evaluación de prescripción y optimización de polifarmacia en adultos mayores  
**Documento:** Análisis clínico-metodológico y especificación funcional del módulo Beers  
**Fecha:** 12 de agosto de 2026  
**Estado:** Documento técnico de trabajo para revisión clínica y metodológica

---

## 1. Propósito del documento

Este documento consolida el análisis realizado sobre tres capas que actualmente convergen en SIGRAM-AM:

1. **La fuente científica primaria:** *American Geriatrics Society 2023 updated AGS Beers Criteria® for Potentially Inappropriate Medication Use in Older Adults*.
2. **El catálogo operativo desarrollado por el Dr. Armando Torre y el equipo clínico:** archivo `top_meds_list_beers_stopp_start_v3-20260730.xlsx`, que selecciona y organiza criterios relevantes para los 54 medicamentos priorizados del piloto.
3. **La implementación computable en SIGRAM-AM:** reglas de backend, estados de evaluación, trazabilidad y representación visual en frontend.

El objetivo es establecer con claridad:

- qué significa realmente cada componente de AGS Beers 2023;
- qué función cumple el catálogo B01–B23;
- qué debe conservarse literalmente del catálogo del Dr. Armando;
- qué información debe recuperarse directamente del paper;
- cómo debe convertirse cada criterio en una regla computable;
- cómo deben distinguirse criterio candidato, criterio activado, dato faltante, revisión clínica y clasificación de apoyo;
- cómo deben representarse visualmente los resultados sin inventar una escala de gravedad que Beers no define;
- qué problemas actuales del motor deben corregirse;
- qué pruebas deben cumplirse antes de considerar validado el módulo Beers del piloto.

Este documento **no sustituye al paper AGS Beers 2023 ni constituye una guía clínica independiente**. Su función es definir una implementación fiel, auditable y metodológicamente defendible dentro del piloto SIGRAM-AM.

---

# 2. Conclusión ejecutiva

La arquitectura correcta para implementar Beers en SIGRAM-AM debe ser:

```text
AGS BEERS CRITERIA 2023
Fuente científica primaria
        ↓
CATÁLOGO OPERATIVO DEL DR. ARMANDO
Selección B01–B23 + mapeo con los 54 medicamentos del piloto
        ↓
REGLA COMPUTABLE SIGRAM
Condiciones, variables requeridas, excepciones, lógica y versionado
        ↓
DATOS DEL PACIENTE
Medicamentos + contexto clínico + CIE-10 + laboratorio + temporalidad
        ↓
RESULTADO DEL TAMIZAJE
activated / not_evaluable / manual_review / no_alert / out_of_scope
        ↓
PRESENTACIÓN CLÍNICA
Recommendation + Rationale + motivo del paciente + trazabilidad
```

La principal recomendación es **no usar el texto del catálogo del Dr. Armando como única representación de Beers**, pero tampoco reemplazarlo por una reinterpretación del software.

El catálogo del Dr. Armando debe conservarse como una **capa operativa institucional del piloto**, mientras que SIGRAM debe recuperar y almacenar por separado, cuando corresponda:

- **Recommendation**;
- **Rationale**;
- **Quality of evidence**;
- **Strength of recommendation**;
- tabla y sección original;
- condiciones;
- excepciones;
- ámbito etario;
- ubicación en la fuente.

Asimismo, SIGRAM **no debe inventar una escala `Alta / Moderada / Baja` para Beers**. Esos conceptos no son la clasificación oficial del criterio. Los colores deben representar:

1. **estado del tamizaje SIGRAM**; y
2. **tipo de Recommendation AGS Beers**,

como dos capas visuales distintas.

---

# 3. Qué es AGS Beers Criteria 2023

## 3.1. Finalidad

AGS Beers Criteria es una lista explícita de medicamentos o situaciones farmacológicas potencialmente inapropiadas en adultos mayores. El paper señala que sus objetivos incluyen:

- reducir la exposición de adultos mayores a medicamentos potencialmente inapropiados;
- mejorar la selección de medicamentos;
- apoyar la educación de profesionales y pacientes;
- reducir eventos adversos relacionados con medicamentos;
- apoyar investigación y evaluación de calidad de atención.

El criterio **no reemplaza el juicio clínico** y debe apoyar, no sustituir, la toma compartida de decisiones.

## 3.2. Población original

Salvo que un criterio especifique otro umbral, el paper está diseñado para:

> **adultos de 65 años o más**

en atención ambulatoria, aguda e institucional, exceptuando cuidados paliativos/hospicio y final de vida.

Esto genera una diferencia metodológica importante con el protocolo SIGRAM, que incluye pacientes desde los 60 años. Esta diferencia debe hacerse explícita en la plataforma y no resolverse silenciosamente.

## 3.3. Las cinco categorías oficiales de Beers

El paper organiza sus criterios en cinco grandes categorías:

| Tabla | Categoría oficial | Qué pregunta clínicamente |
|---|---|---|
| **Table 2** | Medicamentos considerados potencialmente inapropiados | ¿Este fármaco/clase debería evitarse o restringirse en adultos mayores, aun sin una enfermedad específica? |
| **Table 3** | Interacción medicamento–enfermedad/síndrome | ¿Este medicamento se vuelve potencialmente inapropiado debido a una condición concreta del paciente? |
| **Table 4** | Medicamentos a usar con precaución | ¿Existe un balance beneficio/daño que requiere precaución o monitorización? |
| **Table 5** | Interacciones fármaco–fármaco clínicamente relevantes | ¿Existe una combinación específica que debe evitarse o minimizarse? |
| **Table 6** | Medicamentos a evitar o ajustar según función renal | ¿La función renal cambia la recomendación o dosis? |

Además:

| Tabla | Función |
|---|---|
| **Table 7** | Lista de fármacos con propiedades anticolinérgicas fuertes |

La Table 7 es particularmente importante porque **no debe tratarse como si fuera otra tabla de recomendaciones independientes**. Es principalmente una clasificación de apoyo utilizada por otras reglas.

---

# 4. Conceptos que Beers mantiene separados

En sus tablas principales, Beers distingue varios conceptos que SIGRAM debe preservar.

## 4.1. Drug / Drug class / Clinical situation

Describe el medicamento, grupo terapéutico o situación evaluada.

Ejemplo conceptual para B02:

> Relajantes musculares esqueléticos utilizados para molestias musculoesqueléticas.

## 4.2. Rationale

Es el **fundamento clínico** de la preocupación.

Responde:

> ¿Por qué este medicamento o situación puede ser problemática?

No es lo mismo que la recomendación.

## 4.3. Recommendation

Indica la acción propuesta por el panel AGS.

Puede adoptar formas como:

- **Avoid / Evitar**;
- **Use with caution / Usar con precaución**;
- **Reduce dose / Reducir dosis**;
- monitorizar;
- recomendaciones condicionadas;
- combinaciones de acciones.

## 4.4. Quality of evidence

El paper clasifica la calidad de evidencia como:

- **High**;
- **Moderate**;
- **Low**.

Esto representa la confianza/calidad del sustento científico.

**No representa gravedad clínica.**

## 4.5. Strength of recommendation

Se expresa principalmente como:

- **Strong**;
- **Weak**.

Integra calidad de evidencia, balance beneficio-riesgo, frecuencia/severidad de daños y juicio clínico.

**Una recomendación fuerte no equivale a “riesgo alto”.**

---

# 5. Por qué SIGRAM no debe crear una “gravedad Beers”

Una de las decisiones metodológicas más importantes es eliminar de Beers una escala genérica:

- Alta;
- Moderada;
- Baja.

Esa escala no forma parte de la estructura oficial del paper.

Ejemplo:

- B19, gabapentina con función renal reducida: Beers recomienda **Reducir dosis**, con evidencia **Moderada** y fuerza **Fuerte**.
- B20, tramadol con CrCl <30: tiene recomendación distinta según formulación, evidencia **Baja** y fuerza **Débil**.
- B11: puede indicar **Usar con precaución**, aunque la fuerza sea **Fuerte**.

Por tanto:

```text
Recommendation ≠ severidad
Quality of evidence ≠ severidad
Strength of recommendation ≠ severidad
```

SIGRAM puede indicar visualmente que una regla se activó, pero no debe traducir estas dimensiones a una “gravedad” clínica propia sin una metodología adicional validada.

---

# 6. Estructura del catálogo desarrollado por el Dr. Armando

El archivo analizado contiene tres hojas principales:

1. **Medicamentos**
2. **Ubicación de criterios**
3. **Ubicación STOPP-START**

Para este documento se analizan principalmente las dos primeras.

---

# 7. Hoja “Medicamentos”: qué función cumple

La hoja contiene **54 medicamentos/presentaciones priorizadas**.

Columnas principales:

- número;
- medicamento;
- grupo farmacéutico;
- criterios STOPP v3 aplicables;
- criterios START v3 aplicables;
- criterios AGS Beers 2023 aplicables.

## 7.1. Cobertura Beers del catálogo

De los 54 medicamentos priorizados:

- **19 presentan al menos una relación con criterios Beers B01–B23**;
- **35 no presentan un criterio Beers específico en las Tablas 2–7 según el catálogo operativo**.

Esto no significa que esos 35 medicamentos sean “seguros”; únicamente significa que el catálogo no identifica para ellos un criterio Beers específico dentro de este subconjunto.

## 7.2. Lógica medicamento → criterio candidato

Esta hoja permite responder:

> “Si este medicamento aparece en la prescripción, ¿qué criterios Beers podrían ser relevantes?”

Ejemplo:

```text
ORFENADRINA
  ├─ B02
  ├─ B03
  ├─ B12
  ├─ B13
  ├─ B14
  ├─ B17
  └─ B18
```

Esto es un **mapeo para preseleccionar criterios candidatos**.

No debe interpretarse como:

```text
medicamento presente = todos esos criterios activados
```

Esa diferencia debe ser estructural en el backend.

---

# 8. Hoja “Ubicación de criterios”: qué función cumple

El Dr. Armando creó 23 identificadores operativos:

```text
B01 ... B23
```

Estos códigos son **códigos internos de SIGRAM**, no códigos oficiales del artículo AGS Beers.

Para cada código se registra:

- **Código**;
- **Tabla o cuadro**;
- **Criterio / sección**;
- **Formulación operativa en español**;
- **Ubicación**.

La columna más importante metodológicamente es:

> **Formulación operativa en español**

porque transforma el contenido del paper en una forma más directa para el piloto.

Sin embargo, esa formulación suele integrar en una misma frase componentes que el paper mantiene separados, por ejemplo:

```text
Recommendation + situación + Rationale + alguna excepción
```

Por ello, debe conservarse como **formulación operativa SIGRAM**, pero no utilizarse como único modelo de datos.

---

# 9. Qué hizo correctamente el catálogo del Dr. Armando

El catálogo aporta cuatro elementos esenciales que el paper por sí solo no resuelve para SIGRAM:

## 9.1. Reduce el universo al piloto

Beers contiene muchas clases y medicamentos que no forman parte del piloto.

El catálogo define qué criterios resultan relevantes para los 54 medicamentos seleccionados.

## 9.2. Crea identificadores computables

En vez de programar textos largos, SIGRAM puede referirse a:

```text
B02
B16
B19
```

Esto facilita:

- reglas;
- versionado;
- pruebas;
- trazabilidad;
- resultados.

## 9.3. Relaciona presentaciones ESSI con criterios

El catálogo actúa como puente entre:

```text
PRESENTACIÓN ESSI
↓
GRUPO FARMACOLÓGICO
↓
CRITERIO B01–B23
```

Esto responde directamente a la observación metodológica de que cada medicamento debe estar agrupado y debe conocerse “dónde cae”.

## 9.4. Conserva ubicación documental

Cada B01–B23 tiene una referencia:

- tabla;
- sección;
- página.

Esto permite auditar el resultado desde SIGRAM hasta el paper.

---

# 10. Qué NO debe hacer el catálogo por sí solo

El Excel **no debe convertirse directamente en el motor clínico**.

La formulación:

> “B16. Evitar combinar opioides con gabapentina…”

no implica que la mera aparición de gabapentina active B16.

La regla computable debe verificar:

```text
opioide activo
AND
gabapentina/pregabalina activa
AND
condiciones/excepciones
```

El Excel define **qué revisar**.  
El motor determina **si se cumple**.

---

# 11. Análisis detallado B01–B23

La siguiente tabla distingue:

- información derivada directamente del catálogo del Dr. Armando;
- interpretación necesaria para convertirla en una regla SIGRAM.

> **Nota:** cuando una recomendación depende de condiciones o presenta múltiples perfiles de evidencia, el backend no debe forzar un único valor estático.

| Código | Tabla | Sección del catálogo | Implementación recomendada en SIGRAM |
|---|---|---|---|
| **B01** | Tabla 2 | Benzodiacepinas | Alprazolam convierte B01 en candidato. Antes de declarar hallazgo debe conservarse la posibilidad de indicaciones/excepciones descritas por Beers. Si la indicación no está disponible, considerar revisión clínica o lógica condicionada, no asumir ausencia de justificación. |
| **B02** | Tabla 2 | Relajantes musculares esqueléticos | Orfenadrina activa puede producir un hallazgo directo dentro del ámbito etario original. Recommendation: **Evitar**. Separar situación evaluada, Rationale, medicamento implicado y motivo del paciente. |
| **B03** | Tabla 7 | Fármacos anticolinérgicos fuertes | **Clasificación de apoyo**, no hallazgo clínico independiente. Orfenadrina se clasifica como anticolinérgico fuerte. Debe alimentar B12/B13/B14/B18, no contar automáticamente como PIM independiente. |
| **B04** | Tabla 2 | Inhibidores de bomba de protones | No activar por presencia de omeprazol. Requiere duración >8 semanas y evaluación de indicaciones/excepciones de mantenimiento. |
| **B05** | Tabla 2 | AINE oral | Diclofenaco/naproxeno/ibuprofeno generan criterio candidato. Deben evaluarse duración, alto riesgo, combinaciones concomitantes y gastroprotección. No usar `AINE = alerta`. |
| **B06** | Tabla 3 | Insuficiencia cardiaca | Necesita AINE + insuficiencia cardiaca + estado sintomático. IC asintomática → precaución; IC sintomática → evitar. Si no se conoce estado sintomático → `not_evaluable`. |
| **B07** | Tabla 3 | Antecedente de úlcera gástrica/duodenal | Requiere AAS/AINE + antecedente de úlcera + evaluación de alternativas/gastroprotección. |
| **B08** | Tabla 6 | AINE y función renal | Requiere AINE + función renal. Con CrCl <30 → **Evitar**. Si falta función renal → `not_evaluable`. |
| **B09** | Tabla 2 | AAS en prevención primaria | Debe distinguir inicio de aspirina vs paciente que ya la utiliza y prevención primaria vs secundaria. No reducir a `AAS presente = hallazgo`. |
| **B10** | Tabla 2 | Sulfonilureas | Glibenclamida genera candidato. Deben conservarse condiciones sobre posición terapéutica/barreras para alternativas y mayor preocupación por sulfonilureas de acción prolongada. |
| **B11** | Tabla 4 | SIADH/hiponatremia | Hidroclorotiazida y tramadol son candidatos. Recommendation: **Usar con precaución** y monitorizar sodio al inicio/cambios de dosis. No mostrar `Evitar`. |
| **B12** | Tabla 3 | Delirium | Requiere delirium/alto riesgo + medicamento relevante. La conducta puede variar por clase; corticoides tienen tratamiento particular en el catálogo. Si falta el contexto de delirium → `not_evaluable`. |
| **B13** | Tabla 3 | Demencia/deterioro cognitivo | Requiere condición documentada + benzodiacepina/anticolinérgico fuerte. Table 7 puede aportar la clasificación anticolinérgica. |
| **B14** | Tabla 3 | Caídas o fracturas | Requiere antecedente de caídas/fracturas + clases de fármacos relevantes. Debe conservar excepciones, incluido el uso de opioides para dolor agudo intenso. |
| **B15** | Tabla 5 | Opioide + benzodiacepina | Solo activar si existe simultáneamente un opioide y una benzodiacepina. Recommendation: **Evitar**. |
| **B16** | Tabla 5 | Opioide + gabapentinoide | Solo activar con opioide + gabapentina/pregabalina. Gabapentina sola no activa. Existen excepciones para transición/reducción de opioide. |
| **B17** | Tabla 5 | ≥3 medicamentos activos SNC | Contar exclusivamente clases Beers: antiepilépticos/gabapentinoides, antidepresivos, antipsicóticos, benzodiacepinas, Z-drugs, opioides y relajantes musculares. Con 2 → `no_alert`; con ≥3 → `activated`. |
| **B18** | Tabla 5 | Carga anticolinérgica | Requiere ≥2 medicamentos con propiedades anticolinérgicas. Table 7 debe funcionar como fuente de clasificación. |
| **B19** | Tabla 6 | Gabapentina y función renal | Con función renal <60 mL/min → **Reducir dosis**. No `Evitar`. Si no existe función renal → `not_evaluable`. |
| **B20** | Tabla 6 | Tramadol y función renal | CrCl <30: liberación inmediata → reducir dosis; liberación prolongada → evitar. No debe colapsarse en una única Recommendation. |
| **B21** | Tabla 5 | Inhibidores del sistema renina-angiotensina en ERC | Requiere ERC ≥3a + combinación específica de inhibidores RAS o RAS + diurético ahorrador de potasio. Un IECA/ARA-II aislado no activa el criterio. |
| **B22** | Tabla 5 | Litio + IECA/ARA-II/ARNI | Requiere litio + uno de los agentes indicados. Recommendation: evitar y monitorizar litio si se utiliza. |
| **B23** | Tabla 3, nota e | Síncope + bloqueadores alfa-1 selectivos | El propio catálogo indica datos limitados para tamsulosina. Debe mantenerse como `manual_review` o adaptación pendiente de validación clínica, no como regla automática equivalente a B02. |

---

# 12. Formulaciones operativas B01–B23 del catálogo del Dr. Armando

Esta sección conserva el contenido operacional del Excel para trazabilidad. Estos textos deben almacenarse en SIGRAM como **`operational_formulation`**, no como reemplazo de la estructura original del paper.

### B01 — Tabla 2 — Benzodiacepinas
> Evitar benzodiacepinas en adultos mayores, salvo indicaciones específicas justificadas. Aumentan el riesgo de deterioro cognitivo, delirium, caídas y fracturas; además, existe mayor sensibilidad y riesgo de dependencia.

**Ubicación:** p. 9 del PDF.

### B02 — Tabla 2 — Relajantes musculares esqueléticos
> Evitar los relajantes musculares usados para molestias musculoesqueléticas, incluida la orfenadrina: suelen tolerarse mal por sus efectos anticolinérgicos, sedación y mayor riesgo de fracturas, y su eficacia a dosis tolerables es incierta.

**Ubicación:** p. 12.

### B03 — Tabla 7 — Fármacos con propiedades anticolinérgicas intensas
> Considerar la orfenadrina como medicamento con propiedades anticolinérgicas intensas.

**Ubicación:** p. 23.

### B04 — Tabla 2 — Inhibidores de la bomba de protones
> Evitar el uso programado de inhibidores de la bomba de protones durante más de 8 semanas, excepto cuando exista una indicación de mantenimiento justificada, como esofagitis erosiva, esófago de Barrett, hipersecreción patológica, necesidad demostrada de mantenimiento o protección gastrointestinal por alto riesgo.

**Ubicación:** p. 11.

### B05 — Tabla 2 — AINE no selectivos de COX-2 por vía oral
> Evitar el uso crónico de AINE orales salvo que otras alternativas no sean eficaces y pueda administrarse gastroprotección. En pacientes de alto riesgo, evitar también su uso programado a corto plazo con corticoides sistémicos, anticoagulantes o antiagregantes, salvo ausencia de alternativas y con gastroprotección.

**Ubicación:** pp. 11–12.

### B06 — Tabla 3 — Insuficiencia cardiaca
> En insuficiencia cardiaca asintomática, usar los AINE con precaución; en insuficiencia cardiaca sintomática, evitarlos porque pueden promover retención de líquidos o exacerbar el cuadro.

**Ubicación:** p. 14.

### B07 — Tabla 3 — Antecedente de úlcera gástrica o duodenal
> Evitar ácido acetilsalicílico y AINE no selectivos en pacientes con antecedente de úlcera gástrica o duodenal, salvo que otras alternativas no sean eficaces y pueda proporcionarse gastroprotección.

**Ubicación:** p. 16.

### B08 — Tabla 6 — AINE y función renal
> Evitar AINE orales o parenterales cuando la depuración de creatinina sea menor de 30 mL/min, por riesgo de lesión renal aguda y mayor deterioro de la función renal.

**Ubicación:** p. 22.

### B09 — Tabla 2 — Ácido acetilsalicílico en prevención primaria
> Evitar iniciar ácido acetilsalicílico para prevención primaria cardiovascular. En quienes ya lo reciben con ese propósito, considerar su deprescripción. Este criterio no se aplica a la prevención secundaria con enfermedad cardiovascular establecida.

**Ubicación:** p. 6.

### B10 — Tabla 2 — Sulfonilureas
> Evitar las sulfonilureas como monoterapia o tratamiento añadido de primera o segunda línea, salvo barreras importantes para usar alternativas más seguras y eficaces. Si se requiere una, preferir una de acción corta; evitar glibenclamida por su mayor riesgo de hipoglucemia prolongada.

**Ubicación:** p. 10.

### B11 — Tabla 4 — Medicamentos asociados con SIADH o hiponatremia
> Usar diuréticos y tramadol con precaución; controlar estrechamente el sodio al iniciar el tratamiento o modificar la dosis, porque pueden causar o agravar SIADH o hiponatremia.

**Ubicación:** p. 17.

### B12 — Tabla 3 — Delirium
> En pacientes con delirium o alto riesgo, evitar benzodiacepinas, fármacos anticolinérgicos y opioides. Si un corticoide sistémico es necesario, usar la menor dosis durante el menor tiempo posible y vigilar delirium.

**Ubicación:** p. 15.

### B13 — Tabla 3 — Demencia o deterioro cognitivo
> Evitar fármacos anticolinérgicos intensos y benzodiacepinas en pacientes con demencia o deterioro cognitivo por sus efectos adversos sobre el sistema nervioso central.

**Ubicación:** p. 15.

### B14 — Tabla 3 — Antecedentes de caídas o fracturas
> En pacientes con antecedentes de caídas o fracturas, evitar anticolinérgicos, antiepilépticos, benzodiacepinas y opioides salvo que no existan alternativas más seguras; para opioides, la excepción señalada es el dolor agudo intenso. Si se usan, reducir otros medicamentos del sistema nervioso central que aumenten el riesgo.

**Ubicación:** pp. 15–16.

### B15 — Tabla 5 — Opioides con benzodiacepinas
> Evitar la combinación de un opioide con una benzodiacepina por mayor riesgo de sobredosis y otros eventos adversos.

**Ubicación:** p. 19.

### B16 — Tabla 5 — Opioides con gabapentinoides
> Evitar combinar opioides con gabapentina o pregabalina por eventos adversos graves relacionados con sedación. Se exceptúan la transición desde opioides o el uso para reducir su dosis, manteniendo precaución.

**Ubicación:** p. 19.

### B17 — Tabla 5 — Tres o más medicamentos activos sobre el SNC
> Evitar el uso concurrente de tres o más medicamentos activos sobre el sistema nervioso central de las clases señaladas —antiepilépticos, antidepresivos, antipsicóticos, benzodiacepinas, hipnóticos Z, opioides y relajantes musculares—; minimizar su número por mayor riesgo de caídas y fracturas.

**Ubicación:** p. 19.

### B18 — Tabla 5 — Carga anticolinérgica
> Evitar la combinación de dos o más medicamentos con propiedades anticolinérgicas y minimizar su número, por mayor riesgo de deterioro cognitivo, delirium, caídas y fracturas.

**Ubicación:** p. 19; remite a Table 7.

### B19 — Tabla 6 — Gabapentina y función renal
> Reducir la dosis de gabapentina cuando la función renal estimada sea menor de 60 mL/min, por mayor riesgo de efectos adversos del sistema nervioso central.

**Ubicación:** p. 22.

### B20 — Tabla 6 — Tramadol y función renal
> Cuando la depuración de creatinina sea menor de 30 mL/min, reducir la dosis de tramadol de liberación inmediata y evitar la formulación de liberación prolongada.

**Ubicación:** p. 22.

### B21 — Tabla 5 — Inhibidores del sistema renina-angiotensina en ERC
> En enfermedad renal crónica estadio 3a o superior, evitar el uso rutinario simultáneo de dos o más inhibidores del sistema renina-angiotensina, o de uno de ellos con un diurético ahorrador de potasio, por riesgo de hiperpotasemia.

**Ubicación:** p. 19.

### B22 — Tabla 5 — Litio con IECA, ARA-II o ARNI
> Evitar la combinación de litio con un IECA, ARA-II o ARNI; si se usa, vigilar las concentraciones de litio por mayor riesgo de toxicidad.

**Ubicación:** pp. 19–20.

### B23 — Tabla 3, nota e — Síncope y bloqueadores alfa-1 selectivos
> En pacientes con síncope, considerar que los datos son limitados para bloqueadores alfa-1 periféricos selectivos como tamsulosina, pero el criterio de hipotensión ortostática podría ser aplicable; requiere evaluación clínica individual.

**Ubicación:** p. 16.

---

# 13. Medicamentos del piloto relacionados con Beers

El catálogo contiene 19 medicamentos/presentaciones con al menos un código B01–B23.

| Medicamento del catálogo | Códigos Beers candidatos |
|---|---|
| DICLOFENACO SÓDICO 25 MG / ML X 3 ML | B05, B06, B07, B08 |
| LOSARTAN 50 MG | B21, B22 |
| OMEPRAZOL 20 MG DE LIBERACIÓN RETARDADA | B04 |
| GABAPENTINA 300 MG | B14, B16, B17, B19 |
| NAPROXENO 500/550 MG | B05, B06, B07, B08 |
| ÁCIDO ACETILSALICÍLICO 100 MG | B07, B09 |
| ORFENADRINA CITRATO 100 MG LP | B02, B03, B12, B13, B14, B17, B18 |
| ALPRAZOLAM 0.5 MG | B01, B12, B13, B14, B15, B17 |
| HIDROCLOROTIAZIDA 25 MG | B11 |
| IRBESARTÁN 150 MG | B21, B22 |
| DEXAMETASONA 2 MG/ML | B12 |
| TAMSULOSINA 0.4 MG LP | B23 |
| ORFENADRINA CITRATO 30 MG/ML | B02, B03, B12, B13, B14, B17, B18 |
| NAPROXENO 250/275 MG | B05, B06, B07, B08 |
| IBUPROFENO 400 MG | B05, B06, B07, B08 |
| TRAMADOL 50 MG | B11, B12, B14, B15, B16, B17, B20 |
| ENALAPRIL 10 MG | B21, B22 |
| GLIBENCLAMIDA 5 MG | B10 |
| OMEPRAZOL 20 MG LP | B04 |

El resto de medicamentos del catálogo no debe ser presentado como “libre de riesgo”; únicamente carece de una relación específica Beers dentro del subconjunto definido.

---

# 14. Arquitectura correcta del backend

## 14.1. Separar catálogo, regla y resultado

Cada criterio debe tener un modelo de conocimiento independiente del resultado del paciente.

Ejemplo recomendado:

```json
{
  "criterion_code": "B02",
  "system": "Beers",
  "source_name": "AGS Beers Criteria",
  "source_year": 2023,
  "source_table": "Table 2",
  "source_section": "Skeletal muscle relaxants",
  "source_location": "p. 12",
  "beers_category": "potentially_inappropriate_medication",
  "criterion_kind": "clinical_criterion",
  "operational_formulation": "...texto del catálogo del Dr. Armando...",
  "clinical_situation": "...",
  "rationale": "...",
  "recommendation_type": "avoid",
  "recommendation_text": "Evitar",
  "quality_of_evidence": "moderate",
  "strength_of_recommendation": "strong",
  "age_scope": ">=65",
  "required_data": [],
  "exceptions": [],
  "catalog_version": "..."
}
```

---

# 15. Estados de evaluación recomendados

Los estados deben describir el **resultado computacional**, no el tipo de Recommendation.

## `activated`

Todos los datos necesarios existen y la regla se cumple.

## `not_evaluable`

El criterio es candidato pero falta una variable necesaria.

Ejemplo:

```text
AINE activo
+
B08 candidato
+
TFGe/CrCl no disponible
→ not_evaluable
```

## `manual_review`

Existe información relevante pero el criterio requiere juicio profesional o evidencia insuficiente para automatización.

B23 es el ejemplo más claro.

## `no_alert`

La regla fue evaluable y no se cumplieron sus condiciones.

## `out_of_scope`

Fuera del ámbito original del criterio, por ejemplo un paciente de 60–64 años bajo aplicación canónica de Beers.

## `supporting_classification`

Estado recomendado para clasificaciones auxiliares como B03.

---

# 16. Criterio candidato ≠ criterio activado

Esta es una de las reglas de diseño más importantes.

Ejemplo B16:

```text
GABAPENTINA
↓
B16 candidato

GABAPENTINA sola
↓
NO B16

GABAPENTINA + OPIOIDE
↓
B16 evaluable
↓
revisar excepciones
↓
activated o no_alert
```

Ejemplo B17:

```text
GABAPENTINA + ORFENADRINA
↓
2 medicamentos SNC
↓
B17 = no_alert

GABAPENTINA + ORFENADRINA + OPIOIDE válido
↓
3 medicamentos SNC
↓
B17 = activated
```

---

# 17. Error crítico a evitar: clasificación por coincidencia textual

El motor no debe inferir clases farmacológicas mediante búsquedas de subcadenas ambiguas.

Ejemplo de error:

```text
"opioide" in "analgésico no opioide"
```

puede producir un falso positivo si la lógica usa coincidencia textual simple.

Esto explicaría resultados observados donde **PARACETAMOL**, clasificado en el catálogo como:

> Analgésico y antipirético no opioide

fue contabilizado como opioide/CNS para B16/B17.

La solución correcta es usar **flags/clases estructuradas**:

```json
{
  "PARACETAMOL": {
    "is_opioid": false,
    "is_beers_cns_active_b17": false
  },
  "GABAPENTINA": {
    "is_gabapentinoid": true,
    "is_beers_cns_active_b17": true
  },
  "ORFENADRINA": {
    "is_skeletal_muscle_relaxant": true,
    "is_strong_anticholinergic": true,
    "is_beers_cns_active_b17": true
  }
}
```

---

# 18. B03 debe funcionar como clasificación de apoyo

La Table 7 incluye orfenadrina entre fármacos con propiedades anticolinérgicas fuertes.

Por tanto:

```text
ORFENADRINA
↓
strong_anticholinergic = true
```

Ese dato puede utilizarse para:

- B12;
- B13;
- B14;
- B18.

Pero no debe producir:

```text
B03 = "Evitar"
```

ni sumarse automáticamente al número de hallazgos PIM.

Visualmente puede aparecer en:

> **Clasificaciones de apoyo**

o dentro de trazabilidad.

---

# 19. Problema etario: protocolo SIGRAM ≥60 vs Beers ≥65

Este punto requiere aprobación metodológica formal.

El paper indica aplicación general ≥65 años.

El protocolo SIGRAM trabaja con población desde 60 años.

## Recomendación

Para ≥65:

> aplicación dentro del ámbito original AGS Beers.

Para 60–64:

> **Aplicación exploratoria / adaptación metodológica del piloto — fuera del ámbito etario original de AGS Beers 2023.**

SIGRAM no debería contabilizar esos resultados exactamente igual que una aplicación canónica sin aprobación del equipo clínico.

Una opción recomendable es mostrar:

```text
Coincidencia potencial Beers
Fuera del ámbito etario original (60–64 años)
No contabilizada como criterio canónico
```

hasta que el Dr. Armando/Torre y el equipo metodológico definan la política final.

---

# 20. Qué debe devolver el backend por criterio

Estructura mínima recomendada:

```json
{
  "criterion_code": "B02",
  "status": "activated",
  "matched_medications": ["ORFENADRINA CITRATO"],
  "trigger_facts": [],
  "missing_data": [],
  "reason": "Se identificó ORFENADRINA CITRATO entre los medicamentos activos del paciente.",
  "recommendation_type": "avoid",
  "recommendation_text": "Evitar",
  "clinical_situation": "...",
  "rationale": "...",
  "quality_of_evidence": "moderate",
  "strength_of_recommendation": "strong",
  "exceptions": [],
  "source": {
    "name": "AGS Beers Criteria",
    "year": 2023,
    "table": "Table 2",
    "section": "Skeletal muscle relaxants",
    "location": "p. 12"
  },
  "operational_formulation": "...",
  "catalog_version": "...",
  "technical_trace": {}
}
```

El campo `reason` debe ser determinístico, no generado por IA.

---

# 21. “Motivo del hallazgo” no es lo mismo que “criterio”

## Criterio

Regla general.

Ejemplo:

> Uso de relajantes musculares esqueléticos para molestias musculoesqueléticas.

## Rationale

Por qué la fuente considera problemática la situación.

## Motivo del hallazgo

Dato específico del paciente.

Ejemplo:

> Se identificó ORFENADRINA CITRATO entre los medicamentos activos del paciente.

Esta separación mejora tanto trazabilidad como comprensión clínica.

---

# 22. No generar “Acciones sugeridas” no respaldadas

Una frase como:

> “Revisar la necesidad de orfenadrina y valorar una alternativa con menor carga anticolinérgica y sedante”

no debe mostrarse como parte oficial de Beers si no está documentada en:

- paper;
- catálogo aprobado;
- otra fuente validada.

La plataforma debe mostrar la Recommendation original:

> **Evitar**

y dejar la decisión terapéutica al profesional.

No generar:

- sustitutos;
- deprescripción automática;
- alternativas;
- órdenes terapéuticas.

---

# 23. Implementación visual recomendada

## 23.1. Tabla principal

Título:

> **Hallazgos Beers**

Badge:

> **X criterios activados**

Columnas:

| Código | Medicamento(s) | Recomendación AGS Beers 2023 | Motivo del hallazgo | Acción |
|---|---|---|---|---|

Eliminar:

- Gravedad;
- Alta;
- Moderada;
- Baja;
- Advertencia;
- alertas confirmadas.

La franja lateral roja puede mantenerse como:

> **indicador de regla activada**

no como gravedad.

---

# 24. Sistema de colores recomendado

Deben existir dos sistemas visuales distintos.

## 24.1. Estado del tamizaje SIGRAM

| Estado | Color | Significado |
|---|---|---|
| `activated` | rojo discreto | Se cumplieron las condiciones |
| `not_evaluable` | ámbar | Faltan datos |
| `manual_review` | morado | Requiere juicio profesional |
| `no_alert` | azul-gris | Evaluado, sin activación |
| `out_of_scope` | gris | Fuera de ámbito |
| `supporting_classification` | gris-azulado | Clasificación auxiliar |

**No usar verde para `no_alert`.**

“Sin hallazgo” no significa “seguro”.

## 24.2. Recommendation Beers

| Tipo | Color del chip |
|---|---|
| Evitar | rojo suave |
| Usar con precaución | ámbar |
| Reducir dosis | azul |
| Monitorizar | turquesa |
| Condicionada | violeta |
| Clasificación de apoyo | gris-azulado |

Estos colores diferencian la **naturaleza de la Recommendation**, no gravedad.

---

# 25. Quality of evidence: representación visual

No usar:

```text
High = verde
Moderate = amarillo
Low = rojo
```

Eso implicaría riesgo.

Usar presentación neutral:

```text
Alta      ●●●
Moderada  ●●○
Baja      ●○○
```

con el mismo tono azul/gris.

---

# 26. Strength of recommendation: representación visual

Mostrar:

- **Fuerte**
- **Débil**

como texto o chip neutral.

No usar color de alarma.

---

# 27. Drawer “Ver detalle”

Orden recomendado:

## Recomendación AGS Beers 2023
**Evitar**

## Criterio / situación evaluada
Relajantes musculares esqueléticos usados para molestias musculoesqueléticas.

## Fundamento clínico — Rationale
Texto derivado del paper.

## Medicamentos implicados
ORFENADRINA CITRATO

## Motivo del hallazgo
Se identificó ORFENADRINA CITRATO entre los medicamentos activos del paciente.

## Datos faltantes
Ninguno.

Luego un bloque:

> **Ver fuente y trazabilidad**

---

# 28. “Ver fuente y trazabilidad”

Debe incluir:

- fuente;
- año;
- tabla;
- sección;
- ubicación;
- calidad de evidencia;
- fuerza de recomendación;
- formulación operativa del catálogo SIGRAM;
- código B;
- versión del catálogo;
- evidencia activadora técnica;
- datos utilizados;
- excepciones;
- cobertura;
- limitaciones.

No debe repetir el “Motivo del hallazgo”.

---

# 29. Contadores superiores

Los contadores deben derivarse de estados y no mezclar métricas de cobertura con resultados.

Recomendado:

- **Criterios activados**
- **Requieren información adicional**
- **Requieren revisión clínica**
- **Sin hallazgo en los datos observados**
- opcional: **Fuera del ámbito**

En texto secundario:

> N criterios Beers candidatos considerados en esta evaluación.

“Candidatos” es una métrica de cobertura, no un estado clínico.

---

# 30. Análisis completo

Organizar en bloques:

1. **Criterios activados**
2. **Requieren información adicional**
3. **Requieren revisión clínica**
4. **Sin hallazgo en los datos observados**
5. **Clasificaciones de apoyo**
6. **Fuera del ámbito**

B03 debe ir en **Clasificaciones de apoyo**, no como `no_alert` ni como criterio activado.

---

# 31. Problemas observados en la implementación actual que deben auditarse

## 31.1. B16 — falso positivo por paracetamol

Se observó una versión donde B16 aparecía activado con:

> GABAPENTINA + PARACETAMOL

pero el catálogo clasifica paracetamol como **no opioide**.

Esto es incorrecto.

B16 requiere:

```text
opioide + gabapentinoide
```

Debe revisarse el clasificador de clases farmacológicas.

## 31.2. B17 — conteo incorrecto de SNC

Se observó:

> GABAPENTINA + ORFENADRINA + PARACETAMOL

contabilizados como 3 medicamentos SNC.

Paracetamol no pertenece a las clases Beers del criterio B17.

Resultado correcto con solo gabapentina + orfenadrina:

```text
count = 2
status = no_alert
```

## 31.3. B03

No debe restaurarse como “alerta” solo para reproducir la versión anterior.

Su eliminación como hallazgo clínico independiente es metodológicamente correcta si se conserva como clasificación.

## 31.4. B05

Que desaparezca como hallazgo automático puede ser correcto si antes se activaba únicamente por detectar un AINE.

Debe revisar sus condiciones reales.

## 31.5. B01 y B10

La reducción de hallazgos tras añadir contexto no debe asumirse como regresión sin revisar:

- estado;
- dato faltante;
- excepción;
- lógica del criterio.

No revertir todo el motor solo para igualar el número de alertas de una versión anterior.

---

# 32. Pruebas mínimas obligatorias

## B02

```text
Paciente ≥65 + orfenadrina
→ activated
→ Recommendation = Avoid
```

## B03

```text
orfenadrina
→ supporting_classification
→ strong anticholinergic
→ no PIM independiente
```

## B04

```text
IBP <8 semanas
→ no_alert

IBP >8 semanas sin excepción
→ activated
```

## B06

```text
AINE + IC sintomática
→ activated / Avoid

AINE + IC asintomática
→ activated / Use with caution

AINE + IC + estado sintomático desconocido
→ not_evaluable
```

## B11

```text
criterio cumplido
→ Use with caution
```

## B15

```text
opioide sin benzodiacepina
→ no_alert

opioide + benzodiacepina
→ activated
```

## B16

```text
gabapentina sola
→ no_alert

gabapentina + paracetamol
→ no_alert

gabapentina + opioide válido
→ activated
```

## B17

```text
2 fármacos SNC válidos
→ no_alert

3 fármacos SNC válidos
→ activated
```

## B18

```text
1 anticolinérgico fuerte
→ no_alert

≥2
→ activated
```

## B19

```text
gabapentina + función renal <60
→ Reduce dose

función renal desconocida
→ not_evaluable
```

## B20

```text
tramadol IR + CrCl <30
→ Reduce dose

tramadol ER + CrCl <30
→ Avoid
```

## B21

```text
un ARA-II aislado
→ no_alert

combinación requerida + ERC ≥3a
→ activated
```

## B23

```text
tamsulosina + contexto relevante
→ manual_review
```

---

# 33. Reproducibilidad y versionado

Cada evaluación debe conservar el catálogo y regla utilizados.

No basta guardar:

```text
B02
```

Debe persistirse o snapshotearse:

- código;
- versión del catálogo;
- status;
- recommendation;
- rationale relevante;
- source metadata;
- trigger facts;
- medicamentos implicados;
- missing data.

Así una evaluación histórica no cambia retroactivamente cuando el catálogo se actualiza.

---

# 34. Flujo de validación clínica recomendado

Antes de considerar B01–B23 definitivos:

## Etapa 1 — Auditoría documental

Por cada B:

- revisar paper;
- revisar catálogo Dr. Armando;
- revisar código;
- documentar diferencias.

## Etapa 2 — Validación de la regla computable

Construir casos:

- positivo;
- negativo;
- dato faltante;
- excepción;
- borde.

## Etapa 3 — Revisión clínica

Presentar al Dr. Armando/equipo:

- criterio original;
- formulación operativa;
- lógica computable;
- salidas de prueba.

## Etapa 4 — Congelamiento de versión

Solo después:

```text
catalog_version = validated
```

---

# 35. Matriz recomendada para auditoría B01–B23

Crear un archivo versionado, por ejemplo:

```text
docs/beers_2023_audit.md
```

con columnas:

| Código | Tabla | Catálogo Dr. Armando | Recommendation paper | Rationale | Quality | Strength | Datos requeridos | Excepciones | Implementación | Estado validación |
|---|---|---|---|---|---|---|---|---|---|---|

Los valores deben distinguir:

- **validado contra paper**;
- **adaptación operativa**;
- **pendiente de validación clínica**;
- **error de implementación**.

---

# 36. Definition of Done del módulo Beers

El módulo Beers puede considerarse correctamente implementado cuando:

- [ ] B01–B23 fueron auditados individualmente.
- [ ] El paper y el catálogo operativo están diferenciados.
- [ ] El Excel del Dr. Armando se conserva como fuente operacional.
- [ ] El motor distingue candidato de activado.
- [ ] B03 es clasificación de apoyo.
- [ ] B16 requiere un opioide real.
- [ ] B17 cuenta solo clases SNC válidas y exige ≥3.
- [ ] No se usan coincidencias de texto ambiguas para clases farmacológicas.
- [ ] B19 devuelve “Reducir dosis”.
- [ ] B20 distingue IR y ER.
- [ ] B23 se mantiene en revisión clínica mientras no haya aprobación distinta.
- [ ] `not_evaluable` no se interpreta como ausencia de riesgo.
- [ ] `no_alert` no se muestra como “seguro”.
- [ ] Se maneja explícitamente el ámbito ≥65.
- [ ] Recommendation, Rationale, Quality y Strength están separados.
- [ ] No existe una gravedad Beers inventada.
- [ ] No existen “Acciones sugeridas” no respaldadas.
- [ ] El frontend usa colores semánticamente correctos.
- [ ] Las evaluaciones históricas conservan versión.
- [ ] Los tests clínicos y técnicos pasan.
- [ ] STOPP/START y DDInter no presentan regresiones.

---

# 37. Conclusión final

El catálogo del Dr. Armando **no compite con AGS Beers 2023; lo operacionaliza para SIGRAM-AM**.

El paper responde:

> **qué criterios existen, por qué, qué recomienda el panel y con qué evidencia.**

El catálogo responde:

> **qué parte de ese conocimiento es relevante para los 54 medicamentos del piloto y dónde está ubicada en la fuente.**

El backend debe responder:

> **qué condiciones concretas hacen que esa regla se active en este paciente.**

El frontend debe responder:

> **qué encontró SIGRAM, qué recomienda realmente AGS Beers, por qué se activó y de dónde proviene la información.**

Por tanto, la arquitectura final debe evitar dos extremos:

### Error 1
Copiar literalmente el Excel y asumir:

```text
medicamento presente = criterio activado
```

### Error 2
Ignorar el catálogo clínico y reconstruir Beers de manera independiente por software.

La solución correcta es:

```text
PAPER ORIGINAL
+
CATÁLOGO OPERATIVO CURADO
+
REGLA COMPUTABLE VALIDADA
+
TRAZABILIDAD DEL PACIENTE
```

Esta estructura es coherente con la finalidad investigacional de SIGRAM-AM: un sistema de **tamizaje clínico trazable, reproducible y sometido a revisión profesional**, no un sistema autónomo de prescripción.

---

# 38. Fuentes de referencia utilizadas

1. **By the 2023 American Geriatrics Society Beers Criteria® Update Expert Panel.**  
   *American Geriatrics Society 2023 updated AGS Beers Criteria® for potentially inappropriate medication use in older adults.*  
   Journal of the American Geriatrics Society. 2023;71:2052–2081. DOI: 10.1111/jgs.18372.

2. **Catálogo clínico operativo del piloto SIGRAM-AM:**  
   `top_meds_list_beers_stopp_start_v3-20260730(2).xlsx`  
   Hojas analizadas: `Medicamentos` y `Ubicación de criterios`.

3. **Protocolo vigente SIGRAM-AM / Anexo 9**, utilizado como referencia metodológica para el alcance del piloto.

4. **Descripción técnica y guía de usuario de SIGRAM-AM**, utilizadas para relacionar la estructura clínica con el backend/frontend actual.

---

## Nota de control metodológico

Cuando exista una diferencia entre:

```text
paper AGS Beers 2023
vs.
catálogo operativo del Dr. Armando
vs.
implementación actual del motor
```

la discrepancia **no debe corregirse silenciosamente**.

Debe clasificarse como:

- adaptación operativa intencional;
- simplificación;
- posible error de transcripción;
- error de implementación;
- pendiente de validación clínica.

Si no puede resolverse con las fuentes disponibles:

> **PENDIENTE DE VALIDACIÓN CLÍNICA**

