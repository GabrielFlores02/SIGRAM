from contextlib import asynccontextmanager
from fastapi import FastAPI
from backend.app.config import settings
from backend.app.database import init_db
from backend.app.api.health import router as health_router
from backend.app.api.cases import router as cases_router
from backend.app.api.evaluations import router as evaluations_router
from backend.app.api.catalog import router as catalog_router
from backend.app.api.pilot import router as pilot_router
from backend.app.schemas.responses import IndexResponse

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicializar la base de datos SQLite (crear tablas vacías si las hay)
    init_db()
    yield

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Incluir las rutas
app.include_router(health_router)
app.include_router(cases_router)
app.include_router(evaluations_router)
app.include_router(catalog_router)
app.include_router(pilot_router)

@app.get("/", response_model=IndexResponse)
def index():
    """Endpoint raíz con metadatos y advertencia de uso."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "proof-of-concept",
        "warning": "No utilizar para decisiones clínicas"
    }
