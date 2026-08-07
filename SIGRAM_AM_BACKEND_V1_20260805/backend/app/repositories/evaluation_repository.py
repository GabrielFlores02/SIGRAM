from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Optional
from datetime import datetime
from backend.app.models.models import EvaluationExecution, Alert

class EvaluationRepository:
    @staticmethod
    def create_execution(db: Session, execution: EvaluationExecution) -> EvaluationExecution:
        """Crea y persiste una nueva ejecución de evaluación."""
        try:
            db.add(execution)
            db.commit()
            db.refresh(execution)
            return execution
        except SQLAlchemyError as e:
            db.rollback()
            raise e

    @staticmethod
    def get_execution_by_id(db: Session, execution_id: int) -> Optional[EvaluationExecution]:
        """Recupera una ejecución de evaluación por su ID."""
        return db.query(EvaluationExecution).filter(EvaluationExecution.id == execution_id).first()

    @staticmethod
    def get_latest_execution_for_case(db: Session, case_id: int) -> Optional[EvaluationExecution]:
        """Obtiene la ejecución de evaluación más reciente para un caso específico."""
        return db.query(EvaluationExecution)\
            .filter(EvaluationExecution.case_id == case_id)\
            .order_by(EvaluationExecution.started_at.desc(), EvaluationExecution.id.desc())\
            .first()

    @staticmethod
    def add_alert(db: Session, alert: Alert) -> Alert:
        """Agrega y persiste una alerta asociada a una ejecución."""
        try:
            db.add(alert)
            db.commit()
            db.refresh(alert)
            return alert
        except SQLAlchemyError as e:
            db.rollback()
            raise e

    @staticmethod
    def list_alerts_for_execution(db: Session, execution_id: int) -> List[Alert]:
        """Lista todas las alertas registradas para una ejecución específica."""
        return db.query(Alert).filter(Alert.execution_id == execution_id).all()

    @staticmethod
    def update_execution_result(
        db: Session,
        execution_id: int,
        successful: bool,
        functional_error: bool,
        error_detail: Optional[str],
        processing_time_ms: Optional[float],
        total_medications: int,
        total_alerts: int,
        finished_at: datetime,
        criteria_report: Optional[list] = None,
    ) -> Optional[EvaluationExecution]:
        """Actualiza el resultado y métricas de una ejecución existente."""
        try:
            execution = db.query(EvaluationExecution).filter(EvaluationExecution.id == execution_id).first()
            if execution:
                execution.successful = successful
                execution.functional_error = functional_error
                execution.error_detail = error_detail
                execution.processing_time_ms = processing_time_ms
                execution.total_medications = total_medications
                execution.total_alerts = total_alerts
                if criteria_report is not None:
                    execution.criteria_report = criteria_report
                execution.finished_at = finished_at
                db.commit()
                db.refresh(execution)
            return execution
        except SQLAlchemyError as e:
            db.rollback()
            raise e
