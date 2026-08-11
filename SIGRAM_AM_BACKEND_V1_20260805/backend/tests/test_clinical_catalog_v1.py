from pathlib import Path
from datetime import datetime, timezone

from backend.app.config import settings
from backend.app.schemas.evaluations import EvaluationExecutionRead
from backend.app.services.clinical_catalog_service import ClinicalCatalogService


def _result_by_code(results, code):
    return next(item for item in results if item["criterion_code"] == code)


def test_catalog_v1_has_expected_scope():
    summary = ClinicalCatalogService().summary()
    assert summary["catalog_version"] == "2026-07-30-top-medications-v1"
    assert summary["medication_count"] == 54
    assert summary["criterion_count"] == 97
    assert summary["criteria_by_system"] == {"beers": 23, "stopp_start": 74}


def test_beers_b01_requires_manual_review_until_clinical_rule_is_validated():
    alerts, results = ClinicalCatalogService().evaluate(
        ["ALPRAZOLAM"],
        age=75,
        sex="F",
        clinical_context={},
    )
    beers_alerts = [item for item in alerts if item["rule_code"] == "B01"]
    assert beers_alerts == []
    b01 = _result_by_code(results, "B01")
    assert b01["status"] == "manual_review"
    assert b01["source_table"] == "Table 2"


def test_missing_falls_and_renal_function_are_reported():
    _, results = ClinicalCatalogService().evaluate(
        ["GABAPENTINA"],
        age=70,
        sex="M",
        clinical_context={},
    )
    b14 = _result_by_code(results, "B14")
    b19 = _result_by_code(results, "B19")
    assert b14["status"] == "not_evaluable"
    assert b14["missing_data"][0]["field"] == "falls_history"
    assert b19["status"] == "not_evaluable"
    assert b19["missing_data"][0]["field"] == "egfr_ml_min_1_73m2"


def test_metformin_low_egfr_generates_stopp_alert():
    alerts, results = ClinicalCatalogService().evaluate(
        ["METFORMINA"],
        age=80,
        sex="F",
        clinical_context={"egfr_ml_min_1_73m2": 25},
    )
    assert _result_by_code(results, "STOPP-E6")["status"] == "alert"
    assert any(item["rule_code"] == "STOPP-E6" for item in alerts)


def test_aine_without_ppi_generates_start_screen():
    alerts, results = ClinicalCatalogService().evaluate(
        ["DICLOFENACO"],
        age=72,
        sex="M",
        clinical_context={},
    )
    assert _result_by_code(results, "START-F3")["status"] == "alert"
    assert any(item["rule_code"] == "START-F3" for item in alerts)


def test_beers_under_65_is_marked_as_out_of_scope():
    _, results = ClinicalCatalogService().evaluate(
        ["ALPRAZOLAM"],
        age=62,
        sex="F",
        clinical_context={},
    )
    b01 = _result_by_code(results, "B01")
    assert b01["age_scope"] == "out_of_scope_60_64"
    assert b01["status"] == "out_of_scope"


def test_duration_is_scoped_to_the_implicated_medication_and_b05_detects_combination():
    alerts, results = ClinicalCatalogService().evaluate(
        ["DICLOFENACO", "DEXAMETASONA", "ACIDO FOLICO"],
        age=72,
        sex="F",
        clinical_context={
            "safer_alternatives_ineffective": True,
            "medication_facts": [
                {"active_ingredient": "DICLOFENACO", "duration_days": 3},
                {"active_ingredient": "ACIDO FOLICO", "duration_days": 30},
            ]
        },
    )
    b05 = _result_by_code(results, "B05")
    assert b05["status"] == "activated"
    assert b05["context_used"]["medication_duration_days"] == 3
    assert {
        item.get("medication") for item in b05["triggering_evidence"]
    }.issuperset({"DICLOFENACO", "DEXAMETASONA"})
    assert b05["exception_status"] == "partial_exception_requires_confirmation"
    assert any(item["rule_code"] == "B05" for item in alerts)


def test_complete_b05_exception_suppresses_alert_and_reports_protector():
    alerts, results = ClinicalCatalogService().evaluate(
        ["DICLOFENACO", "DEXAMETASONA", "OMEPRAZOL"],
        age=72,
        sex="F",
        clinical_context={
            "safer_alternatives_ineffective": True,
            "medication_facts": [
                {"active_ingredient": "DICLOFENACO", "duration_days": 3}
            ],
        },
    )
    b05 = _result_by_code(results, "B05")
    assert b05["status"] == "no_alert"
    assert b05["exception_status"] == "exception_applied"
    assert any(
        item.get("medication") == "OMEPRAZOL"
        for item in b05["protective_evidence"]
    )
    assert not any(item["rule_code"] == "B05" for item in alerts)


def test_b16_exception_for_opioid_transition_is_applied():
    _, alert_results = ClinicalCatalogService().evaluate(
        ["TRAMADOL", "GABAPENTINA"],
        age=75,
        sex="M",
        clinical_context={},
    )
    assert _result_by_code(alert_results, "B16")["status"] == "activated"

    _, excepted_results = ClinicalCatalogService().evaluate(
        ["TRAMADOL", "GABAPENTINA"],
        age=75,
        sex="M",
        clinical_context={"opioid_transition_or_dose_reduction": True},
    )
    b16 = _result_by_code(excepted_results, "B16")
    assert b16["status"] == "no_alert"
    assert b16["exception_status"] == "exception_applied"


def test_beers_b02_b03_and_b18_keep_screening_separate_from_classification():
    alerts, results = ClinicalCatalogService().evaluate(
        ["ORFENADRINA"], age=75, sex="F", clinical_context={}
    )
    b02 = _result_by_code(results, "B02")
    b03 = _result_by_code(results, "B03")
    b18 = _result_by_code(results, "B18")
    assert b02["status"] == "activated"
    assert b02["recommendation_text"] == "Evitar."
    assert b03["status"] == "supporting_classification"
    assert b03["counts_as_clinical_finding"] is False
    assert b18["status"] == "no_alert"
    assert any(item["rule_code"] == "B02" for item in alerts)
    assert not any(item["rule_code"] == "B03" for item in alerts)


def test_beers_b16_requires_opioid_and_returns_both_implicated_medications():
    _, gabapentin_only = ClinicalCatalogService().evaluate(
        ["GABAPENTINA"], age=75, sex="F", clinical_context={}
    )
    assert _result_by_code(gabapentin_only, "B16")["status"] == "no_alert"

    _, combination = ClinicalCatalogService().evaluate(
        ["TRAMADOL", "GABAPENTINA"], age=75, sex="F", clinical_context={}
    )
    b16 = _result_by_code(combination, "B16")
    assert b16["status"] == "activated"
    assert b16["implicated_medications"] == ["GABAPENTINA", "TRAMADOL"]
    assert "GABAPENTINA, TRAMADOL" in b16["reason"]


def test_beers_b17_uses_strict_three_or_more_cns_medication_threshold():
    _, two_cns = ClinicalCatalogService().evaluate(
        ["GABAPENTINA", "ORFENADRINA"], age=75, sex="F", clinical_context={}
    )
    b17_two = _result_by_code(two_cns, "B17")
    assert b17_two["status"] == "no_alert"
    assert b17_two["trigger_facts"]["cns_active_count"] == 2

    _, three_cns = ClinicalCatalogService().evaluate(
        ["ALPRAZOLAM", "GABAPENTINA", "TRAMADOL"], age=75, sex="F", clinical_context={}
    )
    b17_three = _result_by_code(three_cns, "B17")
    assert b17_three["status"] == "activated"
    assert b17_three["trigger_facts"]["cns_active_count"] == 3
    assert b17_three["implicated_medications"] == ["ALPRAZOLAM", "GABAPENTINA", "TRAMADOL"]

    _, four_cns = ClinicalCatalogService().evaluate(
        ["ALPRAZOLAM", "GABAPENTINA", "ORFENADRINA", "TRAMADOL"], age=75, sex="F", clinical_context={}
    )
    assert _result_by_code(four_cns, "B17")["trigger_facts"]["cns_active_count"] == 4
    assert _result_by_code(four_cns, "B17")["status"] == "activated"


def test_non_opioid_analgesic_does_not_activate_beers_b16_or_b17():
    _, results = ClinicalCatalogService().evaluate(
        ["GABAPENTINA", "ORFENADRINA", "PARACETAMOL"],
        age=75,
        sex="F",
        clinical_context={},
    )
    b16 = _result_by_code(results, "B16")
    b17 = _result_by_code(results, "B17")
    assert b16["status"] == "no_alert"
    assert b17["status"] == "no_alert"
    assert b17["trigger_facts"]["cns_active_count"] == 2
    assert b17["trigger_facts"]["medications"] == ["GABAPENTINA", "ORFENADRINA"]


def test_non_opioid_analgesic_does_not_create_beers_b15_combination():
    _, results = ClinicalCatalogService().evaluate(
        ["ALPRAZOLAM", "PARACETAMOL"], age=75, sex="F", clinical_context={}
    )
    assert _result_by_code(results, "B15")["status"] == "no_alert"


def test_beers_b04_requires_duration_and_maintenance_indication():
    _, missing_results = ClinicalCatalogService().evaluate(
        ["OMEPRAZOL"], age=75, sex="F", clinical_context={}
    )
    assert _result_by_code(missing_results, "B04")["status"] == "not_evaluable"

    _, active_results = ClinicalCatalogService().evaluate(
        ["OMEPRAZOL"],
        age=75,
        sex="F",
        clinical_context={
            "ppi_maintenance_indication": False,
            "medication_facts": [{"active_ingredient": "OMEPRAZOL", "duration_days": 60}],
        },
    )
    assert _result_by_code(active_results, "B04")["status"] == "activated"


def test_beers_b06_b19_b20_and_b23_expose_conditional_or_manual_state():
    _, results = ClinicalCatalogService().evaluate(
        ["DICLOFENACO", "GABAPENTINA", "TRAMADOL", "TAMSULOSINA"],
        age=75,
        sex="M",
        clinical_context={
            "heart_failure_status": "asymptomatic",
            "egfr_ml_min_1_73m2": 25,
            "tramadol_release_formulation": "extended_release",
        },
    )
    assert _result_by_code(results, "B06")["status"] == "activated"
    assert _result_by_code(results, "B06")["recommendation_type"] == "use_with_caution"
    assert _result_by_code(results, "B19")["status"] == "activated"
    assert _result_by_code(results, "B19")["recommendation_type"] == "reduce_dose"
    assert _result_by_code(results, "B20")["status"] == "activated"
    assert _result_by_code(results, "B20")["recommendation_text"] == "Evitar la formulación de liberación extendida."
    assert _result_by_code(results, "B23")["status"] == "manual_review"


def test_stopp_protective_coprescription_changes_result():
    base_context = {"peptic_ulcer_history": True}
    _, unprotected = ClinicalCatalogService().evaluate(
        ["DEXAMETASONA"], age=76, sex="F", clinical_context=base_context
    )
    assert _result_by_code(unprotected, "STOPP-F5")["status"] == "alert"

    _, protected = ClinicalCatalogService().evaluate(
        ["DEXAMETASONA", "OMEPRAZOL"],
        age=76,
        sex="F",
        clinical_context=base_context,
    )
    stopp_f5 = _result_by_code(protected, "STOPP-F5")
    assert stopp_f5["status"] == "no_alert"
    assert stopp_f5["exception_status"] == "protector_present"


def test_combination_precondition_prevents_irrelevant_missing_data():
    _, results = ClinicalCatalogService().evaluate(
        ["ACIDO ACETILSALICILICO"],
        age=78,
        sex="M",
        clinical_context={},
    )
    stopp_c4 = _result_by_code(results, "STOPP-C4")
    assert stopp_c4["status"] == "no_alert"
    assert stopp_c4["missing_data"] == []
    assert stopp_c4["exception_status"] == "not_applicable"


def test_catalog_and_source_endpoints(client):
    summary = client.get("/api/catalog/v1/summary")
    assert summary.status_code == 200
    assert summary.json()["medication_count"] == 54

    medications = client.get("/api/catalog/v1/medications")
    assert medications.status_code == 200
    assert len(medications.json()) == 54
    assert all(item["pharmacologic_group"] for item in medications.json())

    sources = client.get("/api/pilot/v1/sources")
    large_sources_present = all(
        Path(path).is_file()
        for path in (settings.PILOT_COHORT_FILE, settings.PILOT_LABS_FILE)
    )
    if large_sources_present:
        assert sources.status_code == 200
        assert sources.json()["status"] == "ready_for_local_prototype"
    else:
        assert sources.status_code == 503
        missing = set(sources.json()["detail"]["sources"])
        assert {"cohort", "laboratory_results"}.issubset(missing)


def test_api_separates_full_report_from_frontend_findings(client):
    payload = {
        "case_code": "CASE-V1-GABAPENTIN",
        "age": 62,
        "sex": "F",
        "diagnoses": "Dolor en evaluación",
        "is_simulated": True,
        "clinical_context": {},
        "medications": [
            {
                "entered_name": "Gabapentina 300 mg",
                "normalized_active_ingredient": "gabapentina",
                "dose": "300",
                "dose_unit": "mg",
                "frequency": "diaria",
                "route": "oral",
            }
        ],
    }
    created = client.post("/api/cases", json=payload)
    evaluated = client.post(f"/api/cases/{created.json()['id']}/evaluate")
    assert evaluated.status_code == 200
    data = evaluated.json()
    assert any(
        item["criterion_code"] == "B14"
        and item["status"] == "out_of_scope"
        for item in data["criteria_report"]
    )
    assert all(item["status"] in {"alert", "activated"} for item in data["clinical_findings"])
    assert not any(item["criterion_code"] == "B14" for item in data["data_gaps"])
    systems = {item["system"]: item for item in data["analysis_results"]}
    assert systems["beers"]["out_of_scope_count"] >= 1


def test_classification_keeps_essi_presentation_and_group():
    class Medication:
        entered_name = "DICLOFENACO SÓDICO 25 MG / ML X 3 ML"
        normalized_active_ingredient = "DICLOFENACO"

    classification = ClinicalCatalogService().classify_medications([Medication()])
    assert classification
    assert classification[0]["essi_presentation"] == Medication.entered_name
    assert classification[0]["evaluation_name"] == "DICLOFENACO"
    assert classification[0]["matched_top_v1"] is True
    assert "ANTIINFLAMATORIO" in classification[0][
        "pharmacologic_group"
    ].upper()


def test_response_schema_preserves_legacy_rows_and_builds_frontend_views():
    _, technical_report = ClinicalCatalogService().evaluate(
        ["ALPRAZOLAM", "GABAPENTINA"],
        age=75,
        sex="F",
        clinical_context={},
    )
    assert any(item["status"] == "not_evaluable" for item in technical_report)
    now = datetime.now(timezone.utc)
    response = EvaluationExecutionRead.model_validate(
        {
            "id": 1,
            "case_id": 1,
            "started_at": now,
            "finished_at": now,
            "processing_time_ms": 1.0,
            "successful": True,
            "functional_error": False,
            "error_detail": None,
            "total_medications": 2,
            "total_alerts": 1,
            "created_at": now,
            "alerts": [],
            "criteria_report": technical_report,
        }
    )
    assert any(item.status == "not_evaluable" for item in response.criteria_report)
    assert response.clinical_findings == []
    assert response.data_gaps
    assert all(item.status == "not_evaluable" for item in response.data_gaps)
