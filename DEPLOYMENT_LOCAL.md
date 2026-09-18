# Despliegue local de SIGRAM-AM

## Inicio

Abra PowerShell en esta carpeta y ejecute:

```powershell
.\run-local.ps1
```

Servicios:

- Aplicación web: http://127.0.0.1:8089
- API FastAPI: http://127.0.0.1:8002
- Swagger: http://127.0.0.1:8002/docs

## Operación

```powershell
docker compose ps
docker compose logs --follow
.\stop-local.ps1
```

`stop-local.ps1` detiene los contenedores y conserva los casos simulados. El volumen persistente se llama `sigram_backend_data_dev`.

No ejecute `docker compose down -v` salvo que quiera borrar de forma definitiva la base local de casos.

## Reconstrucción después de cambios

```powershell
docker compose up --build --detach
```

## Cohorte y catálogo Rebagliati 2025

- La entrega se monta en modo solo lectura desde `SIGRAM_Rebagliati_2025_Entrega_Desarrollador`.
- Directorio: 181,356 pacientes; medicamentos, CIE-10 y laboratorios se consultan con DuckDB por `patient_code`, sin cargarlos completos en cada solicitud.
- La lista usa `GET /api/pilot/v1/sample-patients?offset=0&limit=50` y búsqueda opcional por `query`.
- Alcance operativo de investigación: 54 medicamentos, 23 criterios Beers, 74 criterios STOPP/START y DDInter local. Las brechas de contexto permanecen como no evaluables y requieren revisión profesional.
- La ausencia de una fila de laboratorio o CIE-10 se presenta como dato no registrado, nunca como normalidad o ausencia de enfermedad.
- Antes de un despliegue, verifique `05_Manifiesto/CHECKSUMS_SHA256.txt` de la entrega.

## Seguridad metodológica

El entorno es un prototipo de investigación. Utilice únicamente casos simulados o pseudonimizados. Los resultados son tamizajes y requieren revisión profesional; no deben emplearse como decisiones clínicas directas.
