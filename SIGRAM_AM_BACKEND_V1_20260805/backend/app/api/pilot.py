from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.database import get_db
from backend.app.schemas.pilot import (
    PilotSampleEvaluationRequest,
    PilotSampleEvaluationResponse,
    PilotSamplePatient,
)
from backend.app.services.pilot_sample_service import PilotSampleService
from backend.app.services.rebagliati_population_service import RebagliatiPopulationService


router = APIRouter(prefix="/api/pilot/v1", tags=["SIGRAM population"])


def _population_service():
    if settings.SIGRAM_DATASET_MODE.strip().lower() == "rebagliati":
        return RebagliatiPopulationService()
    return PilotSampleService()


@router.get("/sample-patients")
def list_sample_patients(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    query: str | None = None,
    sort: str = Query(
        "patient_code", pattern="^(patient_code|alerts|engine_alerts)$"
    ),
):
    """Lista los 10 pacientes pseudonimizados preparados para validar la V1."""
    service = _population_service()
    if isinstance(service, RebagliatiPopulationService):
        return service.list_patients(
            offset=offset, limit=limit, query=query, sort=sort
        )
    return service.list_patients()


@router.get("/simple-patients")
def list_simple_patients(
    query: str | None = None,
    limit: int = Query(50, ge=1, le=200),
):
    """Lista casos demostrativos y permite buscar un paciente por código."""
    service = _population_service()
    if isinstance(service, RebagliatiPopulationService):
        return service.list_simple_patients(query=query, limit=limit)
    items = service.list_patients()
    if query and query.strip():
        needle = query.strip().lower()
        items = [item for item in items if needle in item["patient_code"].lower()]
    return {"items": items[:limit], "total": len(items), "offset": 0, "limit": limit}


@router.get("/sample-patients/{patient_code}/research-data")
def get_sample_patient_research_data(patient_code: str):
    """Expone datos pseudonimizados y trazabilidad para validación metodológica."""
    return _population_service().research_data(patient_code)


@router.get("/sample-patients/{patient_code}/case-prefill")
def get_sample_patient_case_prefill(patient_code: str):
    """Carga la historia pseudonimizada para editarla en Nuevo caso, sin persistirla."""
    return _population_service().case_prefill(patient_code)


@router.post(
    "/sample-patients/{patient_code}/evaluate",
    response_model=PilotSampleEvaluationResponse,
    status_code=status.HTTP_200_OK,
)
def evaluate_sample_patient(
    patient_code: str,
    request: PilotSampleEvaluationRequest | None = None,
    db: Session = Depends(get_db),
):
    """Crea un caso simulado desde la muestra y ejecuta los tres analizadores."""
    clinical_context = request.clinical_context if request else None
    index_date = request.index_date if request else None
    return _population_service().evaluate(
        db,
        patient_code,
        clinical_context,
        requested_index_date=index_date,
    )
