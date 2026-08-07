from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import List, Optional
from datetime import datetime
from backend.app.services.medication_normalizer import normalize_active_ingredient

class MedicationCreate(BaseModel):
    entered_name: str
    normalized_active_ingredient: str
    dose: str
    dose_unit: str
    frequency: str
    duration: Optional[str] = None
    route: str

    @field_validator("normalized_active_ingredient")
    @classmethod
    def validate_and_normalize_ingredient(cls, v: str) -> str:
        """Delega la validación y normalización al normalizador canónico."""
        return normalize_active_ingredient(v)


class MedicationRead(BaseModel):
    id: int
    case_id: int
    entered_name: str
    normalized_active_ingredient: str
    dose: str
    dose_unit: str
    frequency: str
    duration: Optional[str] = None
    route: str
    created_at: datetime

    model_config = {
        "from_attributes": True
    }


class MedicationClinicalFacts(BaseModel):
    active_ingredient: str
    duration_days: Optional[int] = Field(default=None, ge=0)
    daily_dose_mg: Optional[float] = Field(default=None, ge=0)
    indication: Optional[str] = None
    regular_use: Optional[bool] = None


class ClinicalContext(BaseModel):
    """Datos estructurados opcionales requeridos por criterios clínicos."""

    egfr_ml_min_1_73m2: Optional[float] = None
    potassium_mmol_l: Optional[float] = None
    sodium_mmol_l: Optional[float] = None
    corrected_calcium_mmol_l: Optional[float] = None
    tsh_miu_l: Optional[float] = None
    free_t4_normal: Optional[bool] = None
    proteinuria_mg_24h: Optional[float] = None
    systolic_bp_mm_hg: Optional[float] = None
    diastolic_bp_mm_hg: Optional[float] = None
    heart_rate_bpm: Optional[float] = None
    qtc_ms: Optional[float] = None
    bmi: Optional[float] = None
    falls_history: Optional[bool] = None
    frailty_status: Optional[str] = None
    cognitive_impairment: Optional[bool] = None
    delirium: Optional[bool] = None
    orthostatic_hypotension: Optional[bool] = None
    syncope_history: Optional[bool] = None
    adherence_known: Optional[bool] = None
    indication_confirmed: Optional[bool] = None
    gastroprotection: Optional[bool] = None
    heart_failure_status: Optional[str] = None
    peptic_ulcer_history: Optional[bool] = None
    primary_prevention: Optional[bool] = None
    av_block: Optional[bool] = None
    gout_history: Optional[bool] = None
    potassium_monitoring: Optional[bool] = None
    life_expectancy_lt_3_years: Optional[bool] = None
    cardiovascular_history: Optional[bool] = None
    bleeding_risk: Optional[bool] = None
    atrial_fibrillation: Optional[bool] = None
    coronary_stent_or_stenosis: Optional[bool] = None
    stable_vascular_disease: Optional[bool] = None
    constipation: Optional[bool] = None
    copd: Optional[bool] = None
    respiratory_failure: Optional[bool] = None
    osteoarthritis: Optional[bool] = None
    prior_paracetamol_trial: Optional[bool] = None
    upper_gi_disease: Optional[bool] = None
    pain_severity: Optional[str] = None
    first_line_treatment: Optional[bool] = None
    neuropathic_pain: Optional[bool] = None
    chronic_liver_disease: Optional[bool] = None
    reduced_ejection_fraction: Optional[bool] = None
    severe_gerd_or_stricture: Optional[bool] = None
    osteoporosis_or_fragility_fracture: Optional[bool] = None
    bph_urinary_symptoms: Optional[bool] = None
    opioid_regular_use: Optional[bool] = None
    opioid_transition_or_dose_reduction: Optional[bool] = None
    acute_severe_pain: Optional[bool] = None
    ppi_maintenance_indication: Optional[bool] = None
    safer_alternatives_ineffective: Optional[bool] = None
    lithium_level_monitoring: Optional[bool] = None
    medication_facts: List[MedicationClinicalFacts] = Field(default_factory=list)
    lab_provenance: List[dict] = Field(default_factory=list)
    diagnosis_codes: List[str] = Field(default_factory=list)
    diagnosis_code_counts: dict[str, int] = Field(default_factory=dict)
    diagnosis_provenance: List[dict] = Field(default_factory=list)

    # Diagnosticos CIE-10 que aportan contexto, pero no bastan para completar
    # por si solos criterios que exigen gravedad, sintomas o mediciones.
    heart_failure_diagnosis: Optional[bool] = None
    copd_diagnosis: Optional[bool] = None
    bph_diagnosis: Optional[bool] = None
    chronic_kidney_disease_diagnosis: Optional[bool] = None
    hypertension_diagnosis: Optional[bool] = None
    diabetes_diagnosis: Optional[bool] = None

    model_config = ConfigDict(extra="allow")


class ClinicalCaseCreate(BaseModel):
    case_code: str
    age: int = Field(..., ge=60, description="La edad debe ser mayor o igual a 60 años.")
    sex: str
    diagnoses: str
    clinical_context: ClinicalContext = Field(default_factory=ClinicalContext)
    is_simulated: bool = Field(True, description="Debe ser siempre True.")
    medications: List[MedicationCreate]

    @field_validator("case_code")
    @classmethod
    def validate_case_code(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("El código del caso (case_code) es obligatorio.")
        return v.strip()

    @field_validator("medications")
    @classmethod
    def validate_non_empty_medications(cls, v: List[MedicationCreate]) -> List[MedicationCreate]:
        if not v or len(v) == 0:
            raise ValueError("Un caso clínico debe contener al menos un medicamento.")
        return v

    @field_validator("is_simulated")
    @classmethod
    def validate_is_simulated(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("El caso debe ser simulado (is_simulated debe ser True).")
        return True


class ClinicalCaseRead(BaseModel):
    id: int
    case_code: str
    age: int
    sex: str
    diagnoses: str
    clinical_context: ClinicalContext
    is_simulated: bool
    status: str
    created_at: datetime
    updated_at: datetime
    medications: List[MedicationRead]

    model_config = {
        "from_attributes": True
    }


class ClinicalCaseList(BaseModel):
    id: int
    case_code: str
    age: int
    sex: str
    diagnoses: str
    is_simulated: bool
    status: str
    created_at: datetime

    model_config = {
        "from_attributes": True
    }


class ErrorResponse(BaseModel):
    detail: str
