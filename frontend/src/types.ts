export type AnalysisSystem = "beers" | "stopp_start" | "ddinter";
export type CriterionStatus = "alert" | "no_alert" | "not_evaluable" | "manual_review";

export interface MedicationInput {
  entered_name: string;
  normalized_active_ingredient: string;
  dose: string;
  dose_unit: string;
  frequency: string;
  duration?: string;
  route: string;
}

export interface Medication extends MedicationInput {
  id: number;
  case_id: number;
  created_at: string;
}

export interface ClinicalCaseInput {
  case_code: string;
  age: number;
  sex: string;
  diagnoses: string;
  clinical_context: Record<string, unknown>;
  is_simulated: true;
  medications: MedicationInput[];
}

export interface ClinicalCaseSummary {
  id: number;
  case_code: string;
  age: number;
  sex: string;
  diagnoses: string;
  is_simulated: boolean;
  status: string;
  created_at: string;
}

export interface ClinicalCase extends ClinicalCaseSummary {
  clinical_context: Record<string, unknown>;
  updated_at: string;
  medications: Medication[];
}

export interface MissingDatum {
  field?: string;
  label?: string;
  [key: string]: unknown;
}

export interface CriterionResult {
  criterion_code: string;
  system: AnalysisSystem;
  criterion_type: string;
  status: CriterionStatus;
  statement: string;
  source_location: string;
  implicated_medications: string[];
  medication_classification: MedicationClassification[];
  missing_data: MissingDatum[];
  reason: string;
  catalog_version: string;
  age_scope: string;
  context_used: Record<string, unknown>;
  lab_evidence: LabEvidence[];
  diagnosis_evidence: EvidenceTrace[];
  triggering_evidence: EvidenceTrace[];
  protective_evidence: EvidenceTrace[];
  exception_status: string;
  exception_reason?: string | null;
  recommended_actions: string[];
  logic_summary: string;
  medication_coverage_note: string;
}

export interface EvidenceTrace {
  type?: string;
  role?: string;
  field?: string;
  label?: string;
  value?: unknown;
  matched_codes?: Array<{ code?: string }>;
}

export interface LabEvidence {
  field: string;
  value: boolean | number;
  applied: boolean;
  reason: string;
  result_date: string;
  age_days_at_index: number;
  medication_index_date?: string | null;
  temporal_relation_to_medication_index?: string;
  used_under_pilot_full_year_rule?: boolean;
  exam_code: number;
  source_analyte: string;
  source_unit: string;
  source_value_raw: string;
  standardized_unit: string;
  source_file: string;
  source_row_sha256: string;
  mapping_version: string;
  derived_method: string;
  reference_range_raw?: string | null;
  validation_status?: number | null;
  validation_status_semantics: string;
  quality_flags: string[];
}

export interface MedicationClassification {
  essi_presentation: string;
  evaluation_name: string;
  matched_top_v1: boolean;
  catalog_medication?: string | null;
  pharmacologic_group?: string | null;
  beers_codes: string[];
  stopp_codes: string[];
  start_codes: string[];
}

export interface AlertResult {
  id: number;
  execution_id: number;
  rule_code: string;
  alert_type: string;
  problem_identified: string;
  implicated_medications: string[];
  severity: string;
  recommendation: string;
  justification: string;
  source: string;
  rule_version: string;
  is_demo: boolean;
  trace_data: Record<string, unknown>;
  analysis_system: AnalysisSystem;
  created_at: string;
}

export interface AnalysisMethodResult {
  system: AnalysisSystem;
  label: string;
  status: string;
  alert_count: number;
  evaluated_count: number;
  not_evaluable_count: number;
  manual_review_count: number;
  catalog: string;
  note: string;
}

export interface EvaluationExecution {
  id: number;
  case_id: number;
  started_at: string;
  finished_at?: string;
  processing_time_ms?: number;
  successful: boolean;
  functional_error: boolean;
  error_detail?: string;
  total_medications: number;
  total_alerts: number;
  created_at: string;
  alerts: AlertResult[];
  criteria_report: CriterionResult[];
  clinical_findings: CriterionResult[];
  data_gaps: CriterionResult[];
  manual_review_findings: CriterionResult[];
  analysis_results: AnalysisMethodResult[];
}

export interface RequiredData {
  field: string;
  label: string;
}

export interface CatalogCriterion {
  code: string;
  system: "beers" | "stopp_start";
  criterion_type: string;
  statement: string;
  source_location: string;
  automation_status: string;
  required_data: RequiredData[];
}

export interface CatalogMedication {
  order: number;
  medication: string;
  pharmacologic_group: string;
  stopp_codes: string[];
  start_codes: string[];
  beers_codes: string[];
  atc_code: string | null;
  pharmacologic_group_level4: string | null;
  mapping_status: "pending_clinical_validation";
  catalog_version: string;
}

export interface CatalogSummary {
  catalog_version: string;
  source_file: string;
  source_sha256: string;
  medication_count: number;
  criterion_count: number;
  criteria_by_system: Record<"beers" | "stopp_start", number>;
  automated_criterion_count: number;
  manual_or_context_dependent_count: number;
  population: string;
  status: string;
  atc_mapping_status: "pending_clinical_validation";
  atc_code_coverage: number;
  pharmacologic_group_level4_coverage: number;
}

export interface PilotPatient {
  patient_code: string;
  age: number;
  sex: string;
  distinct_top_medications_2025: number;
  max_simultaneous_top_medications: number;
  index_date?: string;
  medication_rows_2025: number;
  raw_lab_rows_2025: number;
  raw_diagnosis_rows_2025: number;
  distinct_diagnosis_codes_2025: number;
}

export interface PilotCasePrefill {
  patient_code: string;
  age: number;
  sex: string;
  diagnoses: string;
  clinical_context: Record<string, unknown>;
  medications: MedicationInput[];
  medication_index_date: string;
  clinical_observation_start_date: string;
  clinical_observation_end_date: string;
}

export interface DiagnosisEvidence {
  field: string;
  value: boolean;
  label: string;
  satisfies_context_field: boolean;
  related_fields: string[];
  applied: boolean;
  reason: string;
  matched_codes: Array<{ code: string; count: number; first_attention_date: string; last_attention_date: string }>;
  first_attention_date: string;
  last_attention_date: string;
  medication_index_date?: string | null;
  temporal_relation_to_medication_index?: string;
  used_under_pilot_full_year_rule?: boolean;
  source_rows_count: number;
  source_file: string;
  mapping_version: string;
  classification: string;
  evidence_semantics: string;
  quality_flags: string[];
}

export interface PilotEvaluationResponse {
  patient: PilotPatient;
  case: ClinicalCase;
  evaluation: EvaluationExecution;
  data_availability: {
    medications_loaded: number;
    diagnoses_loaded: number;
    medication_index_date: string;
    clinical_observation_start_date: string;
    clinical_observation_end_date: string;
    clinical_observation_mode: string;
    medication_catalog_classification: MedicationClassification[];
    raw_lab_rows_2025: number;
    labs_mapped_to_clinical_context: boolean;
    mapped_lab_fields: LabEvidence[];
    relevant_lab_rows_rejected: number;
    future_relevant_lab_rows_excluded: number;
    lab_lookback_days: number;
    lab_mapping_warnings: string[];
    diagnosis_source: string;
    diagnosis_rows_considered: number;
    distinct_diagnosis_codes: number;
    future_diagnosis_rows_excluded: number;
    mapped_diagnosis_fields: DiagnosisEvidence[];
    diagnosis_mapping_warnings: string[];
    unresolved_clinical_fields: string[];
    note: string;
  };
}

export interface PilotResearchData {
  patient: PilotPatient;
  medication_index_date: string;
  clinical_observation_start_date: string;
  clinical_observation_end_date: string;
  active_medications: Array<{
    medication: string;
    fecha_despacho?: string;
    duracion_dias?: number;
    diagnosis_code?: string;
  }>;
  raw_laboratory_rows: Array<{
    result_date_raw?: string;
    test_description?: string;
    exam_code?: number;
    analyte?: string;
    result_value_raw?: string;
    unit?: string;
    normal_value_raw?: string;
    other_normal_value_raw?: string;
    validation_status?: number;
  }>;
  raw_diagnosis_rows: Array<{
    attention_date?: string;
    diagnosis_code?: string;
    diagnosis_position?: number;
  }>;
  lab_mapping: Pick<PilotEvaluationResponse["data_availability"], "mapped_lab_fields" | "relevant_lab_rows_rejected" | "future_relevant_lab_rows_excluded" | "lab_lookback_days" | "lab_mapping_warnings">;
  diagnosis_mapping: Pick<PilotEvaluationResponse["data_availability"], "mapped_diagnosis_fields" | "diagnosis_rows_considered" | "distinct_diagnosis_codes" | "future_diagnosis_rows_excluded" | "diagnosis_mapping_warnings">;
  notice: string;
}
