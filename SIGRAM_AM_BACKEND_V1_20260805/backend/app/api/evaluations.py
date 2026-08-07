from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.schemas.evaluations import EvaluationExecutionRead
from backend.app.services.evaluation_service import EvaluationService
from backend.app.repositories.evaluation_repository import EvaluationRepository

router = APIRouter(prefix="/api", tags=["Evaluations"])

@router.post(
    "/cases/{case_id}/evaluate",
    response_model=EvaluationExecutionRead,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Caso no encontrado."},
        status.HTTP_400_BAD_REQUEST: {"description": "El caso no es simulado."},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "El caso no tiene medicamentos."},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Error interno durante la evaluación."}
    }
)
def evaluate_case(case_id: int, db: Session = Depends(get_db)):
    """Ejecuta la evaluación determinística demostrativa sobre un caso clínico simulado."""
    return EvaluationService.evaluate_case(db, case_id)


@router.get(
    "/cases/{case_id}/results",
    response_model=EvaluationExecutionRead,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Caso o evaluación no encontrados."}
    }
)
def get_latest_results(case_id: int, db: Session = Depends(get_db)):
    """Obtiene la ejecución de evaluación más reciente para un caso y sus alertas."""
    from backend.app.repositories.case_repository import CaseRepository
    case = CaseRepository.get_by_id(db, case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Caso clínico con ID {case_id} no encontrado."
        )

    execution = EvaluationRepository.get_latest_execution_for_case(db, case_id)
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontraron evaluaciones previas para el caso clínico con ID {case_id}."
        )
    return execution


@router.get(
    "/executions/{execution_id}",
    response_model=EvaluationExecutionRead,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Ejecución no encontrada."}
    }
)
def get_execution(execution_id: int, db: Session = Depends(get_db)):
    """Obtiene una ejecución de evaluación específica por su ID junto con sus alertas."""
    execution = EvaluationRepository.get_execution_by_id(db, execution_id)
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ejecución de evaluación con ID {execution_id} no encontrada."
        )
    return execution
