from backend.app.services.renal_function_service import (
    COCKCROFT_GAULT_METHOD,
    cockcroft_gault_creatinine_clearance,
    enrich_with_cockcroft_gault,
)


def test_cockcroft_gault_uses_actual_body_weight_and_female_adjustment():
    assert cockcroft_gault_creatinine_clearance(
        age=76, sex="Femenino", weight_kg=63, serum_creatinine_mg_dl=1.2
    ) == 39.7


def test_calculated_crcl_is_saved_with_traceable_inputs():
    context = enrich_with_cockcroft_gault(
        {
            "weight_kg": 63,
            "height_cm": 160,
            "serum_creatinine_mg_dl": 1.2,
            "serum_creatinine_date": "2026-08-13",
        },
        age=76,
        sex="Femenino",
    )
    assert context["creatinine_clearance_ml_min"] == 39.7
    assert context["creatinine_clearance_source"] == "calculated"
    assert context["creatinine_clearance_method"] == COCKCROFT_GAULT_METHOD
    assert context["creatinine_clearance_inputs"]["weight_basis"] == "actual_body_weight"


def test_documented_crcl_has_priority_over_pilot_calculation():
    context = enrich_with_cockcroft_gault(
        {
            "weight_kg": 63,
            "serum_creatinine_mg_dl": 1.2,
            "creatinine_clearance_ml_min": 40,
        },
        age=76,
        sex="Femenino",
    )
    assert context["creatinine_clearance_ml_min"] == 40
    assert context["creatinine_clearance_source"] == "documented"
