from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, computed_field


class AlertRead(BaseModel):
    id: int
    execution_id: int
    rule_code: str
    alert_type: str
    problem_identified: str
    implicated_medications: list
    severity: str
    recommendation: str
    justification: str
    source: str
    rule_version: str
    is_demo: bool
    trace_data: dict
    created_at: datetime

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def analysis_system(self) -> str:
        return self.trace_data.get("analysis_system", "technical_demo")


class AnalysisMethodResult(BaseModel):
    system: str
    label: str
    status: str
    alert_count: int
    evaluated_count: int = 0
    not_evaluable_count: int = 0
    manual_review_count: int = 0
    catalog: str
    note: str


class CriterionEvaluationResult(BaseModel):
    criterion_code: str
    system: str
    criterion_type: str
    status: str
    statement: str
    source_location: str
    implicated_medications: List[str]
    medication_classification: List[dict] = Field(default_factory=list)
    missing_data: List[dict]
    reason: str
    catalog_version: str
    age_scope: str
    context_used: dict = Field(default_factory=dict)
    lab_evidence: List[dict] = Field(default_factory=list)
    diagnosis_evidence: List[dict] = Field(default_factory=list)
    triggering_evidence: List[dict] = Field(default_factory=list)
    protective_evidence: List[dict] = Field(default_factory=list)
    exception_status: str = "not_applicable"
    exception_reason: Optional[str] = None
    recommended_actions: List[str] = Field(default_factory=list)
    logic_summary: str = ""
    medication_coverage_note: str = "top_v1_only"


class EvaluationExecutionRead(BaseModel):
    id: int
    case_id: int
    started_at: datetime
    finished_at: Optional[datetime] = None
    processing_time_ms: Optional[float] = None
    successful: bool
    functional_error: bool
    error_detail: Optional[str] = None
    total_medications: int
    total_alerts: int
    created_at: datetime
    alerts: List[AlertRead] = Field(default_factory=list)
    criteria_report: List[CriterionEvaluationResult] = Field(default_factory=list)

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def clinical_findings(self) -> List[CriterionEvaluationResult]:
        """Hallazgos confirmados que el frontend muestra por defecto."""
        return [item for item in self.criteria_report if item.status == "alert"]

    @computed_field
    @property
    def data_gaps(self) -> List[CriterionEvaluationResult]:
        """Criterios que requieren informacion adicional."""
        return [
            item
            for item in self.criteria_report
            if item.status == "not_evaluable"
        ]

    @computed_field
    @property
    def manual_review_findings(self) -> List[CriterionEvaluationResult]:
        """Coincidencias que aun requieren interpretacion profesional."""
        return [
            item
            for item in self.criteria_report
            if item.status == "manual_review"
        ]

    @computed_field
    @property
    def analysis_results(self) -> List[AnalysisMethodResult]:
        counts = {"beers": 0, "stopp_start": 0, "ddinter": 0}
        for alert in self.alerts:
            if alert.analysis_system in counts:
                counts[alert.analysis_system] += 1
        status_counts = {
            system: {
                "evaluated": 0,
                "not_evaluable": 0,
                "manual_review": 0,
            }
            for system in ("beers", "stopp_start")
        }
        for criterion in self.criteria_report:
            if criterion.system not in status_counts:
                continue
            if criterion.status in {"alert", "no_alert"}:
                status_counts[criterion.system]["evaluated"] += 1
            elif criterion.status == "not_evaluable":
                status_counts[criterion.system]["not_evaluable"] += 1
            elif criterion.status == "manual_review":
                status_counts[criterion.system]["manual_review"] += 1
        return [
            AnalysisMethodResult(
                system="beers",
                label="Beers",
                status="active_v1_screening_catalog",
                alert_count=counts["beers"],
                evaluated_count=status_counts["beers"]["evaluated"],
                not_evaluable_count=status_counts["beers"]["not_evaluable"],
                manual_review_count=status_counts["beers"]["manual_review"],
                catalog="top de medicamentos validado por el equipo médico, 2026-07-30",
                note=(
                    "La cohorte es 60+; el uso fuera de 65+ debe declararse "
                    "como adaptación del protocolo. clinical_findings contiene "
                    "los hallazgos resueltos para la vista principal."
                ),
            ),
            AnalysisMethodResult(
                system="stopp_start",
                label="STOPP/START",
                status="active_v1_screening_catalog",
                alert_count=counts["stopp_start"],
                evaluated_count=status_counts["stopp_start"]["evaluated"],
                not_evaluable_count=status_counts["stopp_start"]["not_evaluable"],
                manual_review_count=status_counts["stopp_start"]["manual_review"],
                catalog="top de medicamentos STOPP/START v3, 2026-07-30",
                note=(
                    "STOPP y START se conservan como subtipos. criteria_report "
                    "mantiene el analisis completo; las brechas no se convierten "
                    "en resultados negativos."
                ),
            ),
            AnalysisMethodResult(
                system="ddinter",
                label="DDInter",
                status="active_local_legacy_catalog",
                alert_count=counts["ddinter"],
                catalog="ocho CSV locales A, B, D, H, L, P, R y V",
                note=(
                    "Coincidencia exacta/alias provisional; los niveles Unknown "
                    "se excluyen por defecto."
                ),
            ),
        ]


class EvaluationExecutionSummary(BaseModel):
    id: int
    case_id: int
    started_at: datetime
    finished_at: Optional[datetime] = None
    processing_time_ms: Optional[float] = None
    successful: bool
    functional_error: bool
    total_medications: int
    total_alerts: int
    created_at: datetime

    model_config = {"from_attributes": True}
