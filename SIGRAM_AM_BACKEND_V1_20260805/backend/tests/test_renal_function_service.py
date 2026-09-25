from backend.app.services.renal_function_service import (
    CKD_EPI_2021_CREATININE_METHOD,
    COCKCROFT_GAULT_METHOD,
    ckd_epi_2021_egfr,
    cockcroft_gault_creatinine_clearance,
    enrich_with_cockcroft_gault,
)


def test_ckd_epi_2021_calculates_egfr_without_weight():
    assert ckd_epi_2021_egfr(
        age=76, sex="Femenino", serum_creatinine_mg_dl=1.2
    ) == 46.9


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
    assert context["egfr_ml_min_1_73m2"] == 46.9
    assert context["egfr_source"] == "calculated"
    assert context["egfr_method"] == CKD_EPI_2021_CREATININE_METHOD
    assert context["lab_provenance"][-1]["field"] == "egfr_ml_min_1_73m2"


def test_egfr_is_calculated_when_weight_is_not_available():
    context = enrich_with_cockcroft_gault(
        {"serum_creatinine_mg_dl": 1.2},
        age=76,
        sex="Femenino",
    )

    assert context["egfr_ml_min_1_73m2"] == 46.9
    assert "creatinine_clearance_ml_min" not in context


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
