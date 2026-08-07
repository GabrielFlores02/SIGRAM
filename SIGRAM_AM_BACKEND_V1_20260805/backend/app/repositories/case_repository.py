from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
from fastapi import HTTPException, status
from backend.app.models.models import ClinicalCase

class CaseRepository:
    @staticmethod
    def get_by_id(db: Session, case_id: int) -> Optional[ClinicalCase]:
        """Recupera un caso clínico simulado por su ID, incluyendo sus medicamentos asociados."""
        return db.query(ClinicalCase).filter(ClinicalCase.id == case_id).first()

    @staticmethod
    def get_by_code(db: Session, case_code: str) -> Optional[ClinicalCase]:
        """Recupera un caso por su código único (case_code) para validaciones de duplicados."""
        return db.query(ClinicalCase).filter(ClinicalCase.case_code == case_code).first()

    @staticmethod
    def create(db: Session, case_obj: ClinicalCase) -> ClinicalCase:
        """Persiste un caso clínico y sus medicamentos en la base de datos.

        Captura IntegrityError (ej. violación de unicidad de case_code por
        concurrencia) y lo convierte en HTTP 409 tras ejecutar rollback.
        """
        try:
            db.add(case_obj)
            db.commit()
            db.refresh(case_obj)
            return case_obj
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"El código de caso '{case_obj.case_code}' ya se encuentra registrado (conflicto de integridad)."
            )

    @staticmethod
    def list_all(db: Session) -> List[ClinicalCase]:
        """Lista todos los casos clínicos simulados registrados."""
        return db.query(ClinicalCase).all()

    @staticmethod
    def delete(db: Session, case_obj: ClinicalCase) -> None:
        """Elimina un caso clínico simulado de la base de datos (con cascada de medicamentos)."""
        db.delete(case_obj)
        db.commit()
