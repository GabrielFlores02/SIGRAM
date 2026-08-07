"""Conservative mapping from raw pilot laboratory rows to ClinicalContext."""

from __future__ import annotations

import re
import unicodedata
import hashlib
import json
from datetime import date, datetime, timedelta
from typing import Any

import polars as pl


DIRECT_ANALYTES: dict[str, tuple[str, set[int], set[str], str]] = {
    "POTASIO": ("potassium_mmol_l", {84132}, {"MMOL/L"}, "mmol/L"),
    "SODIO": ("sodium_mmol_l", {84295}, {"MMOL/L"}, "mmol/L"),
    "TSH": ("tsh_miu_l", {84443}, {"UIU/ML", "UUI/ML"}, "mIU/L"),
    "HORMONA TSH": (
        "tsh_miu_l",
        {84443},
        {"UIU/ML", "UUI/ML"},
        "mIU/L",
    ),
    "TSH HORMONA ESTIMULANTE DE LA TIROIDES": (
        "tsh_miu_l",
        {84443},
        {"UIU/ML", "UUI/ML"},
        "mIU/L",
    ),
    "PROTEINAS EN ORINA 24 HORAS": (
        "proteinuria_mg_24h",
        {84156},
        {"MG/24H"},
        "mg/24h",
    ),
    "TFG FORMULA CKD EPI 2021": (
        "egfr_ml_min_1_73m2",
        {82565},
        {"ML/MIN/1.73"},
        "mL/min/1.73m2",
    ),
    "TFG": (
        "egfr_ml_min_1_73m2",
        {82565},
        {"ML/MIN/1.73"},
        "mL/min/1.73m2",
    ),
}
DIRECT_TEST_DESCRIPTIONS = {
    "egfr_ml_min_1_73m2": {"DOSAJE DE CREATININA EN SANGRE"},
}
FREE_T4_ANALYTES = {"T4 LIBRE", "HORMONA T4 LIBRE"}
RELEVANT_TOKENS = (
    "POTASIO",
    "SODIO",
    "TSH",
    "T4 LIBRE",
    "PROTEINAS EN ORINA 24 HORAS",
    "FILTRADO GLOMERULAR",
    "TFG",
    "EGFR",
)


def _canonical(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    return re.sub(r"[^A-Z0-9]+", " ", ascii_text.upper()).strip()


def _unit(value: str) -> str:
    text = (value or "").replace("µ", "u").replace("μ", "u")
    return re.sub(r"\s+", "", text).upper()


def _number(value: str) -> float | None:
    text = (value or "").strip()
    if not re.fullmatch(r"[+-]?\d+(?:[.,]\d+)?", text):
        return None
    return float(text.replace(",", "."))


def _date(value: str) -> date | None:
    try:
        return datetime.strptime((value or "").strip(), "%d/%m/%y").date()
    except ValueError:
        return None


def _reference_range(row: dict[str, Any]) -> tuple[float, float, str] | None:
    for key in ("normal_value_raw", "other_normal_value_raw"):
        raw = str(row.get(key) or "").strip()
        match = re.fullmatch(
            r"\[?\s*([+-]?\d+(?:[.,]\d+)?)\s*-\s*"
            r"([+-]?\d+(?:[.,]\d+)?)\s*\]?",
            raw,
        )
        if match:
            low = float(match.group(1).replace(",", "."))
            high = float(match.group(2).replace(",", "."))
            if low <= high:
                return low, high, raw
    return None


class LabContextService:
    """Maps only explicitly recognized analytes and units; no clinical formulas."""

    @staticmethod
    def _is_relevant(analyte: str) -> bool:
        canonical = _canonical(analyte)
        return any(token in canonical for token in RELEVANT_TOKENS)

    @classmethod
    def extract(
        cls,
        laboratory_rows: pl.DataFrame,
        *,
        index_date: date,
        medication_index_date: date | None = None,
        existing_context: dict[str, Any] | None = None,
        lookback_days: int = 365,
    ) -> dict[str, Any]:
        existing = existing_context or {}
        earliest = index_date - timedelta(days=max(lookback_days, 0))
        candidates: dict[str, list[dict[str, Any]]] = {}
        rejected = 0
        future_relevant = 0

        for row in laboratory_rows.iter_rows(named=True):
            analyte_raw = str(row.get("analyte") or "")
            analyte = _canonical(analyte_raw)
            if not cls._is_relevant(analyte_raw):
                continue
            result_date = _date(str(row.get("result_date_raw") or ""))
            if result_date is None:
                rejected += 1
                continue
            if result_date > index_date:
                future_relevant += 1
                continue
            if result_date < earliest:
                rejected += 1
                continue

            field: str | None = None
            value: float | bool | None = None
            reference_raw: str | None = None
            standardized_unit: str | None = None
            derived_method = "direct_numeric_result"
            unit = _unit(str(row.get("unit") or ""))
            exam_code = int(row.get("exam_code") or 0)

            direct = DIRECT_ANALYTES.get(analyte)
            if direct is not None:
                field, accepted_codes, accepted_units, standardized_unit = direct
                if exam_code not in accepted_codes or unit not in accepted_units:
                    rejected += 1
                    continue
                accepted_descriptions = DIRECT_TEST_DESCRIPTIONS.get(field)
                test_description = _canonical(str(row.get("test_description") or ""))
                if (
                    accepted_descriptions is not None
                    and test_description not in accepted_descriptions
                ):
                    rejected += 1
                    continue
                value = _number(str(row.get("result_value_raw") or ""))
            elif analyte in FREE_T4_ANALYTES:
                field = "free_t4_normal"
                if exam_code != 84439:
                    rejected += 1
                    continue
                numeric = _number(str(row.get("result_value_raw") or ""))
                reference = _reference_range(row)
                if numeric is not None and reference is not None:
                    low, high, reference_raw = reference
                    value = low <= numeric <= high
                    standardized_unit = "boolean_within_source_reference_range"
                    derived_method = "numeric_result_within_source_reference_range"

            if field is None or value is None:
                rejected += 1
                continue
            fingerprint_source = {
                key: row.get(key)
                for key in (
                    "result_date_raw",
                    "exam_code",
                    "analyte",
                    "unit",
                    "result_value_raw",
                    "normal_value_raw",
                    "other_normal_value_raw",
                    "validation_status",
                )
            }
            fingerprint = hashlib.sha256(
                json.dumps(
                    fingerprint_source, ensure_ascii=True, sort_keys=True, default=str
                ).encode("utf-8")
            ).hexdigest()
            if medication_index_date is None:
                temporal_relation = "medication_index_not_provided"
            elif result_date < medication_index_date:
                temporal_relation = "before_index"
            elif result_date == medication_index_date:
                temporal_relation = "on_index"
            else:
                temporal_relation = "after_index"
            candidates.setdefault(field, []).append(
                {
                    "field": field,
                    "value": value,
                    "result_date_obj": result_date,
                    "result_date": result_date.isoformat(),
                    "age_days_at_index": (index_date - result_date).days,
                    "medication_index_date": (
                        medication_index_date.isoformat()
                        if medication_index_date
                        else None
                    ),
                    "temporal_relation_to_medication_index": temporal_relation,
                    "used_under_pilot_full_year_rule": bool(
                        medication_index_date
                        and result_date > medication_index_date
                    ),
                    "exam_code": exam_code,
                    "source_analyte": analyte_raw.strip(),
                    "source_unit": str(row.get("unit") or "").strip(),
                    "source_value_raw": str(row.get("result_value_raw") or "").strip(),
                    "standardized_unit": str(standardized_unit),
                    "source_file": "sample_labs_2025.parquet",
                    "source_row_sha256": fingerprint,
                    "mapping_version": "pilot-labs-v1-2026-07-31",
                    "derived_method": derived_method,
                    "reference_range_raw": reference_raw,
                    "validation_status": row.get("validation_status"),
                    "validation_status_semantics": "unknown",
                    "quality_flags": [
                        "validation_status_semantics_not_documented"
                    ],
                }
            )

        updates: dict[str, float | bool] = {}
        evidence: list[dict[str, Any]] = []
        warnings = [
            "VALID_RESULT is preserved but its value semantics are not documented.",
            "Only direct mappings are used; eGFR is accepted only when ESSI reports TFG directly and is not calculated from creatinine.",
            "The 365-day lookback is a provisional pilot rule requiring clinical validation.",
        ]
        for field, field_candidates in sorted(candidates.items()):
            latest_date = max(item["result_date_obj"] for item in field_candidates)
            latest = [
                item for item in field_candidates if item["result_date_obj"] == latest_date
            ]
            unique_values = {item["value"] for item in latest}
            if len(unique_values) != 1:
                rejected += len(latest)
                warnings.append(
                    f"Ambiguous same-day values were not applied for {field}."
                )
                continue
            selected = latest[0]
            selected.pop("result_date_obj", None)
            if selected["age_days_at_index"] > 180:
                selected["quality_flags"].append("result_older_than_180_days")
            if selected["used_under_pilot_full_year_rule"]:
                selected["quality_flags"].append(
                    "result_after_medication_index_used_by_full_year_pilot_rule"
                )
            if existing.get(field) is not None:
                selected["applied"] = False
                selected["reason"] = "manual_context_has_priority"
            else:
                selected["applied"] = True
                selected["reason"] = "latest_accepted_result_on_or_before_index"
                updates[field] = selected["value"]
            evidence.append(selected)

        return {
            "updates": updates,
            "evidence": evidence,
            "relevant_lab_rows_rejected": rejected,
            "future_relevant_lab_rows_excluded": future_relevant,
            "warnings": warnings,
            "lookback_days": lookback_days,
        }
