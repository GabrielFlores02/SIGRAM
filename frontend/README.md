# Frontend SIGRAM-AM

Aplicación React + TypeScript conectada al backend FastAPI entregado en `SIGRAM_AM_BACKEND_V1_20260731`.

## Desarrollo local

1. Inicie el backend desde la raíz del paquete entregado:

   ```powershell
   .\scripts\start_backend.ps1
   ```

2. En otra terminal:

   ```powershell
   cd frontend
   npm install
   npm run dev
   ```

3. Abra `http://127.0.0.1:5173`.

Vite redirige `/api` a `http://127.0.0.1:8000`, por lo que el backend no necesita habilitar CORS durante el desarrollo local.

## Despliegue local con Docker

Desde la carpeta raíz del proyecto ejecute:

```powershell
.\run-local.ps1
```

La aplicación queda disponible en `http://127.0.0.1:8088` y la documentación del backend en `http://127.0.0.1:8001/docs`.

Para detenerla:

```powershell
.\stop-local.ps1
```

El volumen `sigram_backend_data` conserva los casos simulados entre reinicios. Use `docker compose down -v` únicamente si desea eliminar definitivamente esos datos.

## Alcance

- Lista casos simulados y la muestra pseudonimizada del piloto.
- Crea casos simulados y ejecuta la evaluación.
- Renderiza exclusivamente criterios Beers y STOPP/START.
- Presenta `alert`, `manual_review`, `not_evaluable` y `no_alert`.
- Obtiene dinámicamente los campos clínicos requeridos desde el catálogo V1.
- No incluye autenticación, edición ni funciones de prescripción porque el backend no ofrece esos contratos.
