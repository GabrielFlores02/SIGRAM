from datetime import date

import polars as pl

from backend.app.services.clinical_catalog_service import ClinicalCatalogService
from backend.app.services.diagnosis_context_service import DiagnosisContextService


def _row(**overrides):
    row = {
        "attention_date": date(2025, 5, 1),
        "diagnosis_position": 1,
        "diagnosis_code": "M19.9",
    }
    row.update(overrides)
    return row


def test_maps_positive_cie10_and_excludes_future_rows():
    rows = pl.DataFrame(
        [
            _row(diagnosis_code="M19.9"),
            _row(diagnosis_code="N18.2"),
            _row(attention_date=date(2025, 8, 1), diagnosis_code="M81.0"),
        ]
    )

    result = DiagnosisContextService().extract(
        rows, index_date=date(2025, 7, 1), existing_context={}
    )

    assert result["updates"]["osteoarthritis"] is True
    assert result["updates"]["chronic_kidney_disease_diagnosis"] is True
    assert "osteoporosis_or_fragility_fracture" not in result["updates"]
    assert result["future_diagnosis_rows_excluded"] == 1
    assert result["diagnosis_code_counts"] == {"M19.9": 1, "N18.2": 1}


def test_manual_context_has_priority_over_cie10_mapping():
    result = DiagnosisContextService().extract(
        pl.DataFrame([_row()]),
        index_date=date(2025, 7, 1),
        existing_context={"osteoarthritis": False},
    )

    assert "osteoarthritis" not in result["updates"]
    evidence = next(
        item for item in result["evidence"] if item["field"] == "osteoarthritis"
    )
    assert evidence["applied"] is False
    assert evidence["reason"] == "manual_context_has_priority"


def test_absence_of_code_does_not_create_negative_context():
    result = DiagnosisContextService().extract(
        pl.DataFrame([_row(diagnosis_code="I10")]),
        index_date=date(2025, 7, 1),
        existing_context={},
    )

    assert result["updates"]["hypertension_diagnosis"] is True
    assert "osteoarthritis" not in result["updates"]
    assert "falls_history" not in result["updates"]


def test_qualified_cie10_is_supporting_evidence_not_measurement_replacement():
    result = DiagnosisContextService().extract(
        pl.DataFrame([_row(diagnosis_code="N18.2")]),
        index_date=date(2025, 7, 1),
        existing_context={},
    )

    assert result["updates"]["chronic_kidney_disease_diagnosis"] is True
    assert "egfr_ml_min_1_73m2" not in result["updates"]
    evidence = result["evidence"][0]
    assert evidence["satisfies_context_field"] is False
    assert "egfr_ml_min_1_73m2" in evidence["related_fields"]


def test_criterion_report_traces_cie10_evidence():
    provenance = {
        "field": "osteoarthritis",
        "applied": True,
        "related_fields": ["osteoarthritis"],
        "matched_codes": [{"code": "M19.9", "count": 1}],
    }
    _, results = ClinicalCatalogService().evaluate(
        ["DICLOFENACO"],
        age=75,
        sex="F",
        clinical_context={
            "osteoarthritis": True,
            "medication_facts": [{"duration_days": 120}],
            "diagnosis_provenance": [provenance],
        },
    )
    stopp_h3 = next(item for item in results if item["criterion_code"] == "STOPP-H3")

    assert stopp_h3["context_used"]["osteoarthritis"] is True
    assert stopp_h3["diagnosis_evidence"] == [provenance]


def test_marks_diagnosis_after_medication_index_under_full_year_rule():
    result = DiagnosisContextService().extract(
        pl.DataFrame([_row(attention_date=date(2025, 8, 1))]),
        index_date=date(2025, 12, 31),
        medication_index_date=date(2025, 7, 1),
        existing_context={},
        lookback_days=364,
    )

    evidence = result["evidence"][0]
    assert evidence["temporal_relation_to_medication_index"] == "after_index"
    assert evidence["used_under_pilot_full_year_rule"] is True
    assert "diagnosis_after_medication_index_used_by_full_year_pilot_rule" in evidence[
        "quality_flags"
    ]
