"""Mapeo conservador de atenciones CIE-10 a contexto clinico del piloto."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import polars as pl

from backend.app.config import settings


CIE10_PATTERN = re.compile(r"^[A-Z][0-9]{2}(?:\.[0-9A-Z]{1,4})?$")


def normalize_cie10(value: str) -> str | None:
    code = re.sub(r"\s+", "", str(value or "").upper())
    if not CIE10_PATTERN.fullmatch(code):
        return None
    return code


def _matches(code: str, pattern: str) -> bool:
    normalized_pattern = str(pattern).upper().strip()
    if normalized_pattern.endswith("*"):
        return code.startswith(normalized_pattern[:-1])
    return code == normalized_pattern


class DiagnosisContextService:
    """Usa CIE-10 solo como evidencia positiva; nunca infiere ausencia."""

    def __init__(self, mapping_path: str | Path | None = None):
        self.mapping_path = Path(
            mapping_path or settings.CIE10_CONTEXT_MAPPING_FILE
        )

    def _mapping(self) -> dict[str, Any]:
        return json.loads(self.mapping_path.read_text(encoding="utf-8"))

    def extract(
        self,
        diagnosis_rows: pl.DataFrame,
        *,
        index_date: date,
        medication_index_date: date | None = None,
        existing_context: dict[str, Any] | None = None,
        lookback_days: int = 365,
    ) -> dict[str, Any]:
        existing = existing_context or {}
        earliest = index_date - timedelta(days=max(lookback_days, 0))
        future_rows = 0
        invalid_rows = 0
        accepted_rows: list[dict[str, Any]] = []

        for row in diagnosis_rows.iter_rows(named=True):
            attention_date = row.get("attention_date")
            if not isinstance(attention_date, date):
                invalid_rows += 1
                continue
            if attention_date > index_date:
                future_rows += 1
                continue
            if attention_date < earliest:
                continue
            code = normalize_cie10(str(row.get("diagnosis_code") or ""))
            if code is None:
                invalid_rows += 1
                continue
            accepted_rows.append(
                {
                    "code": code,
                    "attention_date": attention_date,
                    "diagnosis_position": int(row.get("diagnosis_position") or 0),
                }
            )

        code_counts = Counter(item["code"] for item in accepted_rows)
        mapping = self._mapping()
        updates: dict[str, bool] = {}
        evidence: list[dict[str, Any]] = []

        for item in mapping["mappings"]:
            matches = [
                row
                for row in accepted_rows
                if any(_matches(row["code"], pattern) for pattern in item["patterns"])
            ]
            if not matches:
                continue
            by_code: dict[str, list[date]] = defaultdict(list)
            for match in matches:
                by_code[match["code"]].append(match["attention_date"])
            matched_codes = [
                {
                    "code": code,
                    "count": len(dates),
                    "first_attention_date": min(dates).isoformat(),
                    "last_attention_date": max(dates).isoformat(),
                }
                for code, dates in sorted(by_code.items())
            ]
            field = item["field"]
            manual_priority = existing.get(field) is not None
            applied = not manual_priority
            if applied:
                updates[field] = bool(item["value"])
            quality_flags = [
                "positive_evidence_only",
                "absence_of_code_does_not_mean_absence_of_condition",
            ]
            if not item.get("satisfies_context_field", False):
                quality_flags.append(
                    "supporting_diagnosis_does_not_complete_qualified_criterion_field"
                )
            match_dates = [match["attention_date"] for match in matches]
            if medication_index_date is None:
                temporal_relation = "medication_index_not_provided"
            elif all(value <= medication_index_date for value in match_dates):
                temporal_relation = "before_or_on_index"
            elif all(value > medication_index_date for value in match_dates):
                temporal_relation = "after_index"
            else:
                temporal_relation = "spans_index"
            used_under_full_year_rule = bool(
                medication_index_date
                and any(value > medication_index_date for value in match_dates)
            )
            if used_under_full_year_rule:
                quality_flags.append(
                    "diagnosis_after_medication_index_used_by_full_year_pilot_rule"
                )
            evidence.append(
                {
                    "field": field,
                    "value": bool(item["value"]),
                    "applied": applied,
                    "reason": (
                        "manual_context_has_priority"
                        if manual_priority
                        else "documented_cie10_before_or_on_index_date"
                    ),
                    "matched_codes": matched_codes,
                    "first_attention_date": min(
                        match["attention_date"] for match in matches
                    ).isoformat(),
                    "last_attention_date": max(
                        match["attention_date"] for match in matches
                    ).isoformat(),
                    "medication_index_date": (
                        medication_index_date.isoformat()
                        if medication_index_date
                        else None
                    ),
                    "temporal_relation_to_medication_index": temporal_relation,
                    "used_under_pilot_full_year_rule": used_under_full_year_rule,
                    "source_rows_count": len(matches),
                    "source_file": "sample_diagnoses_2025.parquet",
                    "mapping_version": mapping["mapping_version"],
                    "classification": mapping["classification"],
                    "evidence_semantics": mapping["semantics"],
                    "satisfies_context_field": bool(
                        item.get("satisfies_context_field", False)
                    ),
                    "related_fields": list(item.get("related_fields") or []),
                    "label": item["label"],
                    "quality_flags": quality_flags,
                }
            )

        return {
            "updates": updates,
            "evidence": evidence,
            "diagnosis_codes": sorted(code_counts),
            "diagnosis_code_counts": dict(sorted(code_counts.items())),
            "diagnosis_rows_considered": len(accepted_rows),
            "distinct_diagnosis_codes": len(code_counts),
            "future_diagnosis_rows_excluded": future_rows,
            "invalid_diagnosis_rows_excluded": invalid_rows,
            "lookback_days": lookback_days,
            "warnings": [
                "CIE-10 from atenmed.parquet is used as positive evidence only.",
                "Code absence is not interpreted as absence of a condition.",
                "Qualified criteria still require severity, symptoms or measurements when stated.",
                "The 365-day diagnosis lookback is a provisional pilot rule.",
            ],
        }
