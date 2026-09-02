import logging
import time
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from backend.app.models.models import EvaluationExecution, Alert
from backend.app.repositories.case_repository import CaseRepository
from backend.app.repositories.evaluation_repository import EvaluationRepository
from backend.app.services.rule_engine import RuleEngine
from backend.app.services.clinical_catalog_service import ClinicalCatalogService


logger = logging.getLogger(__name__)

class EvaluationService:
    @staticmethod
    def evaluate_case(db: Session, case_id: int) -> EvaluationExecution:
        """Orquesta la evaluación de un caso clínico simulado.

        1. Busca el caso en el repositorio.
        2. Valida que exista y que sea simulado (is_simulated=True).
        3. Valida que contenga medicamentos.
        4. Crea e inserta la ejecución inicial con exitosa=False.
        5. Corre el motor de reglas demostrativo y calcula tiempos con perf_counter.
        6. Mapea y persiste las alertas demostrativas generadas.
        7. Actualiza y consolida la ejecución como exitosa.
        8. Ejecuta rollback y marca error controlado en caso de fallos inesperados.
        """
        # 1. Buscar el caso
        case = CaseRepository.get_by_id(db, case_id)
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Caso clínico con ID {case_id} no encontrado."
            )

        # 2. Verificar que sea un caso simulado
        if not case.is_simulated:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo se permite evaluar casos clínicos simulados."
            )

        # 3. Verificar que tenga medicamentos
        if not case.medications:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="El caso clínico no contiene medicamentos registrados para evaluar."
            )

        # 4. Crear la ejecución inicial
        execution = EvaluationExecution(
            case_id=case.id,
            started_at=datetime.now(timezone.utc),
            successful=False,
            functional_error=False,
            total_medications=len(case.medications),
            total_alerts=0,
            criteria_report=[],
        )
        try:
            execution = EvaluationRepository.create_execution(db, execution)
        except SQLAlchemyError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No se pudo registrar la ejecución de la evaluación."
            )

        start_time = time.perf_counter()

        try:
            # 5. Ejecutar el RuleEngine
            active_ingredients = [med.normalized_active_ingredient for med in case.medications]
            engine_alerts = RuleEngine.evaluate(active_ingredients)
            clinical_alerts, criteria_report = ClinicalCatalogService().evaluate(
                case.medications,
                age=case.age,
                sex=case.sex,
                clinical_context=case.clinical_context or {},
            )
            engine_alerts.extend(clinical_alerts)
            severity_priority = {"alta": 1, "moderada": 2, "advertencia": 3}
            engine_alerts.sort(
                key=lambda item: severity_priority.get(item["severity"], 4)
            )

            # 6. Convertir y persistir las alertas
            alert_objs = []
            for alert_data in engine_alerts:
                # Actualizar trace_data con campos obligatorios
                trace = dict(alert_data["trace_data"])
                trace["execution_id"] = execution.id
                trace["case_id"] = case.id
                trace["evaluated_at"] = datetime.now(timezone.utc).isoformat()

                alert_obj = Alert(
                    execution_id=execution.id,
                    rule_code=alert_data["rule_code"],
                    alert_type=alert_data["alert_type"],
                    problem_identified=alert_data["problem_identified"],
                    implicated_medications=alert_data["implicated_medications"],
                    severity=alert_data["severity"],
                    recommendation=alert_data["recommendation"],
                    justification=alert_data["justification"],
                    source=alert_data["source"],
                    rule_version=alert_data["rule_version"],
                    is_demo=alert_data["is_demo"],
                    trace_data=trace,
                    created_at=datetime.now(timezone.utc)
                )
                alert_objs.append(alert_obj)

            # Agregar alertas una a una al repositorio
            for a in alert_objs:
                EvaluationRepository.add_alert(db, a)

            processing_time_ms = (time.perf_counter() - start_time) * 1000.0

            # 7. Actualizar la ejecución como exitosa
            execution = EvaluationRepository.update_execution_result(
                db,
                execution_id=execution.id,
                successful=True,
                functional_error=False,
                error_detail=None,
                processing_time_ms=processing_time_ms,
                total_medications=len(case.medications),
                total_alerts=len(alert_objs),
                finished_at=datetime.now(timezone.utc),
                criteria_report=criteria_report,
            )
            return execution

        except Exception:
            logger.exception("Fallo técnico durante la evaluación del caso %s", case_id)
            # Ejecutar rollback de la transacción de la BD
            db.rollback()

            # Registrar error funcional técnico controlado
            error_msg = "Error interno durante el procesamiento de la evaluación."
            try:
                EvaluationRepository.update_execution_result(
                    db,
                    execution_id=execution.id,
                    successful=False,
                    functional_error=True,
                    error_detail=error_msg,
                    processing_time_ms=(time.perf_counter() - start_time) * 1000.0,
                    total_medications=len(case.medications),
                    total_alerts=0,
                    finished_at=datetime.now(timezone.utc)
                )
            except Exception:
                pass

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_msg
            )
