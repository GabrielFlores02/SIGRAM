import pytest
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from backend.app.models.models import ClinicalCase, EvaluationExecution, Alert
from backend.app.repositories.evaluation_repository import EvaluationRepository

# Helper to create a basic case
def _create_test_case(db_session, case_code="TEST-EVAL-001"):
    case_obj = ClinicalCase(
        case_code=case_code,
        age=70,
        sex="M",
        diagnoses="Diagnóstico de prueba",
        is_simulated=True,
        status="active"
    )
    db_session.add(case_obj)
    db_session.commit()
    db_session.refresh(case_obj)
    return case_obj


def test_create_execution_associated_with_case(db_session):
    """1. Crear una ejecución asociada a un caso."""
    case = _create_test_case(db_session)
    
    execution = EvaluationExecution(
        case_id=case.id,
        started_at=datetime.now(timezone.utc),
        successful=True,
        total_medications=3,
        total_alerts=1
    )
    created = EvaluationRepository.create_execution(db_session, execution)
    assert created.id is not None
    assert created.case_id == case.id
    assert created.successful is True
    assert created.total_medications == 3
    assert created.total_alerts == 1


def test_reject_nonexistent_case_id(db_session):
    """2. Rechazar case_id inexistente (clave foránea)."""
    execution = EvaluationExecution(
        case_id=999999,  # Inexistente
        started_at=datetime.now(timezone.utc)
    )
    with pytest.raises(IntegrityError):
        EvaluationRepository.create_execution(db_session, execution)


def test_register_alert(db_session):
    """3. Registrar una alerta."""
    case = _create_test_case(db_session)
    execution = EvaluationExecution(
        case_id=case.id,
        started_at=datetime.now(timezone.utc)
    )
    EvaluationRepository.create_execution(db_session, execution)

    alert = Alert(
        execution_id=execution.id,
        rule_code="BEERS-001",
        alert_type="interaccion",
        problem_identified="Uso de AINEs con duplicidad",
        implicated_medications=["Ibuprofeno", "Naproxeno"],
        severity="moderada",
        recommendation="Evitar duplicidad terapéutica",
        justification="Aumenta riesgo de hemorragia gastrointestinal",
        source="Criterios Beers 2023",
        rule_version="1.0",
        is_demo=True,
        trace_data={"medications_count": 2}
    )
    created_alert = EvaluationRepository.add_alert(db_session, alert)
    assert created_alert.id is not None
    assert created_alert.execution_id == execution.id
    assert created_alert.rule_code == "BEERS-001"
    assert created_alert.severity == "moderada"
    assert created_alert.implicated_medications == ["Ibuprofeno", "Naproxeno"]


def test_get_execution_with_alerts(db_session):
    """4. Consultar ejecución con alertas."""
    case = _create_test_case(db_session)
    execution = EvaluationExecution(
        case_id=case.id,
        started_at=datetime.now(timezone.utc)
    )
    EvaluationRepository.create_execution(db_session, execution)

    alert1 = Alert(
        execution_id=execution.id,
        rule_code="R1", alert_type="T1", problem_identified="P1",
        implicated_medications=[], severity="advertencia", recommendation="R1",
        justification="J1", source="S1", rule_version="1", is_demo=True, trace_data={}
    )
    alert2 = Alert(
        execution_id=execution.id,
        rule_code="R2", alert_type="T2", problem_identified="P2",
        implicated_medications=[], severity="alta", recommendation="R2",
        justification="J2", source="S2", rule_version="1", is_demo=True, trace_data={}
    )
    EvaluationRepository.add_alert(db_session, alert1)
    EvaluationRepository.add_alert(db_session, alert2)

    # Recuperar ejecución
    retrieved = EvaluationRepository.get_execution_by_id(db_session, execution.id)
    assert retrieved is not None
    assert len(retrieved.alerts) == 2
    # El listado ordenado o simple de alertas
    alerts = EvaluationRepository.list_alerts_for_execution(db_session, execution.id)
    assert len(alerts) == 2


def test_get_latest_execution_for_case(db_session):
    """5. Obtener la ejecución más reciente."""
    case = _create_test_case(db_session)
    
    # Crear primera ejecución
    exec1 = EvaluationExecution(
        case_id=case.id,
        started_at=datetime(2026, 7, 13, 10, 0, 0, tzinfo=timezone.utc),
        successful=False
    )
    EvaluationRepository.create_execution(db_session, exec1)

    # Crear segunda ejecución (más reciente)
    exec2 = EvaluationExecution(
        case_id=case.id,
        started_at=datetime(2026, 7, 13, 11, 0, 0, tzinfo=timezone.utc),
        successful=True
    )
    EvaluationRepository.create_execution(db_session, exec2)

    latest = EvaluationRepository.get_latest_execution_for_case(db_session, case.id)
    assert latest is not None
    assert latest.id == exec2.id
    assert latest.successful is True


def test_validate_totals_non_negative(db_session):
    """6. Validar totales no negativos."""
    case = _create_test_case(db_session)
    
    # total_medications negativo
    execution1 = EvaluationExecution(
        case_id=case.id,
        started_at=datetime.now(timezone.utc),
        total_medications=-1
    )
    with pytest.raises(IntegrityError):
        EvaluationRepository.create_execution(db_session, execution1)

    db_session.rollback()

    # total_alerts negativo
    execution2 = EvaluationExecution(
        case_id=case.id,
        started_at=datetime.now(timezone.utc),
        total_alerts=-1
    )
    with pytest.raises(IntegrityError):
        EvaluationRepository.create_execution(db_session, execution2)


def test_validate_processing_time_non_negative(db_session):
    """7. Validar processing_time_ms no negativo."""
    case = _create_test_case(db_session)
    
    execution = EvaluationExecution(
        case_id=case.id,
        started_at=datetime.now(timezone.utc),
        processing_time_ms=-0.5
    )
    with pytest.raises(IntegrityError):
        EvaluationRepository.create_execution(db_session, execution)


def test_reject_invalid_severity(db_session):
    """8. Con PRAGMA foreign_keys y CheckConstraint activos, rechazar severidad inválida."""
    case = _create_test_case(db_session)
    execution = EvaluationExecution(
        case_id=case.id,
        started_at=datetime.now(timezone.utc)
    )
    EvaluationRepository.create_execution(db_session, execution)

    # Severidad inválida "critica"
    alert = Alert(
        execution_id=execution.id,
        rule_code="BEERS-001",
        alert_type="interaccion",
        problem_identified="P1",
        implicated_medications=[],
        severity="critica",  # Debe fallar CheckConstraint
        recommendation="R1",
        justification="J1",
        source="S1",
        rule_version="1.0",
        is_demo=True,
        trace_data={}
    )
    with pytest.raises(IntegrityError):
        EvaluationRepository.add_alert(db_session, alert)


def test_cascade_delete_case_execution_alerts(db_session):
    """9. Verificar cascada caso → ejecución → alertas."""
    case = _create_test_case(db_session)
    
    execution = EvaluationExecution(
        case_id=case.id,
        started_at=datetime.now(timezone.utc)
    )
    EvaluationRepository.create_execution(db_session, execution)

    alert = Alert(
        execution_id=execution.id,
        rule_code="R1", alert_type="T1", problem_identified="P1",
        implicated_medications=[], severity="alta", recommendation="R1",
        justification="J1", source="S1", rule_version="1", is_demo=True, trace_data={}
    )
    EvaluationRepository.add_alert(db_session, alert)

    # Verificar existencia inicial
    assert db_session.query(EvaluationExecution).filter_by(id=execution.id).first() is not None
    assert db_session.query(Alert).filter_by(id=alert.id).first() is not None

    # Eliminar el caso clínico
    db_session.delete(case)
    db_session.commit()

    # Comprobar que ejecución y alerta desaparecieron por cascada
    assert db_session.query(EvaluationExecution).filter_by(id=execution.id).first() is None
    assert db_session.query(Alert).filter_by(id=alert.id).first() is None


def test_update_execution_result(db_session):
    """Prueba el método update_execution_result de EvaluationRepository."""
    case = _create_test_case(db_session)
    execution = EvaluationExecution(
        case_id=case.id,
        started_at=datetime.now(timezone.utc),
        successful=False
    )
    EvaluationRepository.create_execution(db_session, execution)

    finished = datetime.now(timezone.utc)
    updated = EvaluationRepository.update_execution_result(
        db_session,
        execution_id=execution.id,
        successful=True,
        functional_error=False,
        error_detail=None,
        processing_time_ms=120.5,
        total_medications=5,
        total_alerts=2,
        finished_at=finished
    )
    assert updated is not None
    assert updated.successful is True
    assert updated.processing_time_ms == 120.5
    assert updated.total_medications == 5
    assert updated.total_alerts == 2
    # Convertir a timestamp para comparar ignorando precisión microscópica del tz
    retrieved_finished = updated.finished_at
    if retrieved_finished.tzinfo is None:
        retrieved_finished = retrieved_finished.replace(tzinfo=timezone.utc)
    assert retrieved_finished.timestamp() == pytest.approx(finished.timestamp())
