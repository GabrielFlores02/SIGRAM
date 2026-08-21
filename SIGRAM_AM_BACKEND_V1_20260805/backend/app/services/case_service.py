from sqlalchemy.orm import Session
from typing import List
from fastapi import HTTPException, status
from backend.app.models.models import ClinicalCase, Medication
from backend.app.schemas.cases import ClinicalCaseCreate
from backend.app.repositories.case_repository import CaseRepository
from backend.app.services.medication_normalizer import normalize_active_ingredient
from backend.app.services.renal_function_service import enrich_with_cockcroft_gault

class CaseService:
    @staticmethod
    def create_case(db: Session, case_data: ClinicalCaseCreate) -> ClinicalCase:
        """Crea un caso clínico simulado y sus medicamentos asociados, validando unicidad de código."""
        # 1. Validar que no exista ya un caso con el mismo código único
        existing_case = CaseRepository.get_by_code(db, case_data.case_code)
        if existing_case:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"El código de caso '{case_data.case_code}' ya se encuentra registrado."
            )

        # 2. Instanciar entidad ClinicalCase
        clinical_context = enrich_with_cockcroft_gault(
            case_data.clinical_context.model_dump(),
            age=case_data.age,
            sex=case_data.sex,
        )
        clinical_case = ClinicalCase(
            case_code=case_data.case_code,
            age=case_data.age,
            sex=case_data.sex,
            diagnoses=case_data.diagnoses,
            clinical_context=clinical_context,
            is_simulated=case_data.is_simulated,
            status="active"
        )

        # 3. Normalizar e instanciar medicamentos asociados
        for med in case_data.medications:
            normalized_ingredient = normalize_active_ingredient(med.normalized_active_ingredient)
            medication = Medication(
                entered_name=med.entered_name,
                normalized_active_ingredient=normalized_ingredient,
                dose=med.dose,
                dose_unit=med.dose_unit,
                frequency=med.frequency,
                duration=med.duration,
                route=med.route
            )
            clinical_case.medications.append(medication)

        # 4. Guardar mediante repositorio
        return CaseRepository.create(db, clinical_case)

    @staticmethod
    def get_case(db: Session, case_id: int) -> ClinicalCase:
        """Recupera un caso clínico o lanza excepción 404 si no existe."""
        case_obj = CaseRepository.get_by_id(db, case_id)
        if not case_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Caso clínico con ID {case_id} no encontrado."
            )
        return case_obj

    @staticmethod
    def list_cases(db: Session) -> List[ClinicalCase]:
        """Lista todos los casos clínicos simulados."""
        return CaseRepository.list_all(db)

    @staticmethod
    def delete_case(db: Session, case_id: int) -> None:
        """Elimina un caso clínico simulado de la base de datos."""
        case_obj = CaseRepository.get_by_id(db, case_id)
        if not case_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Caso clínico con ID {case_id} no encontrado."
            )

        # Restringir a la eliminación única de casos simulados
        if not case_obj.is_simulated:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo se permite eliminar casos clínicos simulados."
            )

        CaseRepository.delete(db, case_obj)
