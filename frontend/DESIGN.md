# Sistema de diseño — SIGRAM-AM

Fuente visual: proyecto de Google Stitch **Frontend SIGRAM-AM EsSalud**, pantallas finales `Nuevo Caso - SIGRAM-AM (Actualizado)` y `Resultado de Evaluación - SIGRAM-AM (Actualizado)`. Se prioriza el manual de identidad de EsSalud cuando existe una diferencia con el código generado por Stitch.

## Identidad

- Tipografía: Tahoma; respaldo Arial y `sans-serif`.
- Logotipo: versión horizontal principal de EsSalud, obtenida del Manual de Identidad Corporativa 2016, sin alterar sus proporciones.
- Azul institucional principal: `#007AC9`.
- Celeste institucional: `#3DB7E4`.
- Turquesa de apoyo: `#00A79C`.
- Verde de estado sin alerta: `#00A557`.
- Naranja de revisión: `#F5871F`.
- Rojo reservado para errores técnicos o advertencias críticas: `#BA1A1A`.
- Superficie: `#F8FAFB`; superficie tenue: `#F2F4F5`; borde: `#C0C7D3`.

## Escala y composición

- Contenedor máximo: 1280 px.
- Padding principal: 24 px.
- Espaciado base: 4 px; pasos predominantes: 8, 16, 24 y 32 px.
- Radios: 3–4 px en controles; 6–8 px en tarjetas; redondo solo para estados.
- Sombra discreta: `0 2px 8px rgba(0,48,82,.08)`.
- Tablas con encabezado gris claro, divisores horizontales y desplazamiento horizontal en pantallas pequeñas.

## Componentes

- Cabecera institucional con el logotipo horizontal oficial, nombre del piloto y unidad responsable.
- Navegación primaria: `Casos del piloto` y `Nuevo caso`.
- Formularios en tarjetas; encabezados azules y campos con foco institucional.
- Tarjetas de indicadores: Alertas, Evaluados, No evaluables y Revisión manual.
- Estados de criterio: Advertencia, Revisión manual, No evaluable y Sin alerta.
- Detalle de criterio en panel lateral con código, criterio, medicamentos, justificación, fuente, versión y datos faltantes.
- Aviso permanente de investigación al pie de todas las pantallas.

## Reglas funcionales de interfaz

- Mostrar solamente Beers y STOPP/START; DDInter permanece oculto en esta versión.
- No generar puntaje clínico compuesto.
- No mostrar acciones de prescripción, suspensión, sustitución ni ajuste de dosis.
- La nota metodológica de Beers solo aparece para edades de 60 a 64 años.
- Los campos de contexto clínico se obtienen de `GET /api/catalog/v1/criteria`.
- Mantener separados los errores técnicos de los hallazgos clínicos.
- Mostrar `no_alert` como “Sin alerta” para confirmar que el criterio fue evaluado.

## Responsive

- Escritorio: tablas y formularios completos hasta 1280 px.
- Tablet: medicamentos en cuatro columnas y contexto clínico en dos.
- Móvil: formularios en una columna, indicadores en dos columnas y tablas con desplazamiento horizontal.
