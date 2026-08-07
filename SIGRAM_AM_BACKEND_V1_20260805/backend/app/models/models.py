from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, CheckConstraint, Float, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from backend.app.database import Base

def get_utc_now():
    return datetime.now(timezone.utc)

class ClinicalCase(Base):
    __tablename__ = "clinical_cases"

    id = Column(Integer, primary_key=True, index=True)
    case_code = Column(String, unique=True, index=True, nullable=False)
    age = Column(Integer, nullable=False)
    sex = Column(String, nullable=False)
    diagnoses = Column(String, nullable=False)  # Texto conteniendo diagnósticos o códigos CIE-10
    clinical_context = Column(JSON, nullable=False, default=dict)
    is_simulated = Column(Boolean, nullable=False, default=True)
    status = Column(String, nullable=False, default="active")
    created_at = Column(DateTime, nullable=False, default=get_utc_now)
    updated_at = Column(DateTime, nullable=False, default=get_utc_now, onupdate=get_utc_now)

    # Relación de uno a muchos con Medication, con eliminación en cascada
    medications = relationship(
        "Medication",
        back_populates="case",
        cascade="all, delete-orphan"
    )

    # Relación de uno a muchos con EvaluationExecution, con eliminación en cascada
    executions = relationship(
        "EvaluationExecution",
        back_populates="case",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("age >= 60", name="check_age_minimum_60"),
        CheckConstraint("is_simulated = 1", name="check_is_simulated_only"),
    )


class Medication(Base):
    __tablename__ = "medications"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("clinical_cases.id", ondelete="CASCADE"), nullable=False)
    entered_name = Column(String, nullable=False)
    normalized_active_ingredient = Column(String, nullable=False)
    dose = Column(String, nullable=False)
    dose_unit = Column(String, nullable=False)
    frequency = Column(String, nullable=False)
    duration = Column(String, nullable=True)  # Duración puede ser opcional
    route = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=get_utc_now)

    # Relación muchos a uno con ClinicalCase
    case = relationship("ClinicalCase", back_populates="medications")


class EvaluationExecution(Base):
    __tablename__ = "evaluation_executions"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("clinical_cases.id", ondelete="CASCADE"), nullable=False)
    started_at = Column(DateTime, nullable=False, default=get_utc_now)
    finished_at = Column(DateTime, nullable=True)
    processing_time_ms = Column(Float, nullable=True)
    successful = Column(Boolean, nullable=False, default=False)
    functional_error = Column(Boolean, nullable=False, default=False)
    error_detail = Column(String, nullable=True)
    total_medications = Column(Integer, nullable=False, default=0)
    total_alerts = Column(Integer, nullable=False, default=0)
    criteria_report = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, nullable=False, default=get_utc_now)

    # Relaciones
    case = relationship("ClinicalCase", back_populates="executions")
    alerts = relationship("Alert", back_populates="execution", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("total_medications >= 0", name="check_total_medications_non_negative"),
        CheckConstraint("total_alerts >= 0", name="check_total_alerts_non_negative"),
        CheckConstraint("processing_time_ms IS NULL OR processing_time_ms >= 0", name="check_processing_time_non_negative"),
    )


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(Integer, ForeignKey("evaluation_executions.id", ondelete="CASCADE"), nullable=False)
    rule_code = Column(String, nullable=False)
    alert_type = Column(String, nullable=False)
    problem_identified = Column(String, nullable=False)
    implicated_medications = Column(JSON, nullable=False)
    severity = Column(String, nullable=False)
    recommendation = Column(String, nullable=False)
    justification = Column(String, nullable=False)
    source = Column(String, nullable=False)
    rule_version = Column(String, nullable=False)
    is_demo = Column(Boolean, nullable=False)
    trace_data = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False, default=get_utc_now)

    # Relaciones
    execution = relationship("EvaluationExecution", back_populates="alerts")

    __table_args__ = (
        CheckConstraint("severity IN ('alta', 'moderada', 'advertencia')", name="check_alert_severity_valid"),
    )
