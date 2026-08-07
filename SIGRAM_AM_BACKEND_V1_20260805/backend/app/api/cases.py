from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List
from backend.app.database import get_db
from backend.app.schemas.cases import ClinicalCaseCreate, ClinicalCaseRead, ClinicalCaseList, ErrorResponse
from backend.app.services.case_service import CaseService

router = APIRouter(prefix="/api/cases", tags=["Cases"])

@router.post(
    "",
    response_model=ClinicalCaseRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_409_CONFLICT: {"model": ErrorResponse, "description": "Código de caso duplicado."},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Error de validación en los datos."}
    }
)
def create_case(case_data: ClinicalCaseCreate, db: Session = Depends(get_db)):
    """Crea un caso clínico simulado de adulto mayor (>= 60 años) junto con sus medicamentos."""
    return CaseService.create_case(db, case_data)


@router.get(
    "",
    response_model=List[ClinicalCaseList],
    status_code=status.HTTP_200_OK
)
def list_cases(db: Session = Depends(get_db)):
    """Lista todos los casos clínicos simulados registrados (sin incluir la lista detallada de medicamentos)."""
    return CaseService.list_cases(db)


@router.get(
    "/{case_id}",
    response_model=ClinicalCaseRead,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Caso no encontrado."}
    }
)
def get_case(case_id: int, db: Session = Depends(get_db)):
    """Recupera la información completa de un caso clínico por su ID, incluyendo sus medicamentos."""
    return CaseService.get_case(db, case_id)


@router.delete(
    "/{case_id}",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Caso no encontrado."},
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse, "description": "Restricción de borrado para no simulados."}
    }
)
def delete_case(case_id: int, db: Session = Depends(get_db)):
    """Elimina únicamente un caso clínico simulado por su ID, junto con todos sus medicamentos en cascada."""
    CaseService.delete_case(db, case_id)
    return {"detail": f"Caso clínico {case_id} eliminado exitosamente."}
