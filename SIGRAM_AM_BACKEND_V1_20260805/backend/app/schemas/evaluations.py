from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, computed_field

from backend.app.config import settings


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
    out_of_scope_count: int = 0
    not_evaluable_count: int = 0
    manual_review_count: int = 0
    not_applicable_count: int = 0
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
    source_name: Optional[str] = None
    source_year: Optional[int] = None
    source_version: Optional[str] = None
    source_table: Optional[str] = None
    source_section: Optional[str] = None
    beers_category: Optional[str] = None
    operational_formulation: Optional[str] = None
    evaluated_situation: Optional[str] = None
    rationale: Optional[str] = None
    recommendation_type: Optional[str] = None
    recommendation_text: Optional[str] = None
    quality_of_evidence: Optional[str] = None
    strength_of_recommendation: Optional[str] = None
    evidence_profiles: List[dict] = Field(default_factory=list)
    exceptions: List[dict] = Field(default_factory=list)
    automation_mode: Optional[str] = None
    counts_as_clinical_finding: Optional[bool] = None
    trigger_facts: dict = Field(default_factory=dict)
    # Correspondencia clínica revisada por el equipo médico.  Debe formar
    # parte del esquema público; de otro modo Pydantic descarta este campo
    # aunque el motor lo calcule, y la interfaz vuelve a mostrar códigos
    # internos como STOPP-A3 en lugar del código fuente (p. ej. STOPP-003).
    review_details: List[dict] = Field(default_factory=list)


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
        return [item for item in self.criteria_report if item.status in {"alert", "activated"}]

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
        enabled = {
            item.strip().lower()
            for item in settings.ENABLED_CLINICAL_SYSTEMS.split(",")
            if item.strip()
        }
        counts = {"beers": 0, "stopp_start": 0, "ddinter": 0}
        for alert in self.alerts:
            if alert.analysis_system in counts:
                counts[alert.analysis_system] += 1
        status_counts = {
            system: {
                "evaluated": 0,
                "out_of_scope": 0,
                "not_evaluable": 0,
                "manual_review": 0,
                "not_applicable": 0,
            }
            for system in ("beers", "stopp_start")
        }
        for criterion in self.criteria_report:
            if criterion.system not in status_counts:
                continue
            if criterion.status in {"alert", "activated", "no_alert", "supporting_classification"}:
                status_counts[criterion.system]["evaluated"] += 1
            elif criterion.status == "out_of_scope":
                status_counts[criterion.system]["out_of_scope"] += 1
            elif criterion.status == "not_evaluable":
                status_counts[criterion.system]["not_evaluable"] += 1
            elif criterion.status == "manual_review":
                status_counts[criterion.system]["manual_review"] += 1
            elif criterion.status == "not_applicable":
                status_counts[criterion.system]["not_applicable"] += 1
        results = [
            AnalysisMethodResult(
                system="beers",
                label="Beers",
                status="active_297_source_rules",
                alert_count=counts["beers"],
                evaluated_count=status_counts["beers"]["evaluated"],
                out_of_scope_count=status_counts["beers"]["out_of_scope"],
                not_evaluable_count=status_counts["beers"]["not_evaluable"],
                manual_review_count=status_counts["beers"]["manual_review"],
                not_applicable_count=status_counts["beers"]["not_applicable"],
                catalog="107 filas Beers del Excel médico actualizado al 2026-09-25",
                note=(
                    "Cada fila Beers tiene una regla fuente directa. El alcance es 65+; "
                    "los casos fuera de alcance y los datos faltantes se reportan "
                    "explícitamente, sin convertirlos en resultados negativos."
                ),
            ),
            AnalysisMethodResult(
                system="stopp_start",
                label="STOPP/START",
                status="active_297_source_rules",
                alert_count=counts["stopp_start"],
                evaluated_count=status_counts["stopp_start"]["evaluated"],
                not_evaluable_count=status_counts["stopp_start"]["not_evaluable"],
                manual_review_count=status_counts["stopp_start"]["manual_review"],
                catalog="133 filas STOPP y 57 START del Excel médico actualizado al 2026-09-25",
                note=(
                    "STOPP y START conservan los identificadores de la fuente. "
                    "criteria_report contiene las 190 filas y deja como no evaluable "
                    "todo criterio que todavía necesite un dato clínico explícito."
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
        return [item for item in results if item.system in enabled]


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
