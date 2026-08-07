from datetime import date

import polars as pl

from backend.app.services.lab_context_service import LabContextService


def _row(**overrides):
    row = {
        "result_date_raw": "01/06/25",
        "exam_code": 84132,
        "test_description": "POTASIO EN SANGRE",
        "analyte": "POTASIO",
        "unit": "mmol/L",
        "result_value_raw": "4.5",
        "normal_value_raw": "",
        "other_normal_value_raw": "",
        "validation_status": 0,
    }
    row.update(overrides)
    return row


def test_maps_latest_prior_numeric_result_and_excludes_future():
    rows = pl.DataFrame(
        [
            _row(result_date_raw="01/05/25", result_value_raw="4.1"),
            _row(result_date_raw="01/06/25", result_value_raw="4.5"),
            _row(result_date_raw="01/08/25", result_value_raw="6.2"),
        ]
    )

    result = LabContextService.extract(
        rows, index_date=date(2025, 7, 1), existing_context={}
    )

    assert result["updates"] == {"potassium_mmol_l": 4.5}
    assert result["future_relevant_lab_rows_excluded"] == 1
    assert result["evidence"][0]["result_date"] == "2025-06-01"


def test_rejects_unrecognized_unit_and_non_numeric_result():
    rows = pl.DataFrame(
        [
            _row(unit="mg/dL"),
            _row(result_value_raw="< 4.0"),
        ]
    )

    result = LabContextService.extract(
        rows, index_date=date(2025, 7, 1), existing_context={}
    )

    assert result["updates"] == {}
    assert result["relevant_lab_rows_rejected"] == 2


def test_maps_free_t4_only_when_reference_range_is_available():
    rows = pl.DataFrame(
        [
            _row(
                exam_code=84439,
                analyte="HORMONA T4 LIBRE",
                unit="ng/dL",
                result_value_raw="0.89",
                normal_value_raw="0.7-1.48",
            )
        ]
    )

    result = LabContextService.extract(
        rows, index_date=date(2025, 7, 1), existing_context={}
    )

    assert result["updates"] == {"free_t4_normal": True}
    assert result["evidence"][0]["reference_range_raw"] == "0.7-1.48"


def test_manual_context_has_priority_over_laboratory():
    rows = pl.DataFrame([_row(result_value_raw="6.1")])

    result = LabContextService.extract(
        rows,
        index_date=date(2025, 7, 1),
        existing_context={"potassium_mmol_l": 4.0},
    )

    assert result["updates"] == {}
    assert result["evidence"][0]["applied"] is False
    assert result["evidence"][0]["reason"] == "manual_context_has_priority"


def test_same_day_conflicting_values_are_not_applied():
    rows = pl.DataFrame(
        [
            _row(result_value_raw="4.0"),
            _row(result_value_raw="5.0"),
        ]
    )

    result = LabContextService.extract(
        rows, index_date=date(2025, 7, 1), existing_context={}
    )

    assert result["updates"] == {}
    assert any("Ambiguous" in warning for warning in result["warnings"])


def test_tsh_micro_unit_is_normalized_to_miu_l():
    rows = pl.DataFrame(
        [
            _row(
                exam_code=84443,
                analyte="TSH - HORMONA ESTIMULANTE DE LA TIROIDES",
                unit="µUI/mL",
                result_value_raw="1.68",
            )
        ]
    )

    result = LabContextService.extract(
        rows, index_date=date(2025, 7, 1), existing_context={}
    )

    assert result["updates"] == {"tsh_miu_l": 1.68}
    assert result["evidence"][0]["standardized_unit"] == "mIU/L"


def test_does_not_infer_context_from_unapproved_analytes():
    rows = pl.DataFrame(
        [
            _row(exam_code=82310, analyte="CALCIO", unit="", result_value_raw="9.07"),
            _row(
                exam_code=82043,
                analyte="MICROALBUMINURIA",
                unit="mg/L",
                result_value_raw="18.7",
            ),
            _row(
                exam_code=82570,
                analyte="CREATININA EN ORINA",
                unit="mg/dL",
                result_value_raw="75.37",
            ),
        ]
    )

    result = LabContextService.extract(
        rows, index_date=date(2025, 7, 1), existing_context={}
    )

    assert result["updates"] == {}
    assert result["evidence"] == []


def test_maps_only_directly_reported_egfr_with_exact_essi_identity():
    rows = pl.DataFrame(
        [
            _row(
                exam_code=82565,
                test_description="DOSAJE DE CREATININA EN SANGRE",
                analyte="TFG (Fórmula CKD-EPI 2021)",
                unit="mL/min/1.73 ",
                result_value_raw="42.7",
            )
        ]
    )

    result = LabContextService.extract(
        rows, index_date=date(2025, 7, 1), existing_context={}
    )

    assert result["updates"] == {"egfr_ml_min_1_73m2": 42.7}
    assert result["evidence"][0]["derived_method"] == "direct_numeric_result"


def test_rejects_tfg_label_when_essi_test_identity_does_not_match():
    rows = pl.DataFrame(
        [
            _row(
                exam_code=82565,
                test_description="OTRA PRUEBA",
                analyte="TFG",
                unit="mL/min/1.73",
                result_value_raw="42.7",
            )
        ]
    )

    result = LabContextService.extract(
        rows, index_date=date(2025, 7, 1), existing_context={}
    )

    assert result["updates"] == {}
    assert result["relevant_lab_rows_rejected"] == 1


def test_marks_lab_after_medication_index_under_full_year_rule():
    result = LabContextService.extract(
        pl.DataFrame([_row(result_date_raw="01/08/25")]),
        index_date=date(2025, 12, 31),
        medication_index_date=date(2025, 7, 1),
        existing_context={},
        lookback_days=364,
    )

    evidence = result["evidence"][0]
    assert evidence["temporal_relation_to_medication_index"] == "after_index"
    assert evidence["used_under_pilot_full_year_rule"] is True
    assert "result_after_medication_index_used_by_full_year_pilot_rule" in evidence[
        "quality_flags"
    ]
