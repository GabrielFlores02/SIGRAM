import csv
import re
import unicodedata
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

import polars as pl
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.schemas.cases import (
    ClinicalCaseCreate,
    ClinicalContext,
    MedicationClinicalFacts,
    MedicationCreate,
)
from backend.app.services.case_service import CaseService
from backend.app.services.clinical_catalog_service import ClinicalCatalogService
from backend.app.services.diagnosis_context_service import DiagnosisContextService
from backend.app.services.evaluation_service import EvaluationService
from backend.app.services.lab_context_service import LabContextService


UNRESOLVED_CLINICAL_FIELDS = {
    "caidas": "falls_history",
    "fragilidad": "frailty_status",
    "cognicion": "cognitive_impairment",
    "hipotension_ortostatica": "orthostatic_hypotension",
    "adherencia": "adherence_known",
    "indicacion": "indication_confirmed",
}

PILOT_OBSERVATION_START = date(settings.PILOT_OBSERVATION_YEAR, 1, 1)
PILOT_OBSERVATION_END = date(settings.PILOT_OBSERVATION_YEAR, 12, 31)
PILOT_OBSERVATION_DAYS = (
    PILOT_OBSERVATION_END - PILOT_OBSERVATION_START
).days


def _canonical(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    return re.sub(r"[^A-Z0-9]+", " ", ascii_text.upper()).strip()


class PilotSampleService:
    """Carga exclusivamente la muestra pseudonimizada preparada para la V1."""

    def __init__(self, sample_dir: str | Path | None = None):
        self.sample_dir = Path(sample_dir or settings.PILOT_SAMPLE_DIR)
        self.patients_path = self.sample_dir / "sample_patients.parquet"
        self.medications_path = self.sample_dir / "sample_medications.parquet"
        self.labs_path = self.sample_dir / "sample_labs_2025.parquet"
        self.diagnoses_path = self.sample_dir / "sample_diagnoses_2025.parquet"

    def _require_sources(self) -> None:
        missing = [
            str(path)
            for path in (
                self.patients_path,
                self.medications_path,
                self.labs_path,
                self.diagnoses_path,
            )
            if not path.is_file()
        ]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "message": "Falta la muestra pseudonimizada del piloto V1.",
                    "files": missing,
                },
            )

    def _frames(
        self,
    ) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame]:
        self._require_sources()
        return (
            pl.read_parquet(self.patients_path),
            pl.read_parquet(self.medications_path),
            pl.read_parquet(self.labs_path),
            pl.read_parquet(self.diagnoses_path),
        )

    def list_patients(self) -> list[dict]:
        patients, medications, labs, diagnoses = self._frames()
        medication_counts = medications.group_by("patient_code").agg(
            pl.col("medication").n_unique().alias("distinct_top_medications_2025"),
            pl.len().alias("medication_rows_2025"),
        )
        lab_counts = labs.group_by("patient_code").agg(
            pl.len().alias("raw_lab_rows_2025")
        )
        diagnosis_counts = diagnoses.group_by("patient_code").agg(
            pl.len().alias("raw_diagnosis_rows_2025"),
            pl.col("diagnosis_code")
            .drop_nulls()
            .n_unique()
            .alias("distinct_diagnosis_codes_2025"),
        )
        summaries = (
            patients.join(medication_counts, on="patient_code", how="left")
            .join(lab_counts, on="patient_code", how="left")
            .join(diagnosis_counts, on="patient_code", how="left")
            .with_columns(
                pl.col("distinct_top_medications_2025").fill_null(0),
                pl.col("medication_rows_2025").fill_null(0),
                pl.col("raw_lab_rows_2025").fill_null(0),
                pl.col("raw_diagnosis_rows_2025").fill_null(0),
                pl.col("distinct_diagnosis_codes_2025").fill_null(0),
            )
            .rename({"sexo": "sex"})
            .sort("patient_code")
            .to_dicts()
        )
        for summary in summaries:
            patient_medications = medications.filter(
                pl.col("patient_code") == summary["patient_code"]
            )
            index_date, active_rows = self._select_overlap_episode(patient_medications)
            summary["index_date"] = index_date.isoformat() if index_date else None
            summary["max_simultaneous_top_medications"] = (
                active_rows.get_column("medication").n_unique()
                if not active_rows.is_empty()
                else 0
            )
        return summaries

    def research_data(self, patient_code: str) -> dict:
        """Entrega insumos pseudonimizados para auditar el piloto, sin crear casos."""
        _, medication_rows, lab_rows, diagnosis_rows = self._patient_rows(patient_code)
        medication_index_date, active_rows = self._select_overlap_episode(medication_rows)
        if medication_index_date is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No se pudo construir un episodio temporal de medicamentos.",
            )
        lab_mapping = LabContextService.extract(
            lab_rows,
            index_date=PILOT_OBSERVATION_END,
            medication_index_date=medication_index_date,
            lookback_days=PILOT_OBSERVATION_DAYS,
        )
        diagnosis_mapping = DiagnosisContextService().extract(
            diagnosis_rows,
            index_date=PILOT_OBSERVATION_END,
            medication_index_date=medication_index_date,
            lookback_days=PILOT_OBSERVATION_DAYS,
        )
        medication_columns = [
            column
            for column in ("medication", "fecha_despacho", "duracion_dias", "diagnosis_code")
            if column in active_rows.columns
        ]
        lab_columns = [
            column
            for column in (
                "result_date_raw", "test_description", "exam_code", "analyte",
                "result_value_raw", "unit", "normal_value_raw",
                "other_normal_value_raw", "validation_status",
            )
            if column in lab_rows.columns
        ]
        diagnosis_columns = [
            column
            for column in ("attention_date", "diagnosis_code", "diagnosis_position")
            if column in diagnosis_rows.columns
        ]

        def serialize(rows: list[dict]) -> list[dict]:
            return [
                {
                    key: value.isoformat() if isinstance(value, date) else value
                    for key, value in row.items()
                }
                for row in rows
            ]

        return {
            "patient": next(item for item in self.list_patients() if item["patient_code"] == patient_code),
            "medication_index_date": medication_index_date.isoformat(),
            "clinical_observation_start_date": PILOT_OBSERVATION_START.isoformat(),
            "clinical_observation_end_date": PILOT_OBSERVATION_END.isoformat(),
            "active_medications": serialize(active_rows.select(medication_columns).to_dicts()),
            "raw_laboratory_rows": serialize(lab_rows.select(lab_columns).to_dicts()),
            "raw_diagnosis_rows": serialize(diagnosis_rows.select(diagnosis_columns).to_dicts()),
            "lab_mapping": {
                "mapped_lab_fields": lab_mapping["evidence"],
                "relevant_lab_rows_rejected": lab_mapping["relevant_lab_rows_rejected"],
                "future_relevant_lab_rows_excluded": lab_mapping["future_relevant_lab_rows_excluded"],
                "lab_lookback_days": lab_mapping["lookback_days"],
                "lab_mapping_warnings": lab_mapping["warnings"],
            },
            "diagnosis_mapping": {
                "mapped_diagnosis_fields": diagnosis_mapping["evidence"],
                "diagnosis_rows_considered": diagnosis_mapping["diagnosis_rows_considered"],
                "distinct_diagnosis_codes": diagnosis_mapping["distinct_diagnosis_codes"],
                "future_diagnosis_rows_excluded": diagnosis_mapping["future_diagnosis_rows_excluded"],
                "diagnosis_mapping_warnings": diagnosis_mapping["warnings"],
            },
            "notice": "Datos pseudonimizados para validación del piloto. No usar para decisiones clínicas.",
        }

    def case_prefill(self, patient_code: str) -> dict:
        """Prepara una historia pseudonimizada para editarla como un nuevo caso.

        Este flujo no guarda ningun caso: solo entrega la medicacion activa y los
        campos que pudieron ser derivados de los datos 2025 del paciente.
        """
        patient, medication_rows, lab_rows, diagnosis_rows = self._patient_rows(
            patient_code
        )
        index_date, active_medication_rows = self._select_overlap_episode(
            medication_rows
        )
        if index_date is None or active_medication_rows.is_empty():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No se pudo construir un episodio temporal de medicamentos.",
            )

        grouped = active_medication_rows.group_by(
            "medication", maintain_order=True
        ).agg(
            pl.col("duracion_dias").max().alias("duration_days"),
            pl.col("diagnosis_code").drop_nulls().unique().alias("diagnoses"),
        )
        medications: list[dict] = []
        medication_facts: list[MedicationClinicalFacts] = []
        medication_diagnoses: set[str] = set()
        for row in grouped.iter_rows(named=True):
            name = str(row["medication"])
            active_ingredient = self._active_ingredient(name)
            duration_value = row.get("duration_days")
            duration_days = int(duration_value) if duration_value is not None else None
            medication_diagnoses.update(
                str(item) for item in (row.get("diagnoses") or []) if item
            )
            medications.append(
                {
                    "entered_name": name,
                    "normalized_active_ingredient": active_ingredient,
                    "dose": "no estructurada",
                    "dose_unit": "no estructurada",
                    "frequency": "no estructurada",
                    "duration": (
                        f"{duration_days} dias" if duration_days is not None else ""
                    ),
                    "route": "no estructurada",
                }
            )
            medication_facts.append(
                MedicationClinicalFacts(
                    active_ingredient=active_ingredient,
                    duration_days=duration_days,
                )
            )

        context = ClinicalContext()
        diagnosis_mapping = DiagnosisContextService().extract(
            diagnosis_rows,
            index_date=PILOT_OBSERVATION_END,
            medication_index_date=index_date,
            existing_context=context.model_dump(),
            lookback_days=PILOT_OBSERVATION_DAYS,
        )
        for field, value in diagnosis_mapping["updates"].items():
            setattr(context, field, value)
        context.diagnosis_codes = diagnosis_mapping["diagnosis_codes"]
        context.diagnosis_code_counts = diagnosis_mapping["diagnosis_code_counts"]
        context.diagnosis_provenance = diagnosis_mapping["evidence"]

        lab_mapping = LabContextService.extract(
            lab_rows,
            index_date=PILOT_OBSERVATION_END,
            medication_index_date=index_date,
            existing_context=context.model_dump(),
            lookback_days=PILOT_OBSERVATION_DAYS,
        )
        for field, value in lab_mapping["updates"].items():
            setattr(context, field, value)
        context.lab_provenance = lab_mapping["evidence"]
        context.medication_facts = medication_facts

        raw_sex = str(patient.get("sexo") or "")
        canonical_sex = _canonical(raw_sex)
        sex = (
            "Masculino"
            if canonical_sex in {"M", "MASCULINO", "HOMBRE"}
            else "Femenino"
            if canonical_sex in {"F", "FEMENINO", "MUJER"}
            else raw_sex
        )
        return {
            "patient_code": patient_code,
            "age": int(patient["age"]),
            "sex": sex,
            "diagnoses": (
                ", ".join(diagnosis_mapping["diagnosis_codes"])
                or ", ".join(sorted(medication_diagnoses))
            ),
            "clinical_context": context.model_dump(mode="json"),
            "medications": medications,
            "medication_index_date": index_date.isoformat(),
            "clinical_observation_start_date": PILOT_OBSERVATION_START.isoformat(),
            "clinical_observation_end_date": PILOT_OBSERVATION_END.isoformat(),
        }

    @staticmethod
    def _select_overlap_episode(
        medication_rows: pl.DataFrame,
    ) -> tuple[date | None, pl.DataFrame]:
        """Elige el dia con mas medicamentos top activos, sin mezclar todo el anio."""
        if medication_rows.is_empty():
            return None, medication_rows

        rows = medication_rows.to_dicts()
        intervals: list[tuple[dict, date, date]] = []
        for row in rows:
            start = row.get("fecha_despacho")
            if not isinstance(start, date):
                continue
            raw_duration = row.get("duracion_dias")
            duration_days = max(int(raw_duration or 1), 1)
            intervals.append((row, start, start + timedelta(days=duration_days - 1)))
        if not intervals:
            return None, medication_rows.head(0)

        best_date: date | None = None
        best_active: list[dict] = []
        for candidate in sorted({start for _, start, _ in intervals}):
            active_by_name: dict[str, dict] = {}
            for row, start, end in intervals:
                if start <= candidate <= end:
                    active_by_name[str(row["medication"])] = row
            active = list(active_by_name.values())
            if len(active) > len(best_active):
                best_date = candidate
                best_active = active
        return best_date, pl.DataFrame(best_active, schema=medication_rows.schema)

    @staticmethod
    def _episode_at_date(
        medication_rows: pl.DataFrame,
        requested_date: date,
    ) -> tuple[date, pl.DataFrame]:
        active_by_name: dict[str, dict] = {}
        for row in medication_rows.iter_rows(named=True):
            start = row.get("fecha_despacho")
            if not isinstance(start, date):
                continue
            duration_days = max(int(row.get("duracion_dias") or 1), 1)
            end = start + timedelta(days=duration_days - 1)
            if start <= requested_date <= end:
                active_by_name[str(row["medication"])] = row
        if not active_by_name:
            return requested_date, medication_rows.head(0)
        return requested_date, pl.DataFrame(
            list(active_by_name.values()), schema=medication_rows.schema
        )

    @staticmethod
    def _alias_names() -> list[str]:
        alias_path = Path(settings.DDINTER_ALIAS_FILE)
        if not alias_path.is_file():
            return []
        with alias_path.open("r", encoding="utf-8-sig", newline="") as handle:
            aliases = [
                row["local_active_ingredient"].strip()
                for row in csv.DictReader(handle)
                if row.get("local_active_ingredient", "").strip()
            ]
        return sorted(aliases, key=len, reverse=True)

    @classmethod
    def _active_ingredient(cls, medication_name: str) -> str:
        canonical_medication = _canonical(medication_name)
        for alias in cls._alias_names():
            canonical_alias = _canonical(alias)
            if canonical_alias and canonical_alias in canonical_medication:
                return alias

        # Conserva el nombre farmacologico anterior a la primera concentracion.
        # No intenta inferir sinonimos: esos deben permanecer en el CSV auditable.
        ingredient = re.split(r"\s+\d", medication_name, maxsplit=1)[0]
        return ingredient.strip(" /-") or medication_name

    def _patient_rows(self, patient_code: str):
        patients, medications, labs, diagnoses = self._frames()
        patient = patients.filter(pl.col("patient_code") == patient_code)
        if patient.is_empty():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Paciente pseudonimizado '{patient_code}' no encontrado.",
            )
        return (
            patient.row(0, named=True),
            medications.filter(pl.col("patient_code") == patient_code),
            labs.filter(pl.col("patient_code") == patient_code),
            diagnoses.filter(pl.col("patient_code") == patient_code),
        )

    def evaluate(
        self,
        db: Session,
        patient_code: str,
        supplied_context: ClinicalContext | None = None,
        *,
        requested_index_date: date | None = None,
    ) -> dict:
        patient, medication_rows, lab_rows, diagnosis_rows = self._patient_rows(
            patient_code
        )
        if medication_rows.is_empty():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="El paciente de muestra no tiene medicamentos priorizados.",
            )

        if requested_index_date is not None:
            if requested_index_date.year != settings.PILOT_OBSERVATION_YEAR:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        "La muestra piloto solo contiene datos de "
                        f"{settings.PILOT_OBSERVATION_YEAR}."
                    ),
                )
            index_date, active_medication_rows = self._episode_at_date(
                medication_rows, requested_index_date
            )
        else:
            index_date, active_medication_rows = self._select_overlap_episode(
                medication_rows
            )
        if index_date is None or active_medication_rows.is_empty():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "No hay medicamentos del top V1 activos en la fecha solicitada."
                    if requested_index_date is not None
                    else "No se pudo construir un episodio temporal de medicamentos."
                ),
            )
        grouped = (
            active_medication_rows.group_by("medication", maintain_order=True)
            .agg(
                pl.col("duracion_dias").max().alias("duration_days"),
                pl.col("diagnosis_code").drop_nulls().unique().alias("diagnoses"),
            )
        )
        medication_payload: list[MedicationCreate] = []
        medication_facts: list[MedicationClinicalFacts] = []
        medication_diagnoses: set[str] = set()
        for row in grouped.iter_rows(named=True):
            name = str(row["medication"])
            active_ingredient = self._active_ingredient(name)
            duration_value = row.get("duration_days")
            duration_days = int(duration_value) if duration_value is not None else None
            medication_diagnoses.update(
                str(item) for item in (row.get("diagnoses") or []) if item
            )
            medication_payload.append(
                MedicationCreate(
                    entered_name=name,
                    normalized_active_ingredient=active_ingredient,
                    dose="no estructurada",
                    dose_unit="no estructurada",
                    frequency="no estructurada",
                    duration=(f"{duration_days} dias" if duration_days is not None else None),
                    route="no estructurada",
                )
            )
            medication_facts.append(
                MedicationClinicalFacts(
                    active_ingredient=active_ingredient,
                    duration_days=duration_days,
                )
            )

        context = (supplied_context or ClinicalContext()).model_copy(deep=True)
        diagnosis_mapping = DiagnosisContextService().extract(
            diagnosis_rows,
            index_date=PILOT_OBSERVATION_END,
            medication_index_date=index_date,
            existing_context=context.model_dump(),
            lookback_days=PILOT_OBSERVATION_DAYS,
        )
        for field, value in diagnosis_mapping["updates"].items():
            setattr(context, field, value)
        context.diagnosis_codes = diagnosis_mapping["diagnosis_codes"]
        context.diagnosis_code_counts = diagnosis_mapping["diagnosis_code_counts"]
        context.diagnosis_provenance = diagnosis_mapping["evidence"]
        lab_mapping = LabContextService.extract(
            lab_rows,
            index_date=PILOT_OBSERVATION_END,
            medication_index_date=index_date,
            existing_context=context.model_dump(),
            lookback_days=PILOT_OBSERVATION_DAYS,
        )
        for field, value in lab_mapping["updates"].items():
            setattr(context, field, value)
        context.lab_provenance = lab_mapping["evidence"]
        existing_facts = {item.active_ingredient: item for item in context.medication_facts}
        for fact in medication_facts:
            existing_facts.setdefault(fact.active_ingredient, fact)
        context.medication_facts = list(existing_facts.values())

        case_data = ClinicalCaseCreate(
            case_code=f"TEST-{patient_code}-{uuid4().hex[:8].upper()}",
            age=int(patient["age"]),
            sex=str(patient.get("sexo") or "No registrado"),
            diagnoses=(
                ", ".join(diagnosis_mapping["diagnosis_codes"])
                or ", ".join(sorted(medication_diagnoses))
                or "No estructurados en la muestra"
            ),
            clinical_context=context,
            is_simulated=True,
            medications=medication_payload,
        )
        case = CaseService.create_case(db, case_data)
        evaluation = EvaluationService.evaluate_case(db, case.id)
        medication_classification = ClinicalCatalogService().classify_medications(
            case.medications
        )
        patient_summary = next(
            item for item in self.list_patients() if item["patient_code"] == patient_code
        )
        return {
            "patient": patient_summary,
            "case": case,
            "evaluation": evaluation,
            "data_availability": {
                "medications_loaded": len(medication_payload),
                "diagnoses_loaded": diagnosis_mapping["distinct_diagnosis_codes"],
                "medication_index_date": index_date.isoformat(),
                "clinical_observation_start_date": PILOT_OBSERVATION_START.isoformat(),
                "clinical_observation_end_date": PILOT_OBSERVATION_END.isoformat(),
                "clinical_observation_mode": "retrospective_full_calendar_year_2025",
                "medication_catalog_classification": medication_classification,
                "raw_lab_rows_2025": lab_rows.height,
                "labs_mapped_to_clinical_context": bool(lab_mapping["updates"]),
                "mapped_lab_fields": lab_mapping["evidence"],
                "relevant_lab_rows_rejected": lab_mapping[
                    "relevant_lab_rows_rejected"
                ],
                "future_relevant_lab_rows_excluded": lab_mapping[
                    "future_relevant_lab_rows_excluded"
                ],
                "lab_lookback_days": lab_mapping["lookback_days"],
                "lab_mapping_warnings": lab_mapping["warnings"],
                "diagnosis_source": "sample_diagnoses_2025.parquet from atenmed.parquet",
                "diagnosis_rows_considered": diagnosis_mapping[
                    "diagnosis_rows_considered"
                ],
                "distinct_diagnosis_codes": diagnosis_mapping[
                    "distinct_diagnosis_codes"
                ],
                "future_diagnosis_rows_excluded": diagnosis_mapping[
                    "future_diagnosis_rows_excluded"
                ],
                "mapped_diagnosis_fields": diagnosis_mapping["evidence"],
                "diagnosis_mapping_warnings": diagnosis_mapping["warnings"],
                "unresolved_clinical_fields": [
                    label
                    for label, field in UNRESOLVED_CLINICAL_FIELDS.items()
                    if getattr(context, field) is None
                ],
                "note": (
                    "El piloto usa retrospectivamente todos los laboratorios y CIE-10 "
                    "aceptados entre 2025-01-01 y 2025-12-31. Cada valor conserva evidencia "
                    "y advertencias; la ausencia de CIE-10 no se interpreta como ausencia "
                    "de enfermedad. La fecha indice solo determina los medicamentos del top "
                    "V1 activos; la elegibilidad de polifarmacia proviene de la cohorte completa."
                ),
            },
        }
