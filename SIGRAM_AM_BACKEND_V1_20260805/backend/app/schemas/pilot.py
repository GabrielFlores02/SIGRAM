from datetime import date

from pydantic import BaseModel, Field

from backend.app.schemas.cases import ClinicalCaseRead, ClinicalContext
from backend.app.schemas.evaluations import EvaluationExecutionRead


class PilotSamplePatient(BaseModel):
    patient_code: str
    age: int
    sex: str
    distinct_top_medications_2025: int
    max_simultaneous_top_medications: int
    index_date: str | None
    medication_rows_2025: int
    raw_lab_rows_2025: int
    raw_diagnosis_rows_2025: int
    distinct_diagnosis_codes_2025: int


class PilotSampleEvaluationRequest(BaseModel):
    index_date: date | None = None
    clinical_context: ClinicalContext = Field(default_factory=ClinicalContext)


class PilotLabEvidence(BaseModel):
    field: str
    value: bool | float
    applied: bool
    reason: str
    result_date: str
    age_days_at_index: int
    medication_index_date: str | None = None
    temporal_relation_to_medication_index: str
    used_under_pilot_full_year_rule: bool
    exam_code: int
    source_analyte: str
    source_unit: str
    source_value_raw: str
    standardized_unit: str
    source_file: str
    source_row_sha256: str
    mapping_version: str
    derived_method: str
    reference_range_raw: str | None = None
    validation_status: int | None = None
    validation_status_semantics: str
    quality_flags: list[str] = Field(default_factory=list)


class PilotDiagnosisEvidence(BaseModel):
    field: str
    value: bool
    label: str
    satisfies_context_field: bool
    related_fields: list[str] = Field(default_factory=list)
    applied: bool
    reason: str
    matched_codes: list[dict]
    first_attention_date: str
    last_attention_date: str
    medication_index_date: str | None = None
    temporal_relation_to_medication_index: str
    used_under_pilot_full_year_rule: bool
    source_rows_count: int
    source_file: str
    mapping_version: str
    classification: str
    evidence_semantics: str
    quality_flags: list[str] = Field(default_factory=list)


class PilotDataAvailability(BaseModel):
    medications_loaded: int
    diagnoses_loaded: int
    medication_index_date: str
    clinical_observation_start_date: str
    clinical_observation_end_date: str
    clinical_observation_mode: str
    medication_catalog_classification: list[dict] = Field(default_factory=list)
    raw_lab_rows_2025: int
    labs_mapped_to_clinical_context: bool
    mapped_lab_fields: list[PilotLabEvidence] = Field(default_factory=list)
    relevant_lab_rows_rejected: int = 0
    future_relevant_lab_rows_excluded: int = 0
    lab_lookback_days: int
    lab_mapping_warnings: list[str] = Field(default_factory=list)
    diagnosis_source: str
    diagnosis_rows_considered: int
    distinct_diagnosis_codes: int
    future_diagnosis_rows_excluded: int
    mapped_diagnosis_fields: list[PilotDiagnosisEvidence] = Field(default_factory=list)
    diagnosis_mapping_warnings: list[str] = Field(default_factory=list)
    unresolved_clinical_fields: list[str]
    note: str


class PilotSampleEvaluationResponse(BaseModel):
    patient: PilotSamplePatient
    case: ClinicalCaseRead
    evaluation: EvaluationExecutionRead
    data_availability: PilotDataAvailability
