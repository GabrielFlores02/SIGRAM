# Despliegue local de SIGRAM-AM

## Inicio

Abra PowerShell en esta carpeta y ejecute:

```powershell
.\run-local.ps1
```

Servicios:

- Aplicación web: http://127.0.0.1:8088
- API FastAPI: http://127.0.0.1:8001
- Swagger: http://127.0.0.1:8001/docs
- Salud a través del frontend: http://127.0.0.1:8088/health

## Operación

```powershell
docker compose ps
docker compose logs --follow
.\stop-local.ps1
```

`stop-local.ps1` detiene los contenedores y conserva los casos simulados. El volumen persistente se llama `sigram_backend_data`.

No ejecute `docker compose down -v` salvo que quiera borrar de forma definitiva la base local de casos.

## Reconstrucción después de cambios

```powershell
docker compose up --build --detach
```

## Catálogo clínico de pruebas

- Fuente inmutable: `SIGRAM_AM_BACKEND_V1_20260731/data/raw/top_meds_list_beers_stopp_start_v3-20260730.xlsx`.
- SHA-256: `96912d52ed3ff8e30d8c5cc4545dd6bdcc5422e35b971448725b9b1073bed05f`.
- Alcance: 54 medicamentos, 23 criterios Beers y 74 criterios STOPP/START.
- Backend vigente: `SIGRAM_AM_BACKEND_V1_20260805`, con evidencia positiva y trazable de CIE-10 para la muestra pseudonimizada del piloto. La ausencia de un CIE-10 no se interpreta como ausencia de enfermedad.
- El formulario utiliza solamente los 54 medicamentos del catálogo.
- ATC y cuarto nivel de clasificación farmacológica permanecen pendientes de validación por el equipo clínico. El sistema no asigna valores inferidos.

## Seguridad metodológica

El entorno es un prototipo de investigación. Utilice únicamente casos simulados o pseudonimizados. Los resultados son tamizajes y requieren revisión profesional; no deben emplearse como decisiones clínicas directas.
