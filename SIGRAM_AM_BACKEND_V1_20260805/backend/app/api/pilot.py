from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.schemas.pilot import (
    PilotSampleEvaluationRequest,
    PilotSampleEvaluationResponse,
    PilotSamplePatient,
)
from backend.app.services.pilot_sample_service import PilotSampleService


router = APIRouter(prefix="/api/pilot/v1", tags=["Pilot sample V1"])


@router.get("/sample-patients", response_model=list[PilotSamplePatient])
def list_sample_patients():
    """Lista los 10 pacientes pseudonimizados preparados para validar la V1."""
    return PilotSampleService().list_patients()


@router.get("/sample-patients/{patient_code}/research-data")
def get_sample_patient_research_data(patient_code: str):
    """Expone datos pseudonimizados y trazabilidad para validación metodológica."""
    return PilotSampleService().research_data(patient_code)


@router.get("/sample-patients/{patient_code}/case-prefill")
def get_sample_patient_case_prefill(patient_code: str):
    """Carga la historia pseudonimizada para editarla en Nuevo caso, sin persistirla."""
    return PilotSampleService().case_prefill(patient_code)


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
    return PilotSampleService().evaluate(
        db,
        patient_code,
        clinical_context,
        requested_index_date=index_date,
    )
