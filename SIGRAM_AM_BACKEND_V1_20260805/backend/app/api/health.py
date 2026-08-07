import sys
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.app.database import get_db
from backend.app.config import settings
from backend.app.schemas.responses import HealthResponse

router = APIRouter()

@router.get("/health", response_model=HealthResponse)
def health_check(db: Session = Depends(get_db)):
    """Verifica el estado del servicio y de la conexión a la base de datos.

    Retorna HTTP 200 si la base de datos está disponible.
    Retorna HTTP 503 si la base de datos no responde.
    No expone detalles internos de excepciones.
    """
    python_ver = sys.version.split()[0]

    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "application": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.APP_ENV,
            "python_version": python_ver,
            "database": "available"
        }
    except Exception:
        payload = HealthResponse(
            status="degraded",
            application=settings.APP_NAME,
            version=settings.APP_VERSION,
            environment=settings.APP_ENV,
            python_version=python_ver,
            database="unavailable"
        )
        return JSONResponse(
            status_code=503,
            content=payload.model_dump()
        )
